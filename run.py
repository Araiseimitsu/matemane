#!/usr/bin/env python3
"""
材料管理システム (matemane) 起動スクリプト

使用方法:
    python run.py
"""

import uvicorn
import sys
import os
from dotenv import load_dotenv

# .env を読み込み
load_dotenv()

# プロジェクトルートをPythonパスに追加
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

if __name__ == "__main__":
    # SSL 証明書設定（環境変数から読み込み）
    ssl_certfile = os.getenv("SSL_CERTFILE")
    ssl_keyfile = os.getenv("SSL_KEYFILE")

    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
        ssl_certfile=ssl_certfile if ssl_certfile else None,
        ssl_keyfile=ssl_keyfile if ssl_keyfile else None,
    )