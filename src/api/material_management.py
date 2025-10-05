
"""Material usage forecasting API for 生産中 spreadsheet."""

from __future__ import annotations

import logging
import math
import re
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd
from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel

from src.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/material-management", tags=["材料管理"])


class MaterialUsageDetail(BaseModel):
    row_number: int
    schedule_date: Optional[str]
    machine_no: Optional[str]
    item_code: Optional[str]
    product_name: Optional[str]
    quantity: Optional[float]
    take_count: Optional[float]
    daily_output: Optional[float]
    bars_per_day: Optional[float]
    bars_needed: Optional[int]
    required_bars: Optional[float]
    remarks: Optional[str]


class MaterialUsageSummary(BaseModel):
    material_spec: str
    usage_date: Optional[str]
    total_bars: int
    cumulative_bars: int
    total_quantity: float
    machines: List[MaterialUsageDetail]


COLUMN_MAP: Dict[str, Tuple[str, ...]] = {
    "schedule_date": ("セット予定日",),
    "machine_no": ("機械NO",),
    "item_code": ("品番",),
    "product_name": ("製品名",),
    "quantity": ("数量",),
    "material_spec": ("材質＆材料径",),
    "take_count": ("取り数",),
    "daily_output": ("前回日産", "前回   日産"),
    "required_bars": ("必要　　　本数",),
    "remarks": ("備　　　　考",),
}

USE_COLUMNS: List[str] = []
for aliases in COLUMN_MAP.values():
    for alias in aliases:
        if alias not in USE_COLUMNS:
            USE_COLUMNS.append(alias)


def _format_date(value) -> Optional[str]:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    if isinstance(value, (datetime, date)):
        return value.strftime("%Y-%m-%d")
    try:
        parsed = pd.to_datetime(value)
    except Exception:
        return None
    if pd.isna(parsed):
        return None
    return parsed.strftime("%Y-%m-%d")


def _to_float(value) -> Optional[float]:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(result):
        return None
    return result


def _sanitize_str(value, *, max_len: int = 60) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() == "nan":
        return None
    if len(text) > max_len:
        return text[: max_len - 1] + "..."
    return text


def natural_sort_key(value: Optional[str]) -> Tuple:
    if value is None:
        return ("",)
    return tuple(
        int(part) if part.isdigit() else part.lower()
        for part in re.split(r"(\d+)", value)
    )


def _get_row_value(row: pd.Series, field: str):
    aliases = COLUMN_MAP[field]
    for alias in aliases:
        if alias in row.index:
            return row.get(alias)
    return None


def _load_material_plan() -> List[MaterialUsageSummary]:
    excel_path = Path(settings.production_schedule_path)
    if not excel_path.exists():
        raise FileNotFoundError(f"指定のExcelファイルが存在しません: {excel_path}")

    try:
        # 一部列がExcelに存在しない場合でも読み込めるよう、usecolsは関数指定で存在列のみ選択
        dataframe = pd.read_excel(
            excel_path,
            sheet_name="生産中",
            dtype=object,
            usecols=lambda col: col in USE_COLUMNS,
        )
    except Exception as exc:  # pragma: no cover
        logger.exception("生産中シートの読み込みに失敗しました")
        raise RuntimeError(f"Excel読み込みエラー: {exc}") from exc

    per_material_dates: Dict[str, Dict[Optional[str], List[MaterialUsageDetail]]] = defaultdict(lambda: defaultdict(list))

    for index, row in dataframe.iterrows():
        material_spec_raw = _get_row_value(row, "material_spec")
        material_spec = _sanitize_str(material_spec_raw, max_len=120)
        if material_spec is None:
            continue

        schedule_date_raw = _get_row_value(row, "schedule_date")
        schedule_date = _format_date(schedule_date_raw)

        quantity = _to_float(_get_row_value(row, "quantity"))
        take_count = _to_float(_get_row_value(row, "take_count"))
        raw_daily_output = _get_row_value(row, "daily_output")

        daily_output = _to_float(raw_daily_output)
        if daily_output is None and isinstance(raw_daily_output, str):
            cleaned = raw_daily_output.replace("前回日産", "").replace("前回   日産", "").strip()
            daily_output = _to_float(cleaned)

        required_bars_raw = _to_float(_get_row_value(row, "required_bars"))

        bars_per_day: Optional[float] = None
        if daily_output and daily_output > 0 and take_count and take_count > 0:
            # U列(前回日産) / W列(取り数) をそのまま使用（小数対応）
            bars_per_day = float(daily_output) / float(take_count)

        bars_needed: Optional[int] = None
        if take_count and take_count > 0 and quantity and quantity > 0:
            bars_needed = int(math.ceil(quantity / take_count))
        if bars_needed is None and required_bars_raw is not None:
            bars_needed = int(math.ceil(required_bars_raw))

        detail = MaterialUsageDetail(
            row_number=index + 1,
            schedule_date=schedule_date,
            machine_no=_sanitize_str(_get_row_value(row, "machine_no")),
            item_code=_sanitize_str(_get_row_value(row, "item_code")),
            product_name=_sanitize_str(_get_row_value(row, "product_name"), max_len=80),
            quantity=quantity,
            take_count=take_count,
            daily_output=daily_output,
            bars_per_day=bars_per_day,
            bars_needed=bars_needed,
            required_bars=required_bars_raw,
            remarks=_sanitize_str(_get_row_value(row, "remarks"), max_len=120),
        )

        per_material_dates[material_spec][schedule_date].append(detail)

    summaries: List[MaterialUsageSummary] = []

    for material_spec, date_map in per_material_dates.items():
        cumulative = 0

        def sort_key(date_value: Optional[str]) -> Tuple[int, Optional[str]]:
            if date_value is None:
                return (1, None)
            return (0, date_value)

        for usage_date in sorted(date_map.keys(), key=sort_key):
            details = sorted(
                date_map[usage_date],
                key=lambda d: (
                    d.schedule_date or "",
                    natural_sort_key(d.machine_no),
                    d.item_code or "",
                    d.row_number,
                ),
            )

            # 1日の使用本数（U列:前回日産 / W列:取り数）を優先し、
            # 取得できない場合は従来の bars_needed を使用する
            total_bars_float = sum((d.bars_per_day if d.bars_per_day is not None else (d.bars_needed or 0)) for d in details)
            total_bars = int(math.ceil(total_bars_float))
            total_quantity = sum(d.quantity or 0 for d in details)
            cumulative += total_bars

            summaries.append(
                MaterialUsageSummary(
                    material_spec=material_spec,
                    usage_date=usage_date,
                    total_bars=total_bars,
                    cumulative_bars=cumulative,
                    total_quantity=total_quantity,
                    machines=details,
                )
            )

    summaries.sort(
        key=lambda s: (
            s.material_spec,
            0 if s.usage_date is not None else 1,
            s.usage_date or "",
        )
    )

    return summaries


@router.get("/usage", response_model=List[MaterialUsageSummary])
async def list_material_usage() -> List[MaterialUsageSummary]:
    try:
        return await run_in_threadpool(_load_material_plan)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
