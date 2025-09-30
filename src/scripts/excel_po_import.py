"""
Excelから発注を作成する外部スクリプト

対象ファイル: 材料管理.xlsx
対象シート: 材料管理表

抽出条件:
- Z列(指定納期)が入力あり
- AC列(入荷日)が空

マッピング:
- N列(管理NO) → 発注番号(order_number)
- AA列(手配先) → 仕入れ先(supplier)
- 今日 → 発注日(order_date)
- Z列(指定納期) → 納期予定日(expected_delivery_date)
- I列(品番) → 用途・製品名(purpose) および 材料の part_number
- L列(材料) → 材料名解析（CSVインポートと同等のロジック）

材料登録方針:
- 専用/汎用の判定は「マスターに既存があり、その材料が専用のときのみ専用」。
- 既存検索は name, shape, diameter_mm で実施し、専用品番が一致する既存があればそれを優先。
- 既存がなければ新規作成（UsageType=GENERAL、dedicated_part_number=None、part_number に I列を設定）。

発注作成方針:
- 行単位で1件の発注を作成（アイテムは1点）
- 未設定の長さは既定 2500mm、発注方式は本数指定、数量は1本（変更可）

使い方:
  python -m src.scripts.excel_po_import --excel "材料管理.xlsx" --sheet "材料管理表" --dry-run
"""

from __future__ import annotations

import argparse
import logging
from datetime import datetime
from typing import Optional, Dict, Any

import pandas as pd

from src.db import SessionLocal
from src.db.models import (
    Material, MaterialShape, UsageType,
    PurchaseOrder, PurchaseOrderItem, PurchaseOrderStatus, OrderType,
    User, UserRole
)

# 既存の解析ロジックを再利用
from src.api.excel_viewer import parse_material_info
from src.utils.auth import get_password_hash

logger = logging.getLogger("excel_po_import")
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


DEFAULT_LENGTH_MM = 2500
DEFAULT_ORDER_QUANTITY = 1

# 材質名から比重の推定（materials APIのデータベースを要約）
DEFAULT_DENSITIES = {
    # ステンレス系
    'SUS303': 7.93,
    'SUS304': 7.93,
    'SUS316': 7.98,
    'SUS430': 7.70,
    'SUS440C': 7.70,
    'SUS440': 7.70,
    # 炭素鋼系
    'S45C': 7.85,
    'S45CFS': 7.85,
    'S45CF': 7.85,
    'S50C': 7.85,
    'S55C': 7.85,
    'SK': 7.85,
    'ASK2600S': 7.85,
    'ASK2200R': 7.85,
    'SF-20T': 7.85,
    '1144': 7.85,
    'TLS': 7.85,
    'G23-T8': 7.85,
    # 黄銅系
    'C3604': 8.49,
    'C3604LCD': 8.49,
    'C3602': 8.49,
    'C3602LCD': 8.49,
    'C3601': 8.49,
    # リン青銅系
    'C5191': 8.80,
    'C5212': 8.80,
    # アルミニウム系
    'A2024': 2.78,
    'A2017': 2.79,
    'A5056': 2.64,
    'A6061': 2.70,
    'A7075': 2.80,
    # チタン系
    'TI': 4.51,
    'TC4': 4.43,
}


def guess_density(material_name: str) -> float:
    text = (material_name or "").upper()
    for key, value in DEFAULT_DENSITIES.items():
        if key in text:
            return value
    return 7.85  # 既定（炭素鋼）


def parse_excel_material(material_text: str) -> Optional[Dict[str, Any]]:
    """L列の材料仕様を解析して name/shape/diameter/専用品番 を返す"""
    info = parse_material_info(material_text)
    if not info:
        return None
    return {
        "name": info["material_name"],
        "shape": info["shape"],
        "diameter_mm": info["diameter"],
        "dedicated_part_number": info.get("dedicated_part_number"),
    }


