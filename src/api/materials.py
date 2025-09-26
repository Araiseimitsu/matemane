from fastapi import APIRouter

router = APIRouter()

@router.get("/")
async def get_materials():
    """材料一覧取得"""
    return {"message": "材料管理機能は後ほど実装予定"}
