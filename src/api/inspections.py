from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from datetime import datetime

from src.db import get_db
from src.db.models import Lot, InspectionStatus

router = APIRouter(prefix="/api/inspections", tags=["検品"])


class InspectionRequest(BaseModel):
    inspection_date: datetime = Field(..., description="確認日")
    measured_value: float | None = Field(None, description="実測値")
    appearance_ok: bool = Field(..., description="外観")
    bending_ok: bool = Field(..., description="曲がり")
    inspector_name: str = Field(..., max_length=100, description="作業者名")
    notes: str | None = Field(None, description="備考")


@router.post("/lots/{lot_id}/", response_model=dict, status_code=status.HTTP_200_OK)
async def submit_inspection(lot_id: int, body: InspectionRequest, db: Session = Depends(get_db)):
    lot = db.query(Lot).filter(Lot.id == lot_id).first()
    if not lot:
        raise HTTPException(status_code=404, detail="ロットが見つかりません")

    lot.inspected_at = body.inspection_date
    lot.measured_value = body.measured_value
    lot.appearance_ok = body.appearance_ok
    lot.bending_ok = body.bending_ok
    lot.inspected_by_name = body.inspector_name
    lot.inspection_notes = body.notes

    lot.inspection_status = (
        InspectionStatus.PASSED if (body.appearance_ok and body.bending_ok) else InspectionStatus.FAILED
    )

    db.commit()
    return {
        "message": "検品情報を保存しました",
        "lot_id": lot.id,
        "inspection_status": lot.inspection_status.value,
    }


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