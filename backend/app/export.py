"""CSV, JSON, and PDF export logic for vehicle data."""

import csv
import io
import json
from typing import List

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer

from app.models import Vehicle


EXPORT_FIELDS = [
    "vin", "stock_number", "year", "make", "model", "trim",
    "price", "mileage", "exterior_color", "interior_color",
    "body_style", "drivetrain", "engine", "transmission",
    "detail_url", "is_active",
]


def vehicles_to_dicts(vehicles: List[Vehicle]) -> List[dict]:
    """Convert Vehicle ORM objects to plain dicts for export."""
    rows = []
    for v in vehicles:
        row = {}
        for field in EXPORT_FIELDS:
            val = getattr(v, field, None)
            if val is None:
                val = ""
            elif isinstance(val, bool):
                val = "Yes" if val else "No"
            else:
                val = str(val)
            row[field] = val
        rows.append(row)
    return rows


def export_csv(vehicles: List[Vehicle]) -> str:
    """Export vehicles as CSV string."""
    rows = vehicles_to_dicts(vehicles)
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=EXPORT_FIELDS)
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


def export_json(vehicles: List[Vehicle]) -> str:
    """Export vehicles as JSON string."""
    rows = vehicles_to_dicts(vehicles)
    return json.dumps(rows, indent=2)


def export_pdf(vehicles: List[Vehicle]) -> bytes:
    """Export vehicles as PDF bytes."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(letter),
        rightMargin=30,
        leftMargin=30,
        topMargin=30,
        bottomMargin=30,
    )

    styles = getSampleStyleSheet()
    elements = []

    # Title
    elements.append(Paragraph("AutoAvenue Vehicle Inventory", styles["Title"]))
    elements.append(Spacer(1, 0.25 * inch))

    # Subtitle
    elements.append(Paragraph(f"Total: {len(vehicles)} vehicles", styles["Normal"]))
    elements.append(Spacer(1, 0.25 * inch))

    if not vehicles:
        elements.append(Paragraph("No vehicles to display.", styles["Normal"]))
        doc.build(elements)
        return buffer.getvalue()

    # Table data
    headers = ["VIN", "Year", "Make", "Model", "Price", "Mileage", "Color", "Body"]
    table_data = [headers]

    for v in vehicles:
        table_data.append([
            str(v.vin or ""),
            str(v.year or ""),
            str(v.make or ""),
            str(v.model or ""),
            f"${v.price:,.0f}" if v.price else "",
            f"{v.mileage:,}" if v.mileage else "",
            str(v.exterior_color or ""),
            str(v.body_style or ""),
        ])

    table = Table(table_data, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e3a5f")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("FONTSIZE", (0, 1), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
        ("TOPPADDING", (0, 0), (-1, 0), 8),
        ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#f8f9fa")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f0f4f8")]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#dee2e6")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))

    elements.append(table)
    doc.build(elements)
    return buffer.getvalue()
