"""
Excelから発注を作成する外部スクリプト

対象ファイル: \\192.168.1.200\共有\生産管理課\材料管理.xlsx
対象ファイル: 材料管理.xlsx
対象シート: 材料管理表

抽出条件:
- L列(材料)が非空
- M列(手配日)が入力あり
- Z列(指定納期)が入力あり
- AC列(入荷日)が空

マッピング:
- N列(管理NO) → 発注番号(order_number)
- AA列(手配先) → 仕入れ先(supplier)
- M列(手配日) → 発注日(order_date) ※空の場合は現在日時を使用
- Z列(指定納期) → 納期予定日(expected_delivery_date)
- I列(品番) → 備考(notes)に記録
- L列(材料) → 材料仕様文字列（そのまま保存、入庫時に人の手で解析）

材料登録方針:
- Excel取込時は材料仕様文字列をそのまま保存（自動解析しない）
- material_id = NULL、入庫時に人の手で材料マスタと紐付け
- is_new_material = True で入庫時の材料確定が必要なことを示す

発注作成方針:
- 行単位で1件の発注を作成（アイテムは1点）
- 未設定の長さは既定 2500mm、発注方式は本数指定、数量は1本（変更可）

使い方:
  python -m src.scripts.excel_po_import --excel "\\192.168.1.200\共有\生産管理課\材料管理.xlsx" --sheet "材料管理表" --dry-run
  python -m src.scripts.excel_po_import --excel "材料管理.xlsx" --sheet "材料管理表" --dry-run
"""

from __future__ import annotations

import argparse
import logging
import re
from collections import defaultdict
from datetime import datetime
from typing import Optional, Dict, Any

import pandas as pd
from sqlalchemy import or_

from src.db import SessionLocal
from src.db.models import (
    MaterialShape,
    PurchaseOrder, PurchaseOrderItem, PurchaseOrderStatus, OrderType,
    User, UserRole
)

from src.utils.auth import get_password_hash

logger = logging.getLogger("excel_po_import")
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


DEFAULT_LENGTH_MM = 2500
DEFAULT_ORDER_QUANTITY = 1
DEFAULT_DENSITY = 7.85  # 既定比重（入庫時に人の手で上書き）

def import_excel_to_purchase_orders(excel_path: str, sheet_name: str, dry_run: bool = False) -> Dict[str, Any]:
    """Excelを読み取り、条件一致行ごとに発注を登録する"""
    df = pd.read_excel(excel_path, sheet_name=sheet_name, engine="openpyxl")

    # 列インデックス（0始まり）
    COL_ITEM_CODE = 8   # I列: 品番
    COL_MATERIAL = 11   # L列: 材料
    COL_ORDER_DATE = 12 # M列: 手配日
    COL_ORDER_QTY = 19  # T列: 発注本数/重量値
    COL_UNIT = 20       # U列: 単位（本/kg/束）
    COL_DUE = 25        # Z列: 指定納期
    COL_SUPPLIER = 26   # AA列: 手配先
    COL_RECEIVED_DATE = 28  # AC列: 入荷日
    COL_ORDER_NUMBER = 13   # N列: 管理NO（発注番号）

    # マージセル等で上段にのみ値が入っているケースへの対応（前方埋め）
    # 手配先(AA列)はグループ単位でマージされていることがある
    supplier_series = df.iloc[:, COL_SUPPLIER].ffill()
    # 単位(U列)もグループで指定される可能性があるため前方埋め
    unit_series = df.iloc[:, COL_UNIT].ffill()
    # Z列(指定納期)は前方埋めしない（空行を確実にスキップするため）
    due_series = df.iloc[:, COL_DUE]

    total_rows = len(df)
    processed = 0
    created_orders = 0
    skipped = 0
    errors: list[str] = []
    skip_reasons: Dict[str, int] = defaultdict(int)

    db = SessionLocal()
    try:
        def normalize_management_no(raw: Any) -> Optional[str]:
            """管理NO/発注番号の表記ゆれを正規化"""
            if raw is None:
                return None
            if isinstance(raw, str):
                s = raw.strip()
                if not s or s.lower() in {"nan", "none"}:
                    return None
                # 整数を表す末尾の .0 / .00 を除去
                if re.fullmatch(r"\d+\.0+", s):
                    s = s.split(".")[0]
                return s
            if pd.isna(raw):
                return None
            if isinstance(raw, (int,)):
                return str(raw)
            if isinstance(raw, float):
                if pd.isna(raw):
                    return None
                if raw.is_integer():
                    return str(int(raw))
                # 想定外の小数はそのまま文字列化
                return str(raw).rstrip("0").rstrip(".")
            return str(raw).strip()

        def is_blank(val) -> bool:
            if pd.isna(val):
                return True
            s = str(val).strip()
            s_lower = s.lower()
            return s_lower == "" or s_lower in {"-", "－", "—", "null", "none", "n/a", "nan", "nat"}

        def normalize_unit(u: Any) -> Optional[str]:
            if u is None or pd.isna(u):
                return None
            import unicodedata
            s = str(u).strip()
            s = unicodedata.normalize('NFKC', s)
            s_lower = s.lower()
            if s_lower in {"本", "ほん", "本数"}:
                return "本"
            if s_lower in {"kg", "ｋｇ"}:
                return "kg"
            if s_lower in {"束"}:
                return "束"
            return s  # 未知の単位はそのまま返す

        def ensure_import_user_id() -> int:
            # 既存の有効ユーザー（調達/管理者）を優先
            user = (
                db.query(User)
                .filter(User.is_active == True, User.role.in_([UserRole.PURCHASE, UserRole.ADMIN]))
                .order_by(User.id.asc())
                .first()
            )
            if user:
                return user.id

            # 既存のsystem_importユーザーがあれば使用
            user = db.query(User).filter(User.username == "system_import").first()
            if user:
                return user.id

            # なければ作成（ワンタイムの自動ユーザー）
            sys_user = User(
                username="system_import",
                email="system_import@example.com",
                hashed_password=get_password_hash("system_import_auto"),
                full_name="System Import",
                role=UserRole.PURCHASE,
                is_active=True,
            )
            db.add(sys_user)
            db.flush()
            logger.info(f"システムユーザーを作成: id={sys_user.id}, username={sys_user.username}")
            return sys_user.id

        for idx, row in df.iterrows():
            try:
                # 列値の取得
                item_code = row.iloc[COL_ITEM_CODE] if not pd.isna(row.iloc[COL_ITEM_CODE]) else None
                material_text = row.iloc[COL_MATERIAL] if not pd.isna(row.iloc[COL_MATERIAL]) else None
                # M列(手配日)を取得
                raw_order_date = row.iloc[COL_ORDER_DATE] if not pd.isna(row.iloc[COL_ORDER_DATE]) else None
                # マージ対応後の値を使用（Z, AA）
                due = due_series.iloc[idx]
                supplier = supplier_series.iloc[idx] if not pd.isna(supplier_series.iloc[idx]) else None

                received_raw = None
                if len(row) > COL_RECEIVED_DATE:
                    received_raw = row.iloc[COL_RECEIVED_DATE]
                received_is_blank = is_blank(received_raw)
                raw_order_number = row.iloc[COL_ORDER_NUMBER] if not pd.isna(row.iloc[COL_ORDER_NUMBER]) else None
                order_number = normalize_management_no(raw_order_number)

                # 発注数量・単位取得（T/U列）
                raw_qty = row.iloc[COL_ORDER_QTY] if not pd.isna(row.iloc[COL_ORDER_QTY]) else None
                unit = normalize_unit(unit_series.iloc[idx]) if df.shape[1] > COL_UNIT else None
                qty_value: Optional[float] = None
                if raw_qty is not None and not is_blank(raw_qty):
                    try:
                        qty_value = float(raw_qty)
                    except Exception:
                        qty_value = None

                # 取り込み条件: L列(材料)非空、M列(手配日)入力あり、Z列(指定納期)入力あり、AC列(入荷日)が空扱い（"-"/"－"/"—"も空）
                if (
                    is_blank(material_text)
                    or is_blank(raw_order_date)
                    or is_blank(due)
                    or (not received_is_blank)
                ):
                    skipped += 1
                    if is_blank(material_text) or is_blank(due) or (not received_is_blank):
                        skip_reasons["mandatory_fields"] += 1
                    elif is_blank(raw_order_date):
                        skip_reasons["missing_order_date"] += 1
                    logger.warning(
                        f"{idx+1}行: 取り込み条件不一致のためスキップ (I='{item_code}', L='{material_text}', M='{raw_order_date}', Z='{due}', AC='{str(received_raw).strip() if received_raw is not None else received_raw}')"
                    )
                    continue

                # Z列(指定納期)の日付変換チェック
                try:
                    due_date = pd.to_datetime(due)
                except Exception as e:
                    skipped += 1
                    skip_reasons["invalid_due_date"] += 1
                    logger.warning(f"{idx+1}行: 指定納期の日付形式が無効なためスキップ (Z='{due}', エラー={e})")
                    continue

                if not supplier or str(supplier).strip() == "":
                    skipped += 1
                    skip_reasons["missing_supplier"] += 1
                    logger.warning(f"{idx+1}行: 仕入先が未入力のためスキップ")
                    continue

                if not order_number:
                    skipped += 1
                    skip_reasons["missing_order_number"] += 1
                    logger.warning(f"{idx+1}行: 管理NO(発注番号)が未入力のためスキップ")
                    continue

                # 発注番号重複チェック
                existing_order = db.query(PurchaseOrder).filter(
                    or_(
                        PurchaseOrder.order_number == order_number,
                        PurchaseOrder.order_number == f"{order_number}.0"
                    )
                ).first()
                if existing_order:
                    skipped += 1
                    skip_reasons["duplicate_order_number"] += 1
                    logger.info(f"{idx+1}行: 発注番号重複のためスキップ ({order_number})")
                    continue

                # 材料仕様文字列をそのまま保存（解析は入庫時に人の手で実施）
                # material_id は NULL、入庫時に確定する

                if dry_run:
                    processed += 1
                    # 手配日情報をログに追加
                    order_date_info = f"手配日={raw_order_date}" if raw_order_date and not is_blank(raw_order_date) else "手配日=なし(現在日時使用)"
                    logger.info(f"DRY-RUN: 発注作成予定 - 発注番号={order_number}, 仕入先={supplier}, 品番={item_code}, {order_date_info}, 材料仕様={material_text}")
                    continue

                # 発注作成（品番は備考に記録）
                notes_text = f"品番: {item_code}" if item_code else None
                
                # 発注日の設定：M列(手配日)を優先し、空の場合は現在日時を使用
                if raw_order_date and not is_blank(raw_order_date):
                    try:
                        order_date = pd.to_datetime(raw_order_date)
                    except Exception as e:
                        logger.warning(f"{idx+1}行: 手配日の日付変換に失敗したため現在日時を使用 (手配日='{raw_order_date}', エラー={e})")
                        order_date = datetime.now()
                else:
                    order_date = datetime.now()
                
                po = PurchaseOrder(
                    order_number=order_number,
                    supplier=str(supplier).strip(),
                    order_date=order_date,
                    expected_delivery_date=due_date,  # 事前に検証した日付を使用
                    notes=notes_text,
                    status=PurchaseOrderStatus.PENDING,
                    created_by=ensure_import_user_id(),
                )
                db.add(po)
                db.flush()

                # アイテム作成（T/U列に従い発注方式を決定）
                order_type = OrderType.QUANTITY
                ordered_quantity = None
                ordered_weight_kg = None

                if unit == "kg":
                    order_type = OrderType.WEIGHT
                    ordered_weight_kg = float(qty_value) if qty_value is not None else 0.0
                elif unit == "束":
                    # 束の場合は重量を0、数量はT列の値をそのまま本数として扱う
                    order_type = OrderType.QUANTITY
                    ordered_quantity = int(qty_value) if qty_value is not None else DEFAULT_ORDER_QUANTITY
                    ordered_weight_kg = 0.0
                else:  # 本 もしくは未知の単位は本数として扱う
                    order_type = OrderType.QUANTITY
                    ordered_quantity = int(qty_value) if qty_value is not None else DEFAULT_ORDER_QUANTITY

                # 現行DBスキーマに合わせて、アイテム情報はPurchaseOrderItemのフィールドのみ設定
                # 材料仕様文字列は item_name に保存（詳細は入庫時に材料へ確定）
                item = PurchaseOrderItem(
                    purchase_order_id=po.id,
                    item_name=str(material_text).strip(),
                    order_type=order_type,
                    ordered_quantity=ordered_quantity,
                    ordered_weight_kg=ordered_weight_kg,
                    unit_price=None,
                    kanri_no=order_number,  # 管理NOを保存
                )
                db.add(item)

                # 成功した行は即座にコミット（他行の失敗に巻き戻されないように）
                if not dry_run:
                    db.commit()

                created_orders += 1
                processed += 1
                logger.info(
                    f"発注作成: id={po.id}, 発注番号={po.order_number}, アイテムid={item.id}, 単位={unit}, 値={qty_value}, order_type={order_type.value}, item_name='{item.item_name}'"
                )

            except Exception as e:
                skipped += 1
                errors.append(f"行{idx+1}: {e}")
                skip_reasons["exceptions"] += 1
                logger.exception(f"行{idx+1}処理中にエラー: {e}")
                if not dry_run:
                    db.rollback()  # エラー行のみロールバック

        return {
            "total_rows": total_rows,
            "processed": processed,
            "created_orders": created_orders,
            "skipped": skipped,
            "errors": errors,
            "skip_reasons": dict(skip_reasons),
            "dry_run": dry_run,
        }

    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description="Excelから発注を作成する外部スクリプト")
    parser.add_argument(
        "--excel",
        type=str,
        default=r"\\192.168.1.200\共有\生産管理課\材料管理.xlsx",
        # default="材料管理.xlsx",
        help="Excelファイルパス",
    )
    parser.add_argument("--sheet", type=str, default="材料管理表", help="シート名")
    parser.add_argument("--dry-run", action="store_true", help="DBへ書き込まず検証のみ")
    args = parser.parse_args()

    result = import_excel_to_purchase_orders(args.excel, args.sheet, dry_run=args.dry_run)
    logger.info(f"結果: {result}")


if __name__ == "__main__":
    main()