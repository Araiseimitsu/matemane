from fastapi import APIRouter

router = APIRouter()

@router.post("/print")
async def print_label():
    """ラベル印刷"""
    return {"message": "ラベル印刷機能は後ほど実装予定"}
