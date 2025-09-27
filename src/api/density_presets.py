from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime

from src.db import get_db
from src.db.models import DensityPreset

router = APIRouter()

# Pydantic スキーマ
class DensityPresetBase(BaseModel):
    name: str = Field(..., max_length=100, description="材質名（例：S45C）")
    density: float = Field(..., gt=0, description="比重（g/cm³）")
    description: Optional[str] = Field(None, description="説明")

class DensityPresetCreate(DensityPresetBase):
    pass

class DensityPresetUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=100, description="材質名")
    density: Optional[float] = Field(None, gt=0, description="比重（g/cm³）")
    description: Optional[str] = Field(None, description="説明")
    is_active: Optional[bool] = Field(None, description="有効フラグ")

class DensityPresetResponse(DensityPresetBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

# API エンドポイント
@router.get("/", response_model=List[DensityPresetResponse])
async def get_density_presets(
    skip: int = 0,
    limit: int = 100,
    is_active: Optional[bool] = True,
    db: Session = Depends(get_db)
):
    """比重プリセット一覧取得"""
    query = db.query(DensityPreset)
    
    if is_active is not None:
        query = query.filter(DensityPreset.is_active == is_active)
    
    return query.offset(skip).limit(limit).all()

@router.get("/{preset_id}", response_model=DensityPresetResponse)
async def get_density_preset(preset_id: int, db: Session = Depends(get_db)):
    """比重プリセット詳細取得"""
    preset = db.query(DensityPreset).filter(DensityPreset.id == preset_id).first()
    if not preset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="比重プリセットが見つかりません"
        )
    return preset

@router.post("/", response_model=DensityPresetResponse, status_code=status.HTTP_201_CREATED)
async def create_density_preset(preset: DensityPresetCreate, db: Session = Depends(get_db)):
    """比重プリセット作成"""
    # 同じ名前のプリセットが既に存在するかチェック
    existing_preset = db.query(DensityPreset).filter(
        DensityPreset.name == preset.name,
        DensityPreset.is_active == True
    ).first()
    
    if existing_preset:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="同じ名前の比重プリセットが既に存在します"
        )
    
    db_preset = DensityPreset(**preset.model_dump())
    db.add(db_preset)
    db.commit()
    db.refresh(db_preset)
    
    return db_preset

@router.put("/{preset_id}", response_model=DensityPresetResponse)
async def update_density_preset(
    preset_id: int,
    preset_update: DensityPresetUpdate,
    db: Session = Depends(get_db)
):
    """比重プリセット更新"""
    db_preset = db.query(DensityPreset).filter(DensityPreset.id == preset_id).first()
    if not db_preset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="比重プリセットが見つかりません"
        )
    
    # 名前の重複チェック（自分以外）
    if preset_update.name:
        existing_preset = db.query(DensityPreset).filter(
            DensityPreset.name == preset_update.name,
            DensityPreset.id != preset_id,
            DensityPreset.is_active == True
        ).first()
        
        if existing_preset:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="同じ名前の比重プリセットが既に存在します"
            )
    
    # 更新
    update_data = preset_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_preset, field, value)
    
    db.commit()
    db.refresh(db_preset)
    
    return db_preset

@router.delete("/{preset_id}")
async def delete_density_preset(preset_id: int, db: Session = Depends(get_db)):
    """比重プリセット削除（論理削除）"""
    db_preset = db.query(DensityPreset).filter(DensityPreset.id == preset_id).first()
    if not db_preset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="比重プリセットが見つかりません"
        )
    
    db_preset.is_active = False
    db.commit()
    
    return {"message": "比重プリセットを削除しました"}