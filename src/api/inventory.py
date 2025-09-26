from fastapi import APIRouter

router = APIRouter()

@router.get("/")
async def get_inventory():
    """在庫一覧取得"""
    return {"message": "在庫管理機能は後ほど実装予定"}
