from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.security import HTTPBearer
import uvicorn
import logging

from src.config import settings
from src.db import create_tables, SessionLocal
from src.db.models import Location
from src.api import auth, materials, inventory, movements, labels, density_presets, purchase_orders, order_utils, excel_viewer, production_schedule, material_management, material_groups, inspections

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
    allowed_hosts=["*"] if settings.debug else settings.allowed_hosts
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
app.include_router(density_presets.router, prefix="/api/density-presets", tags=["比重プリセット管理"])
app.include_router(purchase_orders.router, prefix="/api/purchase-orders", tags=["発注管理"])
app.include_router(order_utils.router, prefix="/api/order-utils", tags=["発注ユーティリティ"])
app.include_router(excel_viewer.router, tags=["Excelビューア"])
app.include_router(production_schedule.router, tags=["生産中一覧"])
app.include_router(material_management.router, tags=["材料管理"])
app.include_router(material_groups.router, tags=["材料グループ"])
app.include_router(inspections.router, tags=["検品"])

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

    # 置き場（1〜300）の初期化（存在しないIDのみ作成）
    try:
        with SessionLocal() as db:
            existing_ids = {row[0] for row in db.query(Location.id).all()}
            created = 0
            for i in range(1, 301):
                if i not in existing_ids:
                    db.add(Location(id=i, name=str(i), description=None, is_active=True))
                    created += 1
            if created:
                db.commit()
                logger.info(f"置き場を初期化しました: 新規 {created} 件")
            else:
                logger.info("置き場は既に初期化済みです")
    except Exception as e:
        logger.error(f"置き場初期化エラー: {e}")

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

@app.get("/purchase-orders")
async def purchase_orders_page(request: Request):
    """発注管理画面"""
    return templates.TemplateResponse("purchase_orders.html", {"request": request})

@app.get("/receiving")
async def receiving_page(request: Request):
    """入庫確認画面"""
    return templates.TemplateResponse("receiving.html", {"request": request})


@app.get("/production-schedule")
async def production_schedule_page(request: Request):
    """生産中一覧ページ"""
    return templates.TemplateResponse("production_schedule.html", {"request": request})


@app.get("/excel-viewer")
async def excel_viewer_page(request: Request):
    """Excel在庫照合ビューア画面"""
    return templates.TemplateResponse("excel_viewer.html", {"request": request})

@app.get("/settings")
async def settings_page(request: Request):
    """設定ページ"""
    return templates.TemplateResponse("settings.html", {"request": request})

# 削除: 旧材料グループ管理画面ルート（在庫ページへ統合済み）

@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    """404エラーハンドラー"""
    logger.warning("未検出パスにアクセスされました: %s", request.url.path)

    if request.url.path.startswith("/api/"):
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=404,
            content={"detail": "指定されたリソースが見つかりません"}
        )

    return templates.TemplateResponse(
        "error.html",
        {"request": request, "error_code": 404, "error_message": "ページが見つかりません"},
        status_code=404
    )

@app.exception_handler(500)
async def internal_error_handler(request: Request, exc):
    """500エラーハンドラー"""
    logger.error(f"内部サーバーエラー: {exc}")

    if request.url.path.startswith("/api/"):
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=500,
            content={"detail": "内部サーバーエラーが発生しました。ログを確認してください。"}
        )

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
