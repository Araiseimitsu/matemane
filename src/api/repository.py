"""
Repository information API endpoints
"""
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
import subprocess
import os
import sys

router = APIRouter()

# Repository metadata constants
REPOSITORY_NAME = "matemane"
REPOSITORY_DESCRIPTION = "旋盤用棒材の在庫管理システム（本数・重量のハイブリッド管理）"
REPOSITORY_VERSION = "1.0.0"


class RepositoryInfo(BaseModel):
    """Repository information model"""
    name: str
    description: str
    version: str
    git_remote: Optional[str] = None
    git_branch: Optional[str] = None
    git_commit: Optional[str] = None
    python_version: str


@router.get("/info", response_model=RepositoryInfo)
async def get_repository_info():
    """
    Get repository and system information
    
    Returns basic information about the repository including:
    - Repository name and description
    - Current version
    - Git information (remote, branch, commit)
    - Python version
    """
    # Get git information if available
    git_remote = None
    git_branch = None
    git_commit = None
    
    # Verify we're in a git repository before running git commands
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            capture_output=True,
            timeout=2,
            cwd=os.getcwd()
        )
        is_git_repo = result.returncode == 0
    except Exception:
        is_git_repo = False
    
    if is_git_repo:
        try:
            # Get git remote URL
            result = subprocess.run(
                ["git", "config", "--get", "remote.origin.url"],
                capture_output=True,
                text=True,
                timeout=2,
                cwd=os.getcwd()
            )
            if result.returncode == 0:
                git_remote = result.stdout.strip()
        except Exception:
            pass
        
        try:
            # Get current branch
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True,
                text=True,
                timeout=2,
                cwd=os.getcwd()
            )
            if result.returncode == 0:
                git_branch = result.stdout.strip()
        except Exception:
            pass
        
        try:
            # Get current commit hash
            result = subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"],
                capture_output=True,
                text=True,
                timeout=2,
                cwd=os.getcwd()
            )
            if result.returncode == 0:
                git_commit = result.stdout.strip()
        except Exception:
            pass
    
    # Get Python version
    python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    
    return RepositoryInfo(
        name=REPOSITORY_NAME,
        description=REPOSITORY_DESCRIPTION,
        version=REPOSITORY_VERSION,
        git_remote=git_remote,
        git_branch=git_branch,
        git_commit=git_commit,
        python_version=python_version
    )
