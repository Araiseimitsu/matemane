from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.orm import Session, joinedload
from typing import Optional
from pydantic import BaseModel, Field
from datetime import datetime
from io import BytesIO
import qrcode
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4, letter
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
    management_code: str = Field(..., description="管理コード（UUID）")
    label_type: str = Field(default="standard", description="ラベルタイプ: standard | small")
    copies: int = Field(default=1, ge=1, le=10, description="印刷部数")

class LotTagRequest(BaseModel):
    lot_id: int = Field(..., description="ロットID")
    label_type: str = Field(default="standard", description="ラベルタイプ: standard | small")
    copies: int = Field(default=1, ge=1, le=10, description="印刷部数")

@router.post("/print")
async def print_label(
    request: LabelPrintRequest,
    db: Session = Depends(get_db)
):
    """QRコード付きラベル印刷（PDF生成）"""

    # アイテム情報取得
    item = db.query(Item).options(
        joinedload(Item.lot).joinedload(Lot.material),
        joinedload(Item.location)
    ).filter(Item.management_code == request.management_code).first()

    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="指定された管理コードのアイテムが見つかりません"
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

    if request.label_type == "small":
        # 小型ラベル（50×30mm）
        create_small_label(buffer, item, material, weight_per_piece_kg, total_weight_kg, request.copies)
    else:
        # A4標準ラベル
        create_standard_label(buffer, item, material, weight_per_piece_kg, total_weight_kg, request.copies)

    buffer.seek(0)

    # PDFレスポンス
    response = Response(
        content=buffer.getvalue(),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=label_{request.management_code}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
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

def create_standard_label(buffer: BytesIO, item, material, weight_per_piece_kg: float, total_weight_kg: float, copies: int):
    """A4標準ラベル作成"""
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=10*mm, bottomMargin=10*mm)
    styles = getSampleStyleSheet()

    # 日本語対応スタイル
    jp_style = ParagraphStyle(
        'Japanese',
        parent=styles['Normal'],
        fontName='HeiseiKakuGo-W5',
        fontSize=12,
        leading=16
    )

    title_style = ParagraphStyle(
        'JapaneseTitle',
        parent=styles['Title'],
        fontName='HeiseiKakuGo-W5',
        fontSize=18,
        leading=22,
        alignment=1  # 中央揃え
    )

    for copy_num in range(copies):
        story = []

        # タイトル
        story.append(Paragraph("材料管理ラベル", title_style))
        story.append(Spacer(1, 10*mm))

        # QRコード
        qr_buffer = create_qr_code(item.management_code, 25)
        qr_image = Image(qr_buffer, width=25*mm, height=25*mm)

        # QRコードとタイトルを並べて配置
        header_table = Table([[qr_image, "管理コード: " + item.management_code[:25] + ("..." if len(item.management_code) > 25 else "")]],
                           colWidths=[30*mm, 130*mm])
        header_table.setStyle(TableStyle([
            ('FONT', (1, 0), (1, 0), 'HeiseiKakuGo-W5'),
            ('FONTSIZE', (1, 0), (1, 0), 10),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (1, 0), (1, 0), 'LEFT'),
        ]))

        story.append(header_table)
        story.append(Spacer(1, 10*mm))

        # メイン情報テーブル
        data = [
            ["管理コード", item.management_code],
            ["材質", material.name],
            ["形状", get_shape_name(material.shape.value)],
            ["寸法", f"φ{material.diameter_mm}mm" if material.shape.value == "round" else f"{material.diameter_mm}mm角"],
            ["長さ", f"{item.lot.length_mm}mm"],
            ["ロット番号", item.lot.lot_number],
            ["現在本数", f"{item.current_quantity}本"],
            ["単重", f"{weight_per_piece_kg:.3f}kg/本"],
            ["総重量", f"{total_weight_kg:.3f}kg"],
            ["置き場", item.location.name if item.location else "未配置"],
            ["仕入先", item.lot.supplier or "未登録"],
            ["入荷日", item.lot.received_date.strftime("%Y/%m/%d") if item.lot.received_date else "未登録"],
            ["印刷日時", datetime.now().strftime("%Y/%m/%d %H:%M")]
        ]

        table = Table(data, colWidths=[40*mm, 100*mm])
        table.setStyle(TableStyle([
            ('FONT', (0, 0), (-1, -1), 'HeiseiKakuGo-W5'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
        ]))

        story.append(table)

        if copy_num < copies - 1:
            story.append(Spacer(1, 20*mm))

    doc.build(story)

def create_small_label(buffer: BytesIO, item, material, weight_per_piece_kg: float, total_weight_kg: float, copies: int):
    """小型ラベル（50×30mm）作成"""
    page_width = 50 * mm
    page_height = 30 * mm

    c = canvas.Canvas(buffer, pagesize=(page_width, page_height))

    for copy_num in range(copies):
        if copy_num > 0:
            c.showPage()

        # QRコード（20mm角）
        qr_buffer = create_qr_code(item.management_code, 20)
        c.drawImage(qr_buffer, 2*mm, 8*mm, width=20*mm, height=20*mm)

        # テキスト情報（右側）
        c.setFont('HeiseiKakuGo-W5', 6)

        # 材質・形状
        c.drawString(24*mm, 25*mm, f"{material.name}")
        c.drawString(24*mm, 22*mm, f"{get_shape_name(material.shape.value)}")

        # 寸法・長さ
        if material.shape.value == "round":
            size_text = f"φ{material.diameter_mm}"
        else:
            size_text = f"{material.diameter_mm}□"
        c.drawString(24*mm, 19*mm, size_text)
        c.drawString(24*mm, 16*mm, f"L{item.lot.length_mm}")

        # 本数・重量
        c.drawString(24*mm, 13*mm, f"{item.current_quantity}本")
        c.drawString(24*mm, 10*mm, f"{total_weight_kg:.1f}kg")

        # 管理コード（下部）
        c.setFont('HeiseiKakuGo-W5', 4)
        code_short = item.management_code[:8] + "..."
        c.drawString(2*mm, 4*mm, code_short)

        # 印刷日
        c.drawString(2*mm, 1*mm, datetime.now().strftime("%m/%d"))

    c.save()

def get_shape_name(shape_value: str) -> str:
    """形状値を日本語名に変換"""
    shape_map = {
        "round": "丸棒",
        "hexagon": "六角棒",
        "square": "角棒"
    }
    return shape_map.get(shape_value, shape_value)

@router.get("/preview/{management_code}")
async def preview_label(management_code: str, db: Session = Depends(get_db)):
    """ラベルプレビュー情報取得"""
    item = db.query(Item).options(
        joinedload(Item.lot).joinedload(Lot.material),
        joinedload(Item.location)
    ).filter(Item.management_code == management_code).first()

    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="指定された管理コードのアイテムが見つかりません"
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
            "management_code": item.management_code,
            "current_quantity": item.current_quantity,
            "created_at": item.created_at
        },
        "material": {
            "name": material.name,
            "shape": material.shape.value,
            "shape_name": get_shape_name(material.shape.value),
            "diameter_mm": material.diameter_mm,
            "density": material.current_density
        },
        "lot": {
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

    if request.label_type == "small":
        # 小型現品票（50×30mm）
        create_small_lot_tag(buffer, lot, material, request.copies)
    else:
        # A4標準現品票
        create_standard_lot_tag(buffer, lot, material, request.copies)

    buffer.seek(0)

    # PDFレスポンス
    response = Response(
        content=buffer.getvalue(),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=lot_tag_{lot.lot_number}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        }
    )

    return response

def create_standard_lot_tag(buffer: BytesIO, lot, material, copies: int):
    """A4標準現品票作成"""
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=10*mm, bottomMargin=10*mm)
    styles = getSampleStyleSheet()

    # 日本語対応スタイル
    jp_style = ParagraphStyle(
        'Japanese',
        parent=styles['Normal'],
        fontName='HeiseiKakuGo-W5',
        fontSize=12,
        leading=16
    )

    title_style = ParagraphStyle(
        'JapaneseTitle',
        parent=styles['Title'],
        fontName='HeiseiKakuGo-W5',
        fontSize=20,
        leading=24,
        alignment=1  # 中央揃え
    )

    for copy_num in range(copies):
        story = []

        # タイトル
        story.append(Paragraph("現品票", title_style))
        story.append(Spacer(1, 15*mm))

        # QRコード（ロット番号をエンコード）
        qr_buffer = create_qr_code(lot.lot_number, 30)
        qr_image = Image(qr_buffer, width=30*mm, height=30*mm)

        # QRコードとタイトルを並べて配置
        header_table = Table([[qr_image, "QRコード: " + lot.lot_number[:20] + ("..." if len(lot.lot_number) > 20 else "")]],
                           colWidths=[35*mm, 120*mm])
        header_table.setStyle(TableStyle([
            ('FONT', (1, 0), (1, 0), 'HeiseiKakuGo-W5'),
            ('FONTSIZE', (1, 0), (1, 0), 10),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (1, 0), (1, 0), 'LEFT'),
        ]))

        story.append(header_table)
        story.append(Spacer(1, 10*mm))

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

        # メイン情報テーブル
        data = [
            ["ロット番号", lot.lot_number],
            ["材質", material.name],
            ["形状・寸法", f"{get_shape_name(material.shape.value)} φ{material.diameter_mm}mm" if material.shape.value == "round" else f"{get_shape_name(material.shape.value)} {material.diameter_mm}mm"],
            ["長さ", f"{lot.length_mm}mm"],
            ["単重", f"{weight_per_piece_kg:.3f}kg/本"],
            ["仕入先", lot.supplier or "未登録"],
            ["入荷日", lot.received_date.strftime("%Y/%m/%d") if lot.received_date else "未登録"],
            ["作成日時", lot.created_at.strftime("%Y/%m/%d %H:%M")],
            ["印刷日時", datetime.now().strftime("%Y/%m/%d %H:%M")]
        ]

        table = Table(data, colWidths=[45*mm, 110*mm])
        table.setStyle(TableStyle([
            ('FONT', (0, 0), (-1, -1), 'HeiseiKakuGo-W5'),
            ('FONTSIZE', (0, 0), (-1, -1), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
            ('ROWBACKGROUNDS', (0, 0), (-1, -1), [colors.white, colors.lightgrey])
        ]))

        story.append(table)
        story.append(Spacer(1, 10*mm))

        # 備考欄
        if lot.notes:
            story.append(Paragraph("備考:", jp_style))
            story.append(Paragraph(lot.notes, jp_style))

        if copy_num < copies - 1:
            story.append(Spacer(1, 30*mm))

    doc.build(story)

def create_small_lot_tag(buffer: BytesIO, lot, material, copies: int):
    """小型現品票（50×30mm）作成"""
    page_width = 50 * mm
    page_height = 30 * mm

    c = canvas.Canvas(buffer, pagesize=(page_width, page_height))

    for copy_num in range(copies):
        if copy_num > 0:
            c.showPage()

        # QRコード（15mm角）
        qr_buffer = create_qr_code(lot.lot_number, 15)
        c.drawImage(qr_buffer, 2*mm, 12*mm, width=15*mm, height=15*mm)

        # タイトル
        c.setFont('HeiseiKakuGo-W5', 7)
        c.drawString(20*mm, 26*mm, "現品票")

        # テキスト情報（右側）
        c.setFont('HeiseiKakuGo-W5', 5)

        # 材質・形状
        c.drawString(20*mm, 22*mm, f"{material.name}")
        c.drawString(20*mm, 19*mm, f"{get_shape_name(material.shape.value)}")

        # 寸法・長さ
        if material.shape.value == "round":
            size_text = f"φ{material.diameter_mm}"
        else:
            size_text = f"{material.diameter_mm}□"
        c.drawString(20*mm, 16*mm, size_text)
        c.drawString(20*mm, 13*mm, f"L{lot.length_mm}")

        # ロット番号（下部）
        c.setFont('HeiseiKakuGo-W5', 4)
        lot_short = lot.lot_number[:12] + "..." if len(lot.lot_number) > 12 else lot.lot_number
        c.drawString(2*mm, 8*mm, lot_short)

        # 仕入先・印刷日
        c.drawString(2*mm, 5*mm, lot.supplier[:8] + "..." if lot.supplier and len(lot.supplier) > 8 else lot.supplier or "")
        c.drawString(2*mm, 2*mm, datetime.now().strftime("%m/%d"))

    c.save()

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
            "created_at": lot.created_at
        },
        "material": {
            "name": material.name,
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
