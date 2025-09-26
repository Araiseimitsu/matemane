from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.security import HTTPBearer
import uvicorn
import logging

from src.config import settings
from src.db import create_tables
from src.api import auth, materials, inventory, movements, labels

# ログ設定
logging.basicConfig(
    level=logging.INFO if settings.debug else logging.WARNING,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# FastAPIアプリケーション初期化
app = FastAPI(
    title="材料管理システム (matemane)",
    description="旋盤用棒材の在庫管理システム",
    version="1.0.0",
    debug=settings.debug
)

# セキュリティミドルウェア
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["localhost", "127.0.0.1", "*.localhost"]
)

# 静的ファイルとテンプレート設定
app.mount("/static", StaticFiles(directory="src/static"), name="static")
templates = Jinja2Templates(directory="src/templates")

# セキュリティスキーム
security = HTTPBearer()

# APIルーター登録
app.include_router(auth.router, prefix="/api/auth", tags=["認証"])
app.include_router(materials.router, prefix="/api/materials", tags=["材料管理"])
app.include_router(inventory.router, prefix="/api/inventory", tags=["在庫管理"])
app.include_router(movements.router, prefix="/api/movements", tags=["入出庫管理"])
app.include_router(labels.router, prefix="/api/labels", tags=["ラベル印刷"])

@app.on_event("startup")
async def startup_event():
    """起動時処理"""
    logger.info("材料管理システムを起動中...")

    # データベーステーブル作成
    try:
        create_tables()
        logger.info("データベーステーブルの初期化が完了しました")
    except Exception as e:
        logger.error(f"データベース初期化エラー: {e}")
        raise

    logger.info("材料管理システムの起動が完了しました")

@app.on_event("shutdown")
async def shutdown_event():
    """終了時処理"""
    logger.info("材料管理システムを終了します")

@app.get("/")
async def root(request: Request):
    """ダッシュボード画面"""
    return templates.TemplateResponse("dashboard.html", {"request": request})

@app.get("/login")
async def login_page(request: Request):
    """ログイン画面"""
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/materials")
async def materials_page(request: Request):
    """材料管理画面"""
    return templates.TemplateResponse("materials.html", {"request": request})

@app.get("/inventory")
async def inventory_page(request: Request):
    """在庫管理画面"""
    return templates.TemplateResponse("inventory.html", {"request": request})

@app.get("/movements")
async def movements_page(request: Request):
    """入出庫管理画面"""
    return templates.TemplateResponse("movements.html", {"request": request})

@app.get("/scan")
async def scan_page(request: Request):
    """QRスキャン画面"""
    return templates.TemplateResponse("scan.html", {"request": request})

@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    """404エラーハンドラー"""
    return templates.TemplateResponse(
        "error.html",
        {"request": request, "error_code": 404, "error_message": "ページが見つかりません"}
    )

@app.exception_handler(500)
async def internal_error_handler(request: Request, exc):
    """500エラーハンドラー"""
    logger.error(f"内部サーバーエラー: {exc}")
    return templates.TemplateResponse(
        "error.html",
        {"request": request, "error_code": 500, "error_message": "内部サーバーエラーが発生しました"}
    )

if __name__ == "__main__":
    import sys
    import os
    # プロジェクトルートをPythonパスに追加
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, project_root)

    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
        log_level="info" if settings.debug else "warning"
    )