from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional
from sqlalchemy.orm import Session, joinedload

from src.db import get_db
from src.db.models import MaterialGroup, MaterialGroupMember, Material

router = APIRouter(prefix="/api/material-groups", tags=["material-groups"])


# ==========================
# Pydantic Schemas
# ==========================

class MaterialGroupBase(BaseModel):
    group_name: str = Field(..., max_length=200, description="グループ名")
    description: Optional[str] = Field(None, description="説明")
    is_active: bool = Field(True, description="有効フラグ")


class MaterialGroupCreate(MaterialGroupBase):
    pass


class MaterialGroupUpdate(BaseModel):
    group_name: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = None
    is_active: Optional[bool] = None


class MaterialGroupResponse(MaterialGroupBase):
    model_config = ConfigDict(from_attributes=True)
    id: int


class GroupMemberAdd(BaseModel):
    material_id: int = Field(..., description="追加する材料ID")


class GroupMemberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    group_id: int
    material_id: int


# ==========================
# Endpoints - Groups
# ==========================

@router.get("/", response_model=List[MaterialGroupResponse])
async def list_groups(
    is_active: Optional[bool] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    query = db.query(MaterialGroup)
    if is_active is not None:
        query = query.filter(MaterialGroup.is_active == is_active)
    groups = query.offset(skip).limit(limit).all()
    return groups


@router.post("/", response_model=MaterialGroupResponse, status_code=status.HTTP_201_CREATED)
async def create_group(payload: MaterialGroupCreate, db: Session = Depends(get_db)):
    # 同名グループ重複チェック（任意）
    existing = db.query(MaterialGroup).filter(MaterialGroup.group_name == payload.group_name).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="同名のグループが既に存在します")

    group = MaterialGroup(**payload.model_dump())
    db.add(group)
    db.commit()
    db.refresh(group)
    return group


@router.get("/{group_id}", response_model=MaterialGroupResponse)
async def get_group(group_id: int, db: Session = Depends(get_db)):
    group = db.query(MaterialGroup).filter(MaterialGroup.id == group_id).first()
    if not group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="グループが見つかりません")
    return group


@router.patch("/{group_id}", response_model=MaterialGroupResponse)
async def update_group(group_id: int, payload: MaterialGroupUpdate, db: Session = Depends(get_db)):
    group = db.query(MaterialGroup).filter(MaterialGroup.id == group_id).first()
    if not group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="グループが見つかりません")

    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(group, k, v)
    db.commit()
    db.refresh(group)
    return group


@router.delete("/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_group(group_id: int, db: Session = Depends(get_db)):
    group = db.query(MaterialGroup).filter(MaterialGroup.id == group_id).first()
    if not group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="グループが見つかりません")
    db.delete(group)
    db.commit()
    return None


# ==========================
# Endpoints - Group Members
# ==========================

@router.get("/{group_id}/members", response_model=List[GroupMemberResponse])
async def list_group_members(group_id: int, db: Session = Depends(get_db)):
    group = db.query(MaterialGroup).filter(MaterialGroup.id == group_id).first()
    if not group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="グループが見つかりません")

    members = db.query(MaterialGroupMember).filter(MaterialGroupMember.group_id == group_id).all()
    return members


@router.post("/{group_id}/members", response_model=GroupMemberResponse, status_code=status.HTTP_201_CREATED)
async def add_group_member(group_id: int, payload: GroupMemberAdd, db: Session = Depends(get_db)):
    group = db.query(MaterialGroup).filter(MaterialGroup.id == group_id).first()
    if not group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="グループが見つかりません")

    material = db.query(Material).filter(Material.id == payload.material_id).first()
    if not material:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="材料が見つかりません")

    # 既存所属チェック
    existing = db.query(MaterialGroupMember).filter(
        MaterialGroupMember.group_id == group_id,
        MaterialGroupMember.material_id == payload.material_id
    ).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="この材料は既にグループに所属しています")

    membership = MaterialGroupMember(group_id=group_id, material_id=payload.material_id)
    db.add(membership)
    db.commit()
    db.refresh(membership)
    return membership


@router.delete("/{group_id}/members/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_group_member(group_id: int, member_id: int, db: Session = Depends(get_db)):
    """グループ所属の削除"""
    membership = db.query(MaterialGroupMember).filter(
        MaterialGroupMember.id == member_id,
        MaterialGroupMember.group_id == group_id
    ).first()
    if not membership:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="所属が見つかりません")
    db.delete(membership)
    db.commit()
    return None


@router.delete("/{group_id}/members/{material_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_group_member(group_id: int, material_id: int, db: Session = Depends(get_db)):
    membership = db.query(MaterialGroupMember).filter(
        MaterialGroupMember.group_id == group_id,
        MaterialGroupMember.material_id == material_id
    ).first()
    if not membership:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="所属が見つかりません")

    db.delete(membership)
    db.commit()
    return None