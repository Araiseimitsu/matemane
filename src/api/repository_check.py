"""
リポジトリ（ファイル共有）アクセス確認API

このモジュールは、アプリケーションが必要とするネットワーク共有や
ローカルファイルパスへのアクセス可能性を確認する機能を提供します。
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Optional
from pathlib import Path
import os
import logging

from src.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()


class RepositoryStatus(BaseModel):
    """リポジトリの状態情報"""
    name: str
    path: str
    accessible: bool
    exists: bool
    readable: bool
    writable: bool
    error_message: Optional[str] = None


class RepositoryCheckResponse(BaseModel):
    """リポジトリチェックのレスポンス"""
    repositories: List[RepositoryStatus]
    total_count: int
    accessible_count: int
    inaccessible_count: int


def check_path_accessibility(path_str: str) -> Dict[str, any]:
    """
    指定されたパスのアクセス可能性をチェック
    
    Args:
        path_str: チェックするファイルまたはディレクトリのパス
        
    Returns:
        アクセス情報の辞書
    """
    result = {
        "accessible": False,
        "exists": False,
        "readable": False,
        "writable": False,
        "error_message": None
    }
    
    try:
        path = Path(path_str)
        
        # 存在チェック
        result["exists"] = path.exists()
        
        if result["exists"]:
            # 読み取り可能かチェック
            try:
                result["readable"] = os.access(str(path), os.R_OK)
            except Exception as e:
                logger.warning(f"読み取り権限チェック失敗 {path}: {e}")
                result["readable"] = False
            
            # 書き込み可能かチェック
            try:
                if path.is_file():
                    # ファイルの場合は親ディレクトリの書き込み権限をチェック
                    result["writable"] = os.access(str(path.parent), os.W_OK)
                else:
                    result["writable"] = os.access(str(path), os.W_OK)
            except Exception as e:
                logger.warning(f"書き込み権限チェック失敗 {path}: {e}")
                result["writable"] = False
            
            # アクセス可能と判定（存在して読み取り可能）
            result["accessible"] = result["readable"]
        else:
            result["error_message"] = "パスが存在しません"
            
    except PermissionError as e:
        result["error_message"] = f"アクセス権限がありません: {str(e)}"
        logger.error(f"Permission error for {path_str}: {e}")
    except OSError as e:
        result["error_message"] = f"OSエラー: {str(e)}"
        logger.error(f"OS error for {path_str}: {e}")
    except Exception as e:
        result["error_message"] = f"予期しないエラー: {str(e)}"
        logger.error(f"Unexpected error for {path_str}: {e}")
    
    return result


@router.get("/api/repositories/check", response_model=RepositoryCheckResponse)
async def check_repositories():
    """
    設定されているすべてのリポジトリ（ファイルパス）のアクセス可能性をチェック
    
    Returns:
        RepositoryCheckResponse: リポジトリの状態情報
    """
    logger.info("リポジトリアクセスチェックを開始")
    
    # チェック対象のリポジトリを定義
    repositories_to_check = [
        {
            "name": "生産スケジュール (セット予定表)",
            "path": settings.production_schedule_path
        },
        {
            "name": "材料管理Excel (材料管理.xlsx)",
            "path": r"\\192.168.1.200\共有\生産管理課\材料管理.xlsx"
        },
    ]
    
    # 各リポジトリの状態をチェック
    results = []
    for repo in repositories_to_check:
        check_result = check_path_accessibility(repo["path"])
        
        status = RepositoryStatus(
            name=repo["name"],
            path=repo["path"],
            accessible=check_result["accessible"],
            exists=check_result["exists"],
            readable=check_result["readable"],
            writable=check_result["writable"],
            error_message=check_result["error_message"]
        )
        results.append(status)
        
        logger.info(
            f"リポジトリ '{repo['name']}': "
            f"アクセス可能={status.accessible}, "
            f"存在={status.exists}, "
            f"読取={status.readable}, "
            f"書込={status.writable}"
        )
    
    # 集計
    accessible_count = sum(1 for r in results if r.accessible)
    inaccessible_count = len(results) - accessible_count
    
    response = RepositoryCheckResponse(
        repositories=results,
        total_count=len(results),
        accessible_count=accessible_count,
        inaccessible_count=inaccessible_count
    )
    
    logger.info(
        f"リポジトリチェック完了: "
        f"総数={response.total_count}, "
        f"アクセス可能={response.accessible_count}, "
        f"アクセス不可={response.inaccessible_count}"
    )
    
    return response
