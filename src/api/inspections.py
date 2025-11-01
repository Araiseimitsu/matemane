from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload
from pydantic import BaseModel, Field
from datetime import datetime
import re

from src.db import get_db
from src.db.models import Lot, InspectionStatus, Item, PurchaseOrderItem

router = APIRouter(prefix="/api/inspections", tags=["検品"])


class InspectionRequest(BaseModel):
    inspection_date: datetime = Field(..., description="確認日")
    bending_ok: bool = Field(..., description="曲がり")
    inspector_name: str = Field(..., max_length=100, description="作業者名")
    notes: str | None = Field(None, description="備考")
    scratch_ok: bool = Field(True, description="キズ")
    dirt_ok: bool = Field(True, description="汚れ")
    inspection_judgement: str | None = Field(None, description="判定結果")


@router.post("/lots/{lot_id}/", response_model=dict, status_code=status.HTTP_200_OK)
async def submit_inspection(lot_id: int, body: InspectionRequest, db: Session = Depends(get_db)):
    lot = db.query(Lot).filter(Lot.id == lot_id).first()
    if not lot:
        raise HTTPException(status_code=404, detail="ロットが見つかりません")

    lot.inspected_at = body.inspection_date
    lot.bending_ok = body.bending_ok
    lot.inspected_by_name = body.inspector_name
    lot.inspection_notes = body.notes

    # 判定ロジック：手動選択があれば優先、なければ全項目のANDで判定
    if body.inspection_judgement == 'pass':
        lot.inspection_status = InspectionStatus.PASSED
    elif body.inspection_judgement == 'fail':
        lot.inspection_status = InspectionStatus.FAILED
    else:
        # 自動判定：全項目がOKの場合のみ合格
        lot.inspection_status = (
            InspectionStatus.PASSED if (body.bending_ok and body.scratch_ok and body.dirt_ok) else InspectionStatus.FAILED
        )

    print(f"デバッグ: 検品処理開始 - Lot ID={lot_id}, Status={lot.inspection_status.value}")

    # 検品合格の場合にのみ在庫アイテムを登録
    if lot.inspection_status == InspectionStatus.PASSED:
        # 既に在庫アイテムが存在するかチェック
        existing_item = db.query(Item).filter(Item.lot_id == lot.id).first()
        print(f"デバッグ: 既存Itemチェック - Lot ID={lot.id}, Existing={existing_item is not None}")
        
        if not existing_item:
            # ロットの備考から置き場情報を抽出
            primary_location = None
            if lot.notes and "登録予定置き場:" in lot.notes:
                # 備考から置き場情報を解析
                location_match = re.search(r"登録予定置き場:\s*([\d,]+)", lot.notes)
                if location_match:
                    location_str = location_match.group(1)
                    # カンマ区切りで複数ある場合は最初の置き場を使用
                    locations = [loc.strip() for loc in location_str.split(",") if loc.strip()]
                    if locations:
                        try:
                            primary_location = int(locations[0])
                        except ValueError:
                            primary_location = None
            
            print(f"デバッグ: 置き場情報 - Location ID={primary_location}, Quantity={lot.initial_quantity}")
            
            # 在庫アイテムを作成
            inventory_item = Item(
                lot_id=lot.id,
                location_id=primary_location,
                current_quantity=lot.initial_quantity or 0
            )
            db.add(inventory_item)
            print(f"デバッグ: Item作成完了 - Item ID={inventory_item.id}")
            
            # 備考から登録予定置き場情報をクリア
            if lot.notes and "登録予定置き場:" in lot.notes:
                lot.notes = re.sub(r"\n?登録予定置き場:[^\n]*", "", lot.notes).strip()
                if not lot.notes:
                    lot.notes = None

    db.commit()
    print(f"デバッグ: 検品処理完了 - Lot ID={lot_id}")
    
    return {
        "message": "検品情報を保存しました",
        "lot_id": lot.id,
        "inspection_status": lot.inspection_status.value,
    }


@router.get("/lots/search/{lot_number}", response_model=dict)
async def search_lot_by_number(lot_number: str, db: Session = Depends(get_db)):
    """ロット番号でロットを検索"""
    lot = db.query(Lot).options(
        joinedload(Lot.material),
        joinedload(Lot.purchase_order_item).joinedload(PurchaseOrderItem.purchase_order)
    ).filter(
        Lot.lot_number == lot_number
    ).first()
    
    if not lot:
        raise HTTPException(status_code=404, detail="ロットが見つかりません")
    
    # 検品アイテム形式に変換
    result = {
        "id": lot.id,
        "management_code": lot.lot_number,
        "material": {
            "id": lot.material.id,
            "display_name": lot.material.display_name,
            "name": lot.material.display_name
        } if lot.material else None,
        "lot": {
            "id": lot.id,
            "lot_number": lot.lot_number,
            "inspection_status": lot.inspection_status.value if lot.inspection_status else "pending",
            "initial_weight_kg": lot.initial_weight_kg,
            "notes": lot.notes,
            "order_number": lot.purchase_order_item.purchase_order.order_number if lot.purchase_order_item and lot.purchase_order_item.purchase_order else None
        },
        "total_weight_kg": lot.initial_weight_kg,
        "current_quantity": lot.initial_quantity
    }
    
    return result


@router.get("/lots/pending/", response_model=list)
async def get_pending_inspection_lots(db: Session = Depends(get_db)):
    """検品待ちのロット一覧を取得"""
    lots = db.query(Lot).options(
        joinedload(Lot.material),
        joinedload(Lot.purchase_order_item).joinedload(PurchaseOrderItem.purchase_order)
    ).filter(
        Lot.inspection_status.in_([InspectionStatus.PENDING, InspectionStatus.FAILED])
    ).all()
    
    result = []
    for lot in lots:
        result.append({
            "id": lot.id,
            "lot_number": lot.lot_number,
            "material": {
                "id": lot.material.id,
                "display_name": lot.material.display_name,
                "name": lot.material.display_name
            } if lot.material else None,
            "initial_quantity": lot.initial_quantity,
            "initial_weight_kg": lot.initial_weight_kg,
            "inspection_status": lot.inspection_status.value if lot.inspection_status else "pending",
            "received_date": lot.received_date.isoformat() if lot.received_date else None,
            "notes": lot.notes,
            "purchase_order": {
                "id": lot.purchase_order_item.purchase_order.id,
                "order_number": lot.purchase_order_item.purchase_order.order_number
            } if lot.purchase_order_item and lot.purchase_order_item.purchase_order else None
        })
    
    return result


@router.get("/inspectors/", response_model=list)
async def list_inspectors(db: Session = Depends(get_db)):
    rows = (
        db.query(Lot.inspected_by_name)
        .filter(Lot.inspected_by_name != None)
        .group_by(Lot.inspected_by_name)
        .order_by(Lot.inspected_by_name)
        .all()
    )
    return [r[0] for r in rows]