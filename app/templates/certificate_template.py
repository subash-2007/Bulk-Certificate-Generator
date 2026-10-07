"""
certificate_template.py - ReportLab certificate layout.

ONE predefined template used for every generated certificate.
To change the visual design, edit only this file.

Design philosophy:
    - A4 landscape orientation (297mm × 210mm)
    - Decorative border with a double-line frame
    - Gold-toned accent colours for headings
    - Clear typographic hierarchy: title → body → metadata
"""

import os
from datetime import date
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph
from reportlab.lib.enums import TA_CENTER

# ──────────────────────────────────────────────────────────────────────────────
# Colour palette
# ──────────────────────────────────────────────────────────────────────────────

GOLD = colors.HexColor("#C9A84C")
DARK_GOLD = colors.HexColor("#8B6914")
NAVY = colors.HexColor("#1A2B4A")
LIGHT_GRAY = colors.HexColor("#F5F5F0")
MID_GRAY = colors.HexColor("#888888")
WHITE = colors.white

# ──────────────────────────────────────────────────────────────────────────────
# Page dimensions (landscape A4)
# ──────────────────────────────────────────────────────────────────────────────

PAGE_WIDTH, PAGE_HEIGHT = landscape(A4)  # ≈ 841.9 × 595.3 pt
MARGIN = 20 * mm


def _draw_background(c: canvas.Canvas) -> None:
    """Fill background with off-white and add a subtle noise texture feel."""
    c.setFillColor(LIGHT_GRAY)
    c.rect(0, 0, PAGE_WIDTH, PAGE_HEIGHT, fill=True, stroke=False)


def _draw_border(c: canvas.Canvas) -> None:
    """Draw a decorative double-line border."""
    # Outer border
    c.setStrokeColor(GOLD)
    c.setLineWidth(3)
    c.rect(MARGIN, MARGIN, PAGE_WIDTH - 2 * MARGIN, PAGE_HEIGHT - 2 * MARGIN,
           fill=False, stroke=True)

    # Inner border (offset by 4pt)
    offset = 4 * mm
    c.setLineWidth(0.8)
    c.setStrokeColor(DARK_GOLD)
    c.rect(
        MARGIN + offset, MARGIN + offset,
        PAGE_WIDTH - 2 * (MARGIN + offset),
        PAGE_HEIGHT - 2 * (MARGIN + offset),
        fill=False, stroke=True
    )


def _draw_corner_ornaments(c: canvas.Canvas) -> None:
    """Draw small diamond ornaments at the four inner corners."""
    c.setFillColor(GOLD)
    size = 5
    corners = [
        (MARGIN + 4 * mm, MARGIN + 4 * mm),
        (PAGE_WIDTH - MARGIN - 4 * mm, MARGIN + 4 * mm),
        (MARGIN + 4 * mm, PAGE_HEIGHT - MARGIN - 4 * mm),
        (PAGE_WIDTH - MARGIN - 4 * mm, PAGE_HEIGHT - MARGIN - 4 * mm),
    ]
    for cx, cy in corners:
        # Simple filled square rotated 45° looks like a diamond
        p = c.beginPath()
        p.moveTo(cx, cy + size)
        p.lineTo(cx + size, cy)
        p.lineTo(cx, cy - size)
        p.lineTo(cx - size, cy)
        p.close()
        c.drawPath(p, fill=True, stroke=False)


def _draw_header_band(c: canvas.Canvas) -> None:
    """Draw the dark navy top band that contains the main title."""
    band_top = PAGE_HEIGHT - MARGIN - 4 * mm - 36 * mm
    band_height = 36 * mm
    c.setFillColor(NAVY)
    c.rect(
        MARGIN + 4 * mm, band_top,
        PAGE_WIDTH - 2 * (MARGIN + 4 * mm), band_height,
        fill=True, stroke=False
    )


def _center_text(c: canvas.Canvas, text: str, y: float,
                 font: str, size: float, color=WHITE) -> None:
    """Utility: draw centered text at position y."""
    c.setFont(font, size)
    c.setFillColor(color)
    c.drawCentredString(PAGE_WIDTH / 2, y, text)


def _draw_separator(c: canvas.Canvas, y: float, width_frac: float = 0.5) -> None:
    """Draw a thin gold horizontal rule, centred on the page."""
    half = (PAGE_WIDTH * width_frac) / 2
    cx = PAGE_WIDTH / 2
    c.setStrokeColor(GOLD)
    c.setLineWidth(0.8)
    c.line(cx - half, y, cx + half, y)


def build_certificate_pdf(
    *,
    output_path: str | Path,
    recipient_name: str,
    event_name: str,
    organization_name: str,
    event_date: str,         # Human-readable, e.g. "07 October 2026"
    certificate_id: str,
) -> None:
    """
    Generate a professional PDF certificate and save it to *output_path*.

    Args:
        output_path:       Absolute or relative path for the output PDF.
        recipient_name:    Full name of the certificate recipient.
        event_name:        Name of the event/course.
        organization_name: Issuing organisation.
        event_date:        Formatted date string shown on the certificate.
        certificate_id:    Unique certificate identifier printed at the bottom.

    Raises:
        OSError: If the output directory does not exist or is not writable.
        Exception: Any ReportLab error during PDF creation.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    c = canvas.Canvas(str(output_path), pagesize=landscape(A4))
    c.setTitle(f"Certificate – {recipient_name}")
    c.setAuthor(organization_name)
    c.setSubject(f"Certificate of Participation – {event_name}")

    # ── Background & decorative elements ──────────────────────────────────────
    _draw_background(c)
    _draw_border(c)
    _draw_corner_ornaments(c)
    _draw_header_band(c)

    # ── Title text inside the navy band ───────────────────────────────────────
    band_center_y = PAGE_HEIGHT - MARGIN - 4 * mm - 18 * mm  # midpoint of band
    _center_text(c, "CERTIFICATE OF PARTICIPATION",
                 band_center_y + 6, "Helvetica-Bold", 22, WHITE)
    _center_text(c, "───────────────────────────────────────",
                 band_center_y - 4, "Helvetica", 8, GOLD)

    # ── Body area Y positions (working downward from band bottom) ─────────────
    body_top = PAGE_HEIGHT - MARGIN - 4 * mm - 36 * mm  # band bottom
    y = body_top - 18 * mm

    # "This is to certify that"
    _center_text(c, "This is to certify that", y, "Helvetica", 13, MID_GRAY)
    y -= 16 * mm

    # Recipient name — largest text, gold coloured
    _center_text(c, recipient_name.upper(), y, "Helvetica-Bold", 30, DARK_GOLD)
    y -= 6 * mm

    _draw_separator(c, y, width_frac=0.35)
    y -= 12 * mm

    # "has successfully participated in"
    _center_text(c, "has successfully participated in", y, "Helvetica", 13, MID_GRAY)
    y -= 12 * mm

    # Event name
    _center_text(c, event_name, y, "Helvetica-Bold", 17, NAVY)
    y -= 10 * mm

    _draw_separator(c, y, width_frac=0.25)
    y -= 10 * mm

    # Date
    _center_text(c, event_date, y, "Helvetica", 12, MID_GRAY)

    # ── Signature section ────────────────────────────────────────────────────
    sig_y = MARGIN + 4 * mm + 18 * mm
    sig_x_right = PAGE_WIDTH * 0.72

    # Signature line
    c.setStrokeColor(NAVY)
    c.setLineWidth(0.8)
    c.line(sig_x_right - 60, sig_y + 8, sig_x_right + 60, sig_y + 8)

    c.setFont("Helvetica-Bold", 11)
    c.setFillColor(NAVY)
    c.drawCentredString(sig_x_right, sig_y - 2, organization_name)

    c.setFont("Helvetica", 9)
    c.setFillColor(MID_GRAY)
    c.drawCentredString(sig_x_right, sig_y - 11, "Authorised Signatory")

    # Organizer label
    c.setFont("Helvetica", 9)
    c.setFillColor(MID_GRAY)
    c.drawCentredString(sig_x_right, sig_y - 22, "Organizer")

    # ── Certificate ID (bottom-left footer) ───────────────────────────────────
    footer_y = MARGIN + 4 * mm + 6 * mm
    c.setFont("Helvetica", 8)
    c.setFillColor(MID_GRAY)
    c.drawString(MARGIN + 8 * mm, footer_y, f"Certificate ID: {certificate_id}")

    # ── Issued by (bottom-right footer) ───────────────────────────────────────
    c.drawRightString(
        PAGE_WIDTH - MARGIN - 8 * mm, footer_y,
        f"Issued by: {organization_name}"
    )

    c.save()
