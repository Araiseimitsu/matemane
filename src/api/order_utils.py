from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime
import logging
import re

from src.db import get_db
from src.db.models import PurchaseOrder

router = APIRouter()

logger = logging.getLogger(__name__)

def generate_order_number(db: Session) -> str:
    """ユニークな発注番号を生成"""
    now = datetime.now()
    date_prefix = now.strftime("%Y%m%d")

    latest_order = db.query(PurchaseOrder.order_number).filter(
        PurchaseOrder.order_number.like(f"PO-{date_prefix}-%")
    ).order_by(PurchaseOrder.order_number.desc()).first()

    next_seq = 1
    if latest_order:
        if isinstance(latest_order, tuple):
            latest_order_number = latest_order[0]
        else:
            latest_order_number = getattr(latest_order, "order_number", None)

        if latest_order_number:
            match = re.match(rf"PO-{date_prefix}-(\d+)\Z", latest_order_number)
            if match:
                try:
                    next_seq = int(match.group(1)) + 1
                except ValueError:
                    logger.warning("発注番号の連番抽出に失敗しました: %s", latest_order_number)
                    next_seq = 1
            else:
                logger.warning("想定外の発注番号形式を検出しました: %s", latest_order_number)

    order_number = f"PO-{date_prefix}-{next_seq:03d}"

    while db.query(PurchaseOrder).filter(PurchaseOrder.order_number == order_number).first():
        next_seq += 1
        order_number = f"PO-{date_prefix}-{next_seq:03d}"

    return order_number

@router.get("/generate", response_model=dict)
async def generate_order_number_endpoint(db: Session = Depends(get_db)):
    """発注番号を事前生成（プレビュー用）"""
    try:
        order_number = generate_order_number(db)
    except SQLAlchemyError as exc:
        logger.exception("発注番号生成時にデータベースエラーが発生しました", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="発注番号の自動生成に失敗しました。データベースの状態を確認してください。"
        ) from exc
    except Exception as exc:
        logger.exception("発注番号生成処理で予期しないエラーが発生しました", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="発注番号の自動生成に失敗しました。システム管理者に連絡してください。"
        ) from exc
    return {"order_number": order_number}