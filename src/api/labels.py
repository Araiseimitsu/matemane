from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.orm import Session, joinedload
from typing import Optional
from pydantic import BaseModel, Field
from datetime import datetime
from io import BytesIO
from urllib.parse import quote
import qrcode
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A6
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont

from src.db import get_db
from src.db.models import Item, Lot, Material, Location

router = APIRouter()

# 日本語フォント登録
pdfmetrics.registerFont(UnicodeCIDFont('HeiseiKakuGo-W5'))

class LabelPrintRequest(BaseModel):
    lot_number: str = Field(..., description="LOT番号")
    copies: int = Field(default=1, ge=1, le=10, description="印刷部数")

class LotTagRequest(BaseModel):
    lot_id: int = Field(..., description="ロットID")
    copies: int = Field(default=1, ge=1, le=10, description="印刷部数")

@router.post("/print")
async def print_label(
    request: LabelPrintRequest,
    db: Session = Depends(get_db)
):
    """QRコード付きラベル印刷（PDF生成）"""

    # アイテム情報取得（LOT番号から検索）
    item = db.query(Item).join(Item.lot).options(
        joinedload(Item.lot).joinedload(Lot.material),
        joinedload(Item.location)
    ).filter(Lot.lot_number == request.lot_number).first()

    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="指定されたLOT番号のアイテムが見つかりません"
        )

    material = item.lot.material

    # 重量計算
    if material.shape.value == "round":
        radius_cm = (material.diameter_mm / 2) / 10
        length_cm = item.lot.length_mm / 10
        volume_cm3 = 3.14159 * (radius_cm ** 2) * length_cm
    elif material.shape.value == "hexagon":
        side_cm = (material.diameter_mm / 2) / 10
        length_cm = item.lot.length_mm / 10
        volume_cm3 = (3 * (3 ** 0.5) / 2) * (side_cm ** 2) * length_cm
    elif material.shape.value == "square":
        side_cm = material.diameter_mm / 10
        length_cm = item.lot.length_mm / 10
        volume_cm3 = (side_cm ** 2) * length_cm
    else:
        volume_cm3 = 0

    weight_per_piece_kg = (volume_cm3 * material.current_density) / 1000
    total_weight_kg = weight_per_piece_kg * item.current_quantity

    # PDFバッファ作成
    buffer = BytesIO()

    # A6ラベル作成
    create_a6_label(buffer, item, material, weight_per_piece_kg, total_weight_kg, request.copies)

    buffer.seek(0)

    # ファイル名をURLエンコード（日本語対応）
    filename = f"label_{request.lot_number}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    filename_encoded = quote(filename)

    # PDFレスポンス
    response = Response(
        content=buffer.getvalue(),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{filename_encoded}"
        }
    )

    return response

def create_qr_code(data: str, size_mm: int = 20) -> BytesIO:
    """QRコード生成（最小20mm角）"""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)

    qr_image = qr.make_image(fill_color="black", back_color="white")
    qr_buffer = BytesIO()
    qr_image.save(qr_buffer, format='PNG')
    qr_buffer.seek(0)

    return qr_buffer

def create_a6_label(buffer: BytesIO, item, material, weight_per_piece_kg: float, total_weight_kg: float, copies: int):
    """A6ラベル作成"""
    doc = SimpleDocTemplate(buffer, pagesize=A6, topMargin=5*mm, bottomMargin=5*mm, leftMargin=5*mm, rightMargin=5*mm)
    styles = getSampleStyleSheet()

    # 日本語対応スタイル
    jp_style = ParagraphStyle(
        'Japanese',
        parent=styles['Normal'],
        fontName='HeiseiKakuGo-W5',
        fontSize=8,
        leading=10
    )

    title_style = ParagraphStyle(
        'JapaneseTitle',
        parent=styles['Title'],
        fontName='HeiseiKakuGo-W5',
        fontSize=12,
        leading=14,
        alignment=1  # 中央揃え
    )

    for copy_num in range(copies):
        story = []

        # タイトル
        story.append(Paragraph("材料管理ラベル", title_style))
        story.append(Spacer(1, 5*mm))

        # QRコード
        qr_buffer = create_qr_code(item.lot.lot_number, 18)
        qr_image = Image(qr_buffer, width=18*mm, height=18*mm)

        # QRコードとタイトルを並べて配置
        header_table = Table([[qr_image, "LOT: " + item.lot.lot_number[:15] + ("..." if len(item.lot.lot_number) > 15 else "")]],
                           colWidths=[20*mm, 70*mm])
        header_table.setStyle(TableStyle([
            ('FONT', (1, 0), (1, 0), 'HeiseiKakuGo-W5'),
            ('FONTSIZE', (1, 0), (1, 0), 8),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (1, 0), (1, 0), 'LEFT'),
        ]))

        story.append(header_table)
        story.append(Spacer(1, 5*mm))

        # メイン情報テーブル（A6用に最適化）
        data = [
            ["LOT", item.lot.lot_number],
            ["材質", material.display_name],
            ["形状", get_shape_name(material.shape.value)],
            ["寸法", f"φ{material.diameter_mm}mm" if material.shape.value == "round" else f"{material.diameter_mm}mm角"],
            ["長さ", f"{item.lot.length_mm}mm"],
            ["本数", f"{item.current_quantity}本"],
            ["単重", f"{weight_per_piece_kg:.3f}kg"],
            ["総重量", f"{total_weight_kg:.3f}kg"],
            ["置き場", item.location.name if item.location else "-"],
            ["仕入先", item.lot.supplier or "-"],
            ["入荷日", item.lot.received_date.strftime("%Y/%m/%d") if item.lot.received_date else "-"],
            ["印刷日", datetime.now().strftime("%m/%d %H:%M")]
        ]

        table = Table(data, colWidths=[20*mm, 70*mm])
        table.setStyle(TableStyle([
            ('FONT', (0, 0), (-1, -1), 'HeiseiKakuGo-W5'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
        ]))

        story.append(table)

        if copy_num < copies - 1:
            story.append(Spacer(1, 10*mm))

    doc.build(story)

def get_shape_name(shape_value: str) -> str:
    """形状値を日本語名に変換"""
    shape_map = {
        "round": "丸棒",
        "hexagon": "六角棒",
        "square": "角棒"
    }
    return shape_map.get(shape_value, shape_value)

@router.get("/preview/{lot_number}")
async def preview_label(lot_number: str, db: Session = Depends(get_db)):
    """ラベルプレビュー情報取得"""
    item = db.query(Item).join(Item.lot).options(
        joinedload(Item.lot).joinedload(Lot.material),
        joinedload(Item.location)
    ).filter(Lot.lot_number == lot_number).first()

    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="指定されたLOT番号のアイテムが見つかりません"
        )

    material = item.lot.material

    # 重量計算
    if material.shape.value == "round":
        radius_cm = (material.diameter_mm / 2) / 10
        length_cm = item.lot.length_mm / 10
        volume_cm3 = 3.14159 * (radius_cm ** 2) * length_cm
    elif material.shape.value == "hexagon":
        side_cm = (material.diameter_mm / 2) / 10
        length_cm = item.lot.length_mm / 10
        volume_cm3 = (3 * (3 ** 0.5) / 2) * (side_cm ** 2) * length_cm
    elif material.shape.value == "square":
        side_cm = material.diameter_mm / 10
        length_cm = item.lot.length_mm / 10
        volume_cm3 = (side_cm ** 2) * length_cm
    else:
        volume_cm3 = 0

    weight_per_piece_kg = (volume_cm3 * material.current_density) / 1000
    total_weight_kg = weight_per_piece_kg * item.current_quantity

    return {
        "item": {
            "lot_number": item.lot.lot_number,
            "current_quantity": item.current_quantity,
            "created_at": item.created_at
        },
        "material": {
            "display_name": material.display_name,
            "shape": material.shape.value,
            "shape_name": get_shape_name(material.shape.value),
            "diameter_mm": material.diameter_mm,
            "density": material.current_density
        },
        "lot": {
            "id": item.lot.id,
            "lot_number": item.lot.lot_number,
            "length_mm": item.lot.length_mm,
            "supplier": item.lot.supplier,
            "received_date": item.lot.received_date
        },
        "location": {
            "name": item.location.name if item.location else "未配置"
        },
        "calculated": {
            "weight_per_piece_kg": round(weight_per_piece_kg, 3),
            "total_weight_kg": round(total_weight_kg, 3),
            "volume_per_piece_cm3": round(volume_cm3, 3)
        }
    }

