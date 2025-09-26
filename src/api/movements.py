from fastapi import APIRouter

router = APIRouter()

@router.get("/")
async def get_movements():
    """入出庫履歴取得"""
    return {"message": "入出庫管理機能は後ほど実装予定"}
