"""生産中スケジュールAPI

在庫切れ予測を含む拡張を追加します。
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from pathlib import Path
from typing import List, Optional

import pandas as pd
from fastapi import APIRouter, HTTPException, Depends
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel

from src.config import settings
from sqlalchemy.orm import Session
from sqlalchemy import func
from src.db import get_db
from src.db.models import Item, Lot, Material

from src.api.material_management import _load_material_plan, MaterialUsageSummary

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/production-schedule", tags=["生産中一覧"])


class ProductionItem(BaseModel):
    row_number: int
    set_plan_date: Optional[str]
    machine_no: Optional[str]
    item_code: Optional[str]
    product_name: Optional[str]
    quantity: Optional[str]
    material: Optional[str]
    next_process: Optional[str]
    process_plan_date: Optional[str]
    process_end_date: Optional[str]
    latest_due_date: Optional[str]
    remarks: Optional[str]


COLUMN_MAP = {
    "set_plan_date": "セット予定日",
    "machine_no": "機械NO",
    "item_code": "品番",
    "product_name": "製品名",
    "quantity": "数量",
    "material": "材質＆材料径",
    "next_process": "次工程",
    "process_plan_date": "加工　　　　予定日",
    "process_end_date": "加工終了日",
    "latest_due_date": "最新納期",
    "remarks": "備　　　　考",
}

USE_COLUMNS = list(dict.fromkeys(COLUMN_MAP.values()))

DATE_FIELDS = {
    "set_plan_date",
    "latest_due_date",
    "process_end_date",
}


def _format_date(value) -> Optional[str]:
    if pd.isna(value):
        return None
    if isinstance(value, (datetime, date)):
        return value.strftime("%Y-%m-%d")
    try:
        parsed = pd.to_datetime(value)
    except Exception:
        return _format_text(value)
    if pd.isna(parsed):
        return None
    return parsed.strftime("%Y-%m-%d")


def _format_text(value) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, float):
        if pd.isna(value):
            return None
        if float(value).is_integer():
            return str(int(value))
        return f"{value:.3f}".rstrip("0").rstrip(".")
    text = str(value).strip()
    if not text or text.lower() == "nan":
        return None
    return text


def _should_skip_row(row: pd.Series) -> bool:
    core_fields = [row.get("品番"), row.get("製品名"), row.get("数量")]
    return all(pd.isna(field) or str(field).strip() == "" for field in core_fields)


def _load_production_schedule() -> List[ProductionItem]:
    excel_path = Path(settings.production_schedule_path)
    if not excel_path.exists():
        raise FileNotFoundError(f"指定のExcelファイルが存在しません: {excel_path}")

    try:
        dataframe = pd.read_excel(
            excel_path,
            sheet_name="生産中",
            dtype=object,
            usecols=USE_COLUMNS,
        )
    except Exception as exc:  # pragma: no cover - エラー内容を利用者に伝達
        logger.exception("生産中シートの読み込みに失敗しました")
        raise RuntimeError(f"Excel読み込みエラー: {exc}") from exc

    items: List[ProductionItem] = []

    for index, row in dataframe.iterrows():
        if _should_skip_row(row):
            continue

        payload = {"row_number": int(index) + 1}

        for field, column_name in COLUMN_MAP.items():
            raw_value = row.get(column_name)
            if field in DATE_FIELDS:
                payload[field] = _format_date(raw_value)
            else:
                payload[field] = _format_text(raw_value)

        items.append(ProductionItem(**payload))

    return items


@router.get("/", response_model=List[ProductionItem])
async def list_production_schedule() -> List[ProductionItem]:
    """加工中一覧の表示用データをそのまま返す（Excel準拠）。"""
    try:
        return await run_in_threadpool(_load_production_schedule)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ============================
# 在庫切れ予測用モデル/ヘルパー
# ============================

class DailyUsage(BaseModel):
    usage_date: Optional[str]
    total_bars: int


class StockoutForecast(BaseModel):
    material_spec: str
    current_stock_bars: int
    projected_stockout_date: Optional[str]
    days_until_stockout: Optional[int]
    daily_usage: List[DailyUsage]
    material_master_found: bool
    material_name: Optional[str]
    diameter_mm: Optional[float]


def _get_current_stock_bars(db: Session, display_name: Optional[str]) -> int:
    """Material.display_name（Excel仕様文字列）一致で在庫本数合計を返す"""
    if not display_name:
        return 0

    materials = (
        db.query(Material)
        .filter(Material.display_name == display_name, Material.is_active == True)
        .all()
    )

    if not materials:
        return 0

    total_stock = 0
    for m in materials:
        stock = (
            db.query(func.coalesce(func.sum(Item.current_quantity), 0))
            .join(Lot, Item.lot_id == Lot.id)
            .filter(Lot.material_id == m.id, Item.is_active == True)
            .scalar()
        )
        total_stock += int(stock or 0)

    return total_stock


def _calculate_stockout_forecast(db: Session) -> List[StockoutForecast]:
    """在庫ページに表示される（登録済みで在庫のある）材料を対象に予測を計算"""
    # 既存の材料使用量サマリー（Excel: 生産中）を読み込み
    usage_summaries: List[MaterialUsageSummary] = _load_material_plan()

    # Excelの仕様文字列（material_spec）ごとに日別使用本数を集約
    usage_by_spec: dict[str, List[DailyUsage]] = {}
    for s in usage_summaries:
        # Excel側で使用日が未入力(None)の行は「今日」として扱う
        usage_date_str = s.usage_date or date.today().strftime("%Y-%m-%d")
        lst = usage_by_spec.setdefault(s.material_spec, [])
        lst.append(DailyUsage(usage_date=usage_date_str, total_bars=int(s.total_bars)))

    # DB側の材料（登録済み・display_nameあり）を取得し、在庫があるものに限定
    materials = db.query(Material).filter(
        Material.is_active == True,
        Material.display_name.isnot(None),
    ).all()

    forecasts: List[StockoutForecast] = []
    today = date.today()

    for m in materials:
        spec = m.display_name
        current_stock = _get_current_stock_bars(db, spec)
        if current_stock <= 0:
            # 在庫ゼロは予測対象外（インベントリページ準拠）
            continue

        daily = usage_by_spec.get(spec, [])
        if not daily:
            forecasts.append(
                StockoutForecast(
                    material_spec=spec,
                    current_stock_bars=current_stock,
                    projected_stockout_date=None,
                    days_until_stockout=None,
                    daily_usage=[],
                    material_master_found=True,
                    material_name=m.display_name,
                    diameter_mm=m.diameter_mm,
                )
            )
            continue

        daily_sorted = sorted(daily, key=lambda x: (x.usage_date or ""))
        cumulative = 0
        projected_date: Optional[str] = None
        for d in daily_sorted:
            cumulative += d.total_bars
            if cumulative >= current_stock and projected_date is None:
                projected_date = d.usage_date
                break

        days_until: Optional[int] = None
        if projected_date:
            try:
                dt = datetime.strptime(projected_date, "%Y-%m-%d").date()
                days_until = (dt - today).days
            except Exception:
                days_until = None

        forecasts.append(
            StockoutForecast(
                material_spec=spec,
                current_stock_bars=current_stock,
                projected_stockout_date=projected_date,
                days_until_stockout=days_until,
                daily_usage=daily_sorted,
                material_master_found=True,
                material_name=m.display_name,
                diameter_mm=m.diameter_mm,
            )
        )

    forecasts.sort(key=lambda f: (f.days_until_stockout is None, f.days_until_stockout or 10**9))
    return forecasts


@router.get("/stockout-forecast", response_model=List[StockoutForecast])
async def stockout_forecast(db: Session = Depends(get_db)) -> List[StockoutForecast]:
    try:
        return _calculate_stockout_forecast(db)
    except Exception as exc:
        logger.exception("在庫切れ予測の計算に失敗しました")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