@router.post("/lot-tag")
async def print_lot_tag(
    request: LotTagRequest,
    db: Session = Depends(get_db)
):
    """ロット現品票印刷（PDF生成）"""

    # ロット情報取得
    lot = db.query(Lot).options(
        joinedload(Lot.material)
    ).filter(Lot.id == request.lot_id).first()

    if not lot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="指定されたロットが見つかりません"
        )

    material = lot.material

    # PDFバッファ作成
    buffer = BytesIO()

    # A6現品票作成
    create_a6_lot_tag(buffer, lot, material, request.copies)

    buffer.seek(0)

    # ファイル名をURLエンコード（日本語対応）
    filename = f"lot_tag_{lot.lot_number}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    filename_encoded = quote(filename)

    # PDFレスポンス
    response = Response(
        content=buffer.getvalue(),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{filename_encoded}"
        }
    )

    return response

def create_a6_lot_tag(buffer: BytesIO, lot, material, copies: int):
    """A6現品票作成"""
    doc = SimpleDocTemplate(buffer, pagesize=A6, topMargin=5*mm, bottomMargin=5*mm, leftMargin=5*mm, rightMargin=5*mm)
    styles = getSampleStyleSheet()

    # 日本語対応スタイル
    jp_style = ParagraphStyle(
        'Japanese',
        parent=styles['Normal'],
        fontName='HeiseiKakuGo-W5',
        fontSize=8,
        leading=10
    )

    title_style = ParagraphStyle(
        'JapaneseTitle',
        parent=styles['Title'],
        fontName='HeiseiKakuGo-W5',
        fontSize=14,
        leading=16,
        alignment=1  # 中央揃え
    )

    for copy_num in range(copies):
        story = []

        # タイトル
        story.append(Paragraph("現品票", title_style))
        story.append(Spacer(1, 8*mm))

        # QRコード（ロット番号をエンコード）
        qr_buffer = create_qr_code(lot.lot_number, 20)
        qr_image = Image(qr_buffer, width=20*mm, height=20*mm)

        # QRコードとタイトルを並べて配置
        header_table = Table([[qr_image, "LOT: " + lot.lot_number[:15] + ("..." if len(lot.lot_number) > 15 else "")]],
                           colWidths=[22*mm, 68*mm])
        header_table.setStyle(TableStyle([
            ('FONT', (1, 0), (1, 0), 'HeiseiKakuGo-W5'),
            ('FONTSIZE', (1, 0), (1, 0), 8),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (1, 0), (1, 0), 'LEFT'),
        ]))

        story.append(header_table)
        story.append(Spacer(1, 5*mm))

        # 重量計算（1本あたり）
        if material.shape.value == "round":
            radius_cm = (material.diameter_mm / 2) / 10
            length_cm = lot.length_mm / 10
            volume_cm3 = 3.14159 * (radius_cm ** 2) * length_cm
        elif material.shape.value == "hexagon":
            side_cm = (material.diameter_mm / 2) / 10
            length_cm = lot.length_mm / 10
            volume_cm3 = (3 * (3 ** 0.5) / 2) * (side_cm ** 2) * length_cm
        elif material.shape.value == "square":
            side_cm = material.diameter_mm / 10
            length_cm = lot.length_mm / 10
            volume_cm3 = (side_cm ** 2) * length_cm
        else:
            volume_cm3 = 0

        weight_per_piece_kg = (volume_cm3 * material.current_density) / 1000

        # メイン情報テーブル（A6用に最適化）
        data = [
            ["ロット番号", lot.lot_number],
            ["材質", material.display_name],
            ["形状・寸法", f"{get_shape_name(material.shape.value)} φ{material.diameter_mm}mm" if material.shape.value == "round" else f"{get_shape_name(material.shape.value)} {material.diameter_mm}mm"],
            ["長さ", f"{lot.length_mm}mm"],
            ["数量", f"{(lot.initial_quantity or 0)}本"],
            ["重量(初期)", f"{lot.initial_weight_kg:.3f}kg" if lot.initial_weight_kg else "-"],
            ["単重", f"{weight_per_piece_kg:.3f}kg/本"],
            ["仕入先", lot.supplier or "-"],
            ["入荷日", lot.received_date.strftime("%Y/%m/%d") if lot.received_date else "-"],
            ["作成日", lot.created_at.strftime("%m/%d %H:%M")],
            ["印刷日", datetime.now().strftime("%m/%d %H:%M")]
        ]

        table = Table(data, colWidths=[25*mm, 65*mm])
        table.setStyle(TableStyle([
            ('FONT', (0, 0), (-1, -1), 'HeiseiKakuGo-W5'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
            ('ROWBACKGROUNDS', (0, 0), (-1, -1), [colors.white, colors.lightgrey])
        ]))

        story.append(table)
        story.append(Spacer(1, 5*mm))

        # 備考欄
        if lot.notes:
            story.append(Paragraph("備考:", jp_style))
            story.append(Paragraph(lot.notes, jp_style))

        if copy_num < copies - 1:
            story.append(Spacer(1, 10*mm))

    doc.build(story)

@router.get("/lot-preview/{lot_id}")
async def preview_lot_tag(lot_id: int, db: Session = Depends(get_db)):
    """現品票プレビュー情報取得"""
    lot = db.query(Lot).options(
        joinedload(Lot.material)
    ).filter(Lot.id == lot_id).first()

    if not lot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="指定されたロットが見つかりません"
        )

    material = lot.material

    # 重量計算
    if material.shape.value == "round":
        radius_cm = (material.diameter_mm / 2) / 10
        length_cm = lot.length_mm / 10
        volume_cm3 = 3.14159 * (radius_cm ** 2) * length_cm
    elif material.shape.value == "hexagon":
        side_cm = (material.diameter_mm / 2) / 10
        length_cm = lot.length_mm / 10
        volume_cm3 = (3 * (3 ** 0.5) / 2) * (side_cm ** 2) * length_cm
    elif material.shape.value == "square":
        side_cm = material.diameter_mm / 10
        length_cm = lot.length_mm / 10
        volume_cm3 = (side_cm ** 2) * length_cm
    else:
        volume_cm3 = 0

    weight_per_piece_kg = (volume_cm3 * material.current_density) / 1000

    return {
        "lot": {
            "id": lot.id,
            "lot_number": lot.lot_number,
            "length_mm": lot.length_mm,
            "supplier": lot.supplier,
            "received_date": lot.received_date,
            "notes": lot.notes,
            "created_at": lot.created_at,
            "initial_quantity": lot.initial_quantity,
            "initial_weight_kg": lot.initial_weight_kg
        },
        "material": {
            "display_name": material.display_name,
            "shape": material.shape.value,
            "shape_name": get_shape_name(material.shape.value),
            "diameter_mm": material.diameter_mm,
            "density": material.current_density
        },
        "calculated": {
            "weight_per_piece_kg": round(weight_per_piece_kg, 3),
            "volume_per_piece_cm3": round(volume_cm3, 3)
        }
    }