def find_or_create_material(db, name: str, shape: MaterialShape, diameter_mm: float,
                            part_number: Optional[str], dedicated_part_number: Optional[str]) -> Material:
    """既存材料検索。なければ登録。専用判定はマスター既存のときのみ。

    優先順位:
      1) 専用品番が指定されている場合は、同一 name/shape/diameter かつ専用品番一致の既存を優先
      2) それが無ければ、同一 name/shape/diameter の汎用既存を使用
      3) 既存が無ければ新規作成（UsageType=GENERAL, dedicated_part_number=None）
    """

    # 1) 専用既存（専用品番一致）
    if dedicated_part_number:
        existing_dedicated = (
            db.query(Material)
            .filter(
                Material.name == name,
                Material.shape == shape,
                Material.diameter_mm == diameter_mm,
                Material.is_active == True,
                Material.usage_type == UsageType.DEDICATED,
                Material.dedicated_part_number == dedicated_part_number,
            )
            .first()
        )
        if existing_dedicated:
            return existing_dedicated

    # 2) 汎用既存
    existing_general = (
        db.query(Material)
        .filter(
            Material.name == name,
            Material.shape == shape,
            Material.diameter_mm == diameter_mm,
            Material.is_active == True,
            Material.usage_type == UsageType.GENERAL,
        )
        .first()
    )
    if existing_general:
        return existing_general

    # 3) 既存が無ければ新規（専用扱いはしない）
    density = guess_density(name)
    material = Material(
        part_number=part_number,
        name=name,
        shape=shape,
        diameter_mm=diameter_mm,
        current_density=density,
        usage_type=UsageType.GENERAL,
        dedicated_part_number=None,
        is_active=True,
    )
    db.add(material)
    db.flush()
    logger.info(
        f"材料を新規登録: id={material.id}, {name} {shape.value} {diameter_mm}mm, part={part_number} dedicated=None"
    )
    return material


def import_excel_to_purchase_orders(excel_path: str, sheet_name: str, dry_run: bool = False) -> Dict[str, Any]:
    """Excelを読み取り、条件一致行ごとに発注を登録する"""
    df = pd.read_excel(excel_path, sheet_name=sheet_name, engine="openpyxl")

    # 列インデックス（0始まり）
    COL_ITEM_CODE = 8   # I列: 品番
    COL_MATERIAL = 11   # L列: 材料
    COL_ORDER_QTY = 19  # T列: 発注本数/重量値
    COL_UNIT = 20       # U列: 単位（本/kg/束）
    COL_DUE = 25        # Z列: 指定納期
    COL_SUPPLIER = 26   # AA列: 手配先
    COL_RECEIVED_DATE = 28  # AC列: 入荷日
    COL_ORDER_NUMBER = 13   # N列: 管理NO（発注番号）

    # マージセル等で上段にのみ値が入っているケースへの対応（前方埋め）
    # 納期(Z列)と手配先(AA列)はグループ単位でマージされていることがある
    due_series = df.iloc[:, COL_DUE].ffill()
    supplier_series = df.iloc[:, COL_SUPPLIER].ffill()
    # 単位(U列)もグループで指定される可能性があるため前方埋め
    unit_series = df.iloc[:, COL_UNIT].ffill()

    total_rows = len(df)
    processed = 0
    created_orders = 0
    skipped = 0
    errors: list[str] = []

    db = SessionLocal()
    try:
        def is_blank(val) -> bool:
            if pd.isna(val):
                return True
            s = str(val).strip()
            return s == "" or s in {"-", "－", "—"}

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
                # マージ対応後の値を使用（Z, AA）
                due = due_series.iloc[idx]
                supplier = supplier_series.iloc[idx] if not pd.isna(supplier_series.iloc[idx]) else None
                received = row.iloc[COL_RECEIVED_DATE]
                order_number = row.iloc[COL_ORDER_NUMBER] if not pd.isna(row.iloc[COL_ORDER_NUMBER]) else None

                # 発注数量・単位取得（T/U列）
                raw_qty = row.iloc[COL_ORDER_QTY] if not pd.isna(row.iloc[COL_ORDER_QTY]) else None
                unit = normalize_unit(unit_series.iloc[idx]) if df.shape[1] > COL_UNIT else None
                qty_value: Optional[float] = None
                if raw_qty is not None and not is_blank(raw_qty):
                    try:
                        qty_value = float(raw_qty)
                    except Exception:
                        qty_value = None

                # 取り込み条件: I列(品番)非空、L列(材料)非空、Z列(指定納期)入力あり、AC列(入荷日)が空扱い（"-"/"－"/"—"も空）
                if (
                    is_blank(item_code)
                    or is_blank(material_text)
                    or is_blank(due)
                    or (not is_blank(received))
                ):
                    skipped += 1
                    logger.warning(
                        f"{idx+1}行: 取り込み条件不一致のためスキップ (I='{item_code}', L='{material_text}', Z='{due}', AC='{received}')"
                    )
                    continue

                if not supplier or str(supplier).strip() == "":
                    skipped += 1
                    logger.warning(f"{idx+1}行: 仕入先が未入力のためスキップ")
                    continue

                if not order_number or str(order_number).strip() == "":
                    skipped += 1
                    logger.warning(f"{idx+1}行: 管理NO(発注番号)が未入力のためスキップ")
                    continue

                # 発注番号重複チェック
                existing_order = db.query(PurchaseOrder).filter(PurchaseOrder.order_number == str(order_number).strip()).first()
                if existing_order:
                    skipped += 1
                    logger.info(f"{idx+1}行: 発注番号重複のためスキップ ({order_number})")
                    continue

                # 材料仕様解析
                parsed = parse_excel_material(material_text)
                if not parsed:
                    skipped += 1
                    logger.warning(f"{idx+1}行: 材料仕様を解析できないためスキップ: '{material_text}'")
                    continue

                # 材料の検索/登録
                material = find_or_create_material(
                    db,
                    name=parsed["name"],
                    shape=parsed["shape"],
                    diameter_mm=float(parsed["diameter_mm"]),
                    part_number=str(item_code).strip() if item_code else None,
                    dedicated_part_number=parsed.get("dedicated_part_number"),
                )

                if dry_run:
                    processed += 1
                    logger.info(f"DRY-RUN: 発注作成予定 - 発注番号={order_number}, 仕入先={supplier}, 用途={item_code}, 材料ID={material.id}")
                    continue

                # 発注作成
                po = PurchaseOrder(
                    order_number=str(order_number).strip(),
                    supplier=str(supplier).strip(),
                    order_date=datetime.now(),
                    expected_delivery_date=pd.to_datetime(due) if not pd.isna(due) else None,
                    purpose=str(item_code).strip() if item_code else None,
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

                item = PurchaseOrderItem(
                    purchase_order_id=po.id,
                    material_id=material.id,
                    material_name=material.name,
                    shape=material.shape,
                    diameter_mm=material.diameter_mm,
                    length_mm=DEFAULT_LENGTH_MM,
                    density=material.current_density,
                    order_type=order_type,
                    ordered_quantity=ordered_quantity,
                    ordered_weight_kg=ordered_weight_kg,
                    unit_price=None,
                    is_new_material=False,
                    usage_type=material.usage_type,
                    dedicated_part_number=material.dedicated_part_number,
                )
                db.add(item)

                created_orders += 1
                processed += 1
                logger.info(
                    f"発注作成: id={po.id}, 発注番号={po.order_number}, アイテムid={item.id}, 単位={unit}, 値={qty_value}, order_type={order_type.value}"
                )

            except Exception as e:
                skipped += 1
                errors.append(f"行{idx+1}: {e}")
                logger.exception(f"行{idx+1}処理中にエラー: {e}")
                db.rollback()

        if not dry_run:
            db.commit()
            logger.info("コミット完了")

        return {
            "total_rows": total_rows,
            "processed": processed,
            "created_orders": created_orders,
            "skipped": skipped,
            "errors": errors,
            "dry_run": dry_run,
        }
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description="Excelから発注を作成する外部スクリプト")
    parser.add_argument("--excel", type=str, default="材料管理.xlsx", help="Excelファイルパス")
    parser.add_argument("--sheet", type=str, default="材料管理表", help="シート名")
    parser.add_argument("--dry-run", action="store_true", help="DBへ書き込まず検証のみ")
    args = parser.parse_args()

    result = import_excel_to_purchase_orders(args.excel, args.sheet, dry_run=args.dry_run)
    logger.info(f"結果: {result}")


if __name__ == "__main__":
    main()