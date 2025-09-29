"""生産中スケジュールAPI"""

from __future__ import annotations

import logging
from datetime import date, datetime
from pathlib import Path
from typing import List, Optional

import pandas as pd
from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel

from src.config import settings

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
    try:
        return await run_in_threadpool(_load_production_schedule)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
