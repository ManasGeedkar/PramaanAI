import io
import json
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

import cv2
import numpy as np
import pymupdf
from PIL import Image as PILImage, ImageChops
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    Image as RLImage,
    KeepTogether,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfgen import canvas
from sqlmodel import Session, select

from app.config import DATA_DIR, STORAGE_DIR, MOCK_SOURCES_DIR, APPLICATIONS_DIR
from app.models import Application, Document, Finding, ExtractedField, Verification

FINDING_QUESTIONS = {
    "MISSING_DOC": "Physically inspect original physical copy of {doc_type} on site; verify registration authority stamp.",
    "EXPIRED_DOC": "Verify current valid statutory certificate and fee receipt on site; confirm no lapse in validity.",
    "CROSS_DOC_MISMATCH": "Inspect original title deeds, revenue khasra/khatauni, and physical boundary registers on site.",
    "RULE_FAIL": "Verify physical campus compliance with AICTE Approval Process Handbook norms ({rule_id}).",
    "RECORD_MISMATCH": "Cross-check physical enrollment registers and AICTE approval orders from prior academic years.",
    "NO_PREVIOUS_RECORD": "Verify original institution establishment approval records and university affiliation gazette.",
    "TAMPER_SUSPECTED": "Physically examine original paper document under magnification for erasure or altered dates.",
    "METADATA_ANOMALY": "Request issuing authority confirmation copy directly; inspect authorized physical seal.",
    "QR_MISMATCH": "Scan physical document QR code directly with official validator; verify document serial number.",
    "DUPLICATE_IMAGE": "Inspect laboratory/classroom facilities on site to confirm exclusive infrastructure setup.",
    "ENTITY_REUSE": "Verify employment registers, biometric attendance, and identity cards of listed faculty on site.",
    "SOURCE_MISMATCH": "Inspect original stamped certificate and obtain written confirmation from local issuing authority.",
    "SOURCE_EXPIRED": "Confirm on-site whether valid renewal application has been formally acknowledged by authority.",
    "SOURCE_UNAVAILABLE": "Review official university affiliation registers with the inspection committee.",
    "VERIFICATION_PENDING": "Obtain certified copy of revenue entry/deed issued by the local sub-registrar office.",
    "MANUAL_REVIEW": "Examine original high-resolution physical certificate and verify seals.",
    "LOW_QUALITY_SCAN": "Request and inspect clean physical original document on site.",
    "LOW_OCR_CONFIDENCE": "Inspect physical document text, dates, and numbers directly on site.",
}


class NumberedCanvas(canvas.Canvas):
    """
    Two-pass canvas to dynamically compute and draw total page count
    and the mandatory disclaimer footer on every page.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count):
        self.saveState()
        self.setFont("Helvetica-Bold", 8)
        self.setFillColor(colors.HexColor("#475569"))
        self.drawString(36, 20, "Advisory findings for verification - not a determination.")
        
        self.setFont("Helvetica", 8)
        page_str = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(A4[0] - 36, 20, page_str)
        
        self.setStrokeColor(colors.HexColor("#cbd5e1"))
        self.setLineWidth(0.5)
        self.line(36, 30, A4[0] - 36, 30)
        self.restoreState()


def get_application_json_data(app: Application) -> Dict[str, Any]:
    folder_path = Path(app.folder)
    candidates = [
        folder_path,
        APPLICATIONS_DIR / app.folder,
        DATA_DIR / "applications" / app.folder,
        DATA_DIR / app.folder,
    ]
    for p in candidates:
        app_json = p / "application.json"
        if app_json.exists():
            try:
                with open(app_json, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
    return {}


def get_aicte_record(aicte_id: str) -> Optional[Dict[str, Any]]:
    aicte_file = MOCK_SOURCES_DIR / "aicte_records.json"
    if aicte_file.exists():
        try:
            with open(aicte_file, "r", encoding="utf-8") as f:
                records = json.load(f)
                return records.get(aicte_id)
        except Exception:
            pass
    return None


def resolve_doc_path(doc: Document) -> Optional[Path]:
    fp = Path(doc.file_path)
    if fp.exists():
        return fp
    candidates = [
        DATA_DIR / doc.file_path,
        APPLICATIONS_DIR / doc.file_path,
        APPLICATIONS_DIR / doc.application.folder / doc.file_path if doc.application else None,
    ]
    for c in candidates:
        if c and c.exists():
            return c
    return None


def generate_full_line_crop(doc: Document, bbox: List[float]) -> Tuple[Optional[bytes], Optional[pymupdf.Rect], Optional[pymupdf.Document]]:
    """
    Crops horizontally from x = 40 pt to bbox.x1 + 80 pt,
    plus 12 pt above and below the bbox, drawing a red box around the exact value bbox,
    and rendering at 200 dpi for sharp readability.
    """
    file_path = resolve_doc_path(doc)
    if not file_path or not file_path.exists():
        return None, None, None

    try:
        if file_path.suffix.lower() == ".pdf":
            pdoc = pymupdf.open(str(file_path))
            if len(pdoc) == 0:
                pdoc.close()
                return None, None, None
            page = pdoc[0]
            pw, ph = page.rect.width, page.rect.height

            # Crop horizontally from x = 40 pt to bbox.x1 + 80 pt
            x0 = 40.0
            x1 = min(pw, float(bbox[2]) + 80.0)
            y0 = max(0.0, float(bbox[1]) - 12.0)
            y1 = min(ph, float(bbox[3]) + 12.0)
            crop_rect = pymupdf.Rect(x0, y0, x1, y1)

            # Draw red box on the exact value bbox
            val_rect = pymupdf.Rect(*bbox)
            page.draw_rect(val_rect, color=(0.85, 0.1, 0.1), width=1.5)

            # Render at 200 dpi so label and value are clearly readable
            pix = page.get_pixmap(clip=crop_rect, dpi=200)
            crop_bytes = pix.tobytes("png")
            return crop_bytes, crop_rect, pdoc
    except Exception as e:
        print(f"Error generating crop for doc {doc.id}: {e}")
    return None, None, None


def generate_ela_crop(doc: Document, crop_rect: pymupdf.Rect) -> Optional[bytes]:
    """
    Generates an ELA heatmap for the exact same region as crop_rect,
    normalised by the 99th percentile of that crop, and rendered with COLORMAP_HOT
    (low = dark/black, high = yellow/white) so the edited region clearly stands out.
    """
    file_path = resolve_doc_path(doc)
    if not file_path or not file_path.exists():
        return None

    try:
        with pymupdf.open(str(file_path)) as pdoc:
            if len(pdoc) == 0:
                return None
            page = pdoc[0]
            pw, ph = page.rect.width, page.rect.height

            imgs = page.get_images()
            orig_pil = None
            if imgs:
                try:
                    xref = imgs[0][0]
                    base_img = pdoc.extract_image(xref)
                    orig_pil = PILImage.open(io.BytesIO(base_img["image"])).convert("RGB")
                except Exception:
                    orig_pil = None
            if orig_pil is None:
                pix = page.get_pixmap(dpi=200)
                orig_pil = PILImage.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")

            buf = io.BytesIO()
            orig_pil.save(buf, format="JPEG", quality=75)
            buf.seek(0)
            resaved_pil = PILImage.open(buf)
            diff = ImageChops.difference(orig_pil, resaved_pil)
            diff_arr = np.array(diff).astype(np.float32)
            diff_gray = np.mean(diff_arr, axis=2)

            sx = orig_pil.width / pw
            sy = orig_pil.height / ph

            hx0 = max(0, int(crop_rect.x0 * sx))
            hx1 = min(orig_pil.width, int(crop_rect.x1 * sx))
            hy0 = max(0, int(crop_rect.y0 * sy))
            hy1 = min(orig_pil.height, int(crop_rect.y1 * sy))

            crop_diff = diff_gray[hy0:hy1, hx0:hx1]
            if crop_diff.size == 0:
                return None

            p99 = np.percentile(crop_diff, 99)
            if p99 <= 0:
                p99 = 1.0

            crop_norm = np.clip((crop_diff / p99) * 255.0, 0, 255).astype(np.uint8)
            heatmap_hot = cv2.applyColorMap(crop_norm, cv2.COLORMAP_HOT)
            heatmap_rgb = cv2.cvtColor(heatmap_hot, cv2.COLOR_BGR2RGB)
            pil_ela = PILImage.fromarray(heatmap_rgb)

            out_buf = io.BytesIO()
            pil_ela.save(out_buf, format="PNG")
            return out_buf.getvalue()
    except Exception as e:
        print(f"Error generating ELA crop for doc {doc.id}: {e}")
    return None


def generate_qr_crop(doc: Document, session: Session) -> Tuple[Optional[bytes], Optional[Dict[str, Any]]]:
    """
    Crops the QR code area on the document and retrieves the decoded payload.
    """
    qr_field = session.exec(
        select(ExtractedField).where(
            ExtractedField.document_id == doc.id,
            ExtractedField.name == "qr"
        )
    ).first()

    decoded_dict = None
    bbox = None
    if qr_field and qr_field.value:
        try:
            decoded_dict = json.loads(qr_field.value)
        except Exception:
            decoded_dict = {"raw": qr_field.value}
        if qr_field.bbox_json:
            try:
                bbox = json.loads(qr_field.bbox_json)
            except Exception:
                bbox = None

    file_path = resolve_doc_path(doc)
    if not file_path or not file_path.exists():
        return None, decoded_dict

    try:
        with pymupdf.open(str(file_path)) as pdoc:
            if len(pdoc) == 0:
                return None, decoded_dict
            page = pdoc[0]
            if bbox:
                qr_rect = pymupdf.Rect(*bbox)
            else:
                qr_rect = pymupdf.Rect(page.rect.width - 150, page.rect.height - 180, page.rect.width - 30, page.rect.height - 40)

            pad = 10.0
            clip_rect = pymupdf.Rect(
                max(0.0, qr_rect.x0 - pad),
                max(0.0, qr_rect.y0 - pad),
                min(page.rect.width, qr_rect.x1 + pad),
                min(page.rect.height, qr_rect.y1 + pad)
            )
            page.draw_rect(qr_rect, color=(0.1, 0.4, 0.8), width=1.5)
            pix = page.get_pixmap(clip=clip_rect, dpi=200)
            return pix.tobytes("png"), decoded_dict
    except Exception as e:
        print(f"Error generating QR crop for doc {doc.id}: {e}")
    return None, decoded_dict


def generate_inspection_brief(app: Application, session: Session) -> bytes:
    """
    Generates a 1-2 page inspection brief PDF for physical inspection teams.
    """
    buf = io.BytesIO()
    doc_pdf = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=36,
        rightMargin=36,
        topMargin=28,
        bottomMargin=36,
    )

    app_data = get_application_json_data(app)
    inst_info = app_data.get("institution", {})
    district = inst_info.get("district", "N/A")
    state = inst_info.get("state", "N/A")
    univ_name = inst_info.get("university", "Affiliating University")
    aicte_rec = get_aicte_record(app.aicte_id)

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "BriefTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=12.5,
        leading=15,
        textColor=colors.HexColor("#0f172a"),
    )
    subtitle_style = ParagraphStyle(
        "BriefSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9,
        leading=11,
        textColor=colors.HexColor("#1e3a8a"),
    )
    demo_note_style = ParagraphStyle(
        "DemoNote",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=7,
        leading=9,
        textColor=colors.HexColor("#64748b"),
    )
    normal_style = ParagraphStyle(
        "BriefNormal",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=7.5,
        leading=10,
        textColor=colors.HexColor("#334155"),
    )
    bold_style = ParagraphStyle(
        "BriefBold",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=7.5,
        leading=10,
        textColor=colors.HexColor("#0f172a"),
    )
    pin_style = ParagraphStyle(
        "BriefPin",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#0369a1"),
    )

    story = []

    # 1. Header Banner
    band_color = {
        "High": colors.HexColor("#dc2626"),
        "Medium": colors.HexColor("#d97706"),
        "Low": colors.HexColor("#16a34a"),
    }.get(app.risk_band or "Low", colors.HexColor("#475569"))

    header_data = [
        [
            Paragraph("PramaanAI - Physical Inspection Brief (Prototype)", subtitle_style),
            Paragraph(
                f"<font color='white'><b>RISK BAND: {(app.risk_band or 'LOW').upper()} ({int(app.risk_score)} pts)</b></font>",
                ParagraphStyle("RiskBadge", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=8.5, leading=10, alignment=2),
            ),
        ],
        [
            Paragraph("Prepared for AICTE PS 26261 demo - synthetic data", demo_note_style),
            Paragraph(
                f"<b>Application:</b> {app.application_no} &nbsp;|&nbsp; <b>Category:</b> {app.category}",
                ParagraphStyle("HeaderMeta", parent=normal_style, alignment=2),
            ),
        ],
        [
            Paragraph(f"<b>{app.institution_name}</b>", title_style),
            Paragraph(f"<b>Date:</b> {datetime.utcnow().strftime('%d-%m-%Y')}", ParagraphStyle("HeaderDate", parent=normal_style, alignment=2)),
        ],
    ]
    header_table = Table(header_data, colWidths=[355, 168])
    header_table.setStyle(
        TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BACKGROUND", (1, 0), (1, 0), band_color),
            ("TOPPADDING", (0, 0), (-1, -1), 1),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("LEFTPADDING", (1, 0), (1, 0), 4),
            ("RIGHTPADDING", (1, 0), (1, 0), 4),
        ])
    )
    story.append(header_table)
    story.append(Spacer(1, 4))

    # 2. Location line (plain text, no emoji)
    loc_text = f"Location: {district}, {state} &nbsp;|&nbsp; AICTE Permanent ID: {app.aicte_id} &nbsp;|&nbsp; Academic Year: {app.academic_year}"
    pin_box = Table([[Paragraph(loc_text, pin_style)]], colWidths=[523])
    pin_box.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
            ("TOPPADDING", (0, 0), (-1, -1), 2.5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ])
    )
    story.append(pin_box)
    story.append(Spacer(1, 5))

    # 3. Previous-Year vs Current Deltas Table
    prev_approved = {}
    prev_year_str = "None"
    if aicte_rec and aicte_rec.get("previous_year"):
        py = aicte_rec["previous_year"]
        prev_year_str = py.get("academic_year", "2026-27")
        prev_approved = py.get("approved_intake", {})

    programmes = app_data.get("programmes", [])
    delta_rows = [
        [
            Paragraph("<b>Programme</b>", bold_style),
            Paragraph(f"<b>Prev Approved ({prev_year_str})</b>", bold_style),
            Paragraph("<b>Claimed Existing</b>", bold_style),
            Paragraph("<b>Proposed Intake</b>", bold_style),
            Paragraph("<b>Intake Delta</b>", bold_style),
        ]
    ]

    row_styles = []
    if programmes:
        for idx, p in enumerate(programmes, start=1):
            p_name = p.get("name", "N/A")
            prev_intake = prev_approved.get(p_name, "N/A" if aicte_rec and aicte_rec.get("previous_year") else "None")
            claimed = p.get("existing_intake_claimed", 0)
            proposed = p.get("proposed_intake", 0)

            # Delta = proposed - previous approved
            if isinstance(prev_intake, int):
                diff = proposed - prev_intake
                delta_str = f"+{diff}" if diff > 0 else (str(diff) if diff < 0 else "0 (Unchanged)")
                has_discrepancy = (claimed != prev_intake)
            else:
                delta_str = "New / No Record"
                has_discrepancy = False

            row_text_color = "#dc2626" if has_discrepancy else "#334155"
            row_bold_color = "#991b1b" if has_discrepancy else "#0f172a"
            
            p_style = ParagraphStyle(f"DeltaP_{idx}", parent=normal_style, textColor=colors.HexColor(row_text_color))
            p_bold = ParagraphStyle(f"DeltaB_{idx}", parent=bold_style, textColor=colors.HexColor(row_bold_color))

            claimed_str = f"<b>{claimed}</b>" if not has_discrepancy else f"<b>{claimed}</b> (mismatch!)"

            delta_rows.append([
                Paragraph(f"<b>{p_name}</b>", p_bold),
                Paragraph(str(prev_intake), p_style),
                Paragraph(claimed_str, p_style),
                Paragraph(str(proposed), p_style),
                Paragraph(f"<b>{delta_str}</b>", p_bold),
            ])

            if has_discrepancy:
                # Highlight row red when claimed existing != previous approved (INST10 case)
                row_styles.append(("BACKGROUND", (0, idx), (-1, idx), colors.HexColor("#fee2e2")))
                row_styles.append(("LINEBELOW", (0, idx), (-1, idx), 1, colors.HexColor("#ef4444")))
    else:
        delta_rows.append([
            Paragraph("No programme details declared", normal_style),
            Paragraph("-", normal_style),
            Paragraph("-", normal_style),
            Paragraph("-", normal_style),
            Paragraph("-", normal_style),
        ])

    delta_table = Table(delta_rows, colWidths=[155, 95, 95, 85, 93])
    base_delta_styles = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]
    delta_table.setStyle(TableStyle(base_delta_styles + row_styles))
    story.append(Paragraph("<b>1. Intake & Programme History Comparison (AICTE Record vs Application)</b>", bold_style))
    story.append(Spacer(1, 2.5))
    story.append(delta_table)
    story.append(Spacer(1, 5))

    # 4. Open Critical & Warning Findings Table
    open_findings = session.exec(
        select(Finding).where(
            Finding.application_id == app.id,
            Finding.severity.in_(["critical", "warning"]),
            Finding.status != "dismissed"
        )
    ).all()

    story.append(Paragraph(f"<b>2. Critical & Warning Scrutiny Findings ({len(open_findings)} Open)</b>", bold_style))
    story.append(Spacer(1, 2.5))

    findings_rows = [
        [
            Paragraph("<b>Code & Severity</b>", bold_style),
            Paragraph("<b>Scrutiny Reason & Discrepancy</b>", bold_style),
            Paragraph("<b>Suggested checks for the inspection team</b>", bold_style),
        ]
    ]

    for f in open_findings:
        sev_badge = f"<font color='{'#dc2626' if f.severity == 'critical' else '#d97706'}'><b>[{f.severity.upper()}]</b></font>"
        code_cell = f"<b>{f.code}</b><br/>{sev_badge}"
        
        q_template = FINDING_QUESTIONS.get(f.code, "Inspect and verify physical documents and infrastructure during the visit.")
        doc_type_val = "document"
        rule_id_val = f.rule_id or "Norms"
        
        if f.evidence_json:
            try:
                ev = json.loads(f.evidence_json)
                items = ev.get("items", [])
                if items:
                    doc_type_val = items[0].get("doc_type", doc_type_val)
            except Exception:
                pass

        directive_text = q_template.format(doc_type=doc_type_val, rule_id=rule_id_val)

        findings_rows.append([
            Paragraph(code_cell, normal_style),
            Paragraph(f"<b>{f.title}</b><br/>{f.message}", normal_style),
            Paragraph(directive_text, normal_style),
        ])

    if not open_findings:
        findings_rows.append([
            Paragraph("CLEAN", normal_style),
            Paragraph("No open critical or warning discrepancies detected by automated scrutiny.", normal_style),
            Paragraph("Conduct standard baseline verification of campus infrastructure.", normal_style),
        ])

    findings_table = Table(findings_rows, colWidths=[105, 215, 203])
    findings_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 2.5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ])
    )
    story.append(findings_table)
    story.append(Spacer(1, 5))

    # 5. Section: Verifications not completed
    # List every document whose verification status is pending, source_unavailable, or manual_review
    uncompleted_verifs = session.exec(
        select(Verification, Document)
        .where(
            Verification.document_id == Document.id,
            Document.application_id == app.id,
            Verification.status.in_(["pending", "source_unavailable", "manual_review"])
        )
    ).all()

    # Deduplicate by document_id + status
    unique_uncompleted = {}
    for v, doc in uncompleted_verifs:
        key = (v.document_id, v.status)
        if key not in unique_uncompleted:
            unique_uncompleted[key] = (v, doc)

    if unique_uncompleted:
        verif_rows = [
            [
                Paragraph("<b>Document & Source</b>", bold_style),
                Paragraph("<b>Status</b>", bold_style),
                Paragraph("<b>Suggested Follow-up Check for Inspection Team</b>", bold_style),
            ]
        ]

        status_colors = {
            "source_unavailable": "#b45309",
            "manual_review": "#dc2626",
            "pending": "#2563eb",
        }

        for (v, doc) in unique_uncompleted.values():
            s_color = status_colors.get(v.status, "#475569")
            s_badge = f"<font color='{s_color}'><b>{v.status.upper().replace('_', ' ')}</b></font>"
            doc_title = f"<b>{doc.doc_type}</b><br/><font color='#64748b'>Source: {v.source}</font>"

            # Suggested follow up check
            if v.source == "university" or doc.doc_type == "affiliation_letter" or v.status == "source_unavailable":
                suggested_check = f"Obtain affiliation confirmation directly from {univ_name}."
            elif v.status == "pending":
                suggested_check = f"Follow up with revenue/land registry office for async verification of deed {v.reference}."
            elif v.status == "manual_review":
                suggested_check = f"Physically inspect original high-resolution physical certificate and verify seals on site."
            else:
                suggested_check = f"Inspect physical document directly during on-site visit."

            verif_rows.append([
                Paragraph(doc_title, normal_style),
                Paragraph(s_badge, normal_style),
                Paragraph(suggested_check, normal_style),
            ])

        verif_table = Table(verif_rows, colWidths=[130, 110, 283])
        verif_table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#fffbeb")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#fde68a")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 2.5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ])
        )
        story.append(Paragraph(f"<b>3. Verifications not completed ({len(unique_uncompleted)} Outstanding)</b>", bold_style))
        story.append(Spacer(1, 2.5))
        story.append(verif_table)
        story.append(Spacer(1, 5))

    # 6. Document Evidence Highlights & Forensic Crops (Deduplicated, Stacked Vertically at 200 dpi)
    seen_crops = set()
    evidence_elements = []

    for f in open_findings:
        if not f.evidence_json:
            continue
        try:
            ev = json.loads(f.evidence_json)
        except Exception:
            continue

        items = ev.get("items", [])

        # Case A: ELA Tamper Suspected
        if f.code == "TAMPER_SUSPECTED" and items:
            item = items[0]
            doc_id = item.get("document_id")
            bbox = item.get("bbox")
            field_name = item.get("field", "unknown")
            crop_key = (doc_id, field_name)

            if crop_key not in seen_crops and doc_id and bbox:
                seen_crops.add(crop_key)
                doc_rec = session.get(Document, doc_id)
                if doc_rec:
                    doc_crop_bytes, crop_rect, open_pdoc = generate_full_line_crop(doc_rec, bbox)
                    if doc_crop_bytes and crop_rect:
                        ela_crop_bytes = generate_ela_crop(doc_rec, crop_rect)
                        
                        # Full content width = 520 pt
                        # Compute proportional height based on crop_rect aspect ratio
                        content_width = 515.0
                        crop_aspect = crop_rect.height / max(1.0, crop_rect.width)
                        disp_height = min(55.0, max(36.0, content_width * crop_aspect))

                        doc_img = RLImage(io.BytesIO(doc_crop_bytes), width=content_width, height=disp_height)
                        ela_img = RLImage(io.BytesIO(ela_crop_bytes), width=content_width, height=disp_height) if ela_crop_bytes else Paragraph("ELA unavailable", normal_style)

                        # Stacked vertically each full content width
                        stacked_data = [
                            [Paragraph(f"<b>Tamper Indicator on '{field_name}' ({doc_rec.doc_type})</b>", bold_style)],
                            [doc_img],
                            [Paragraph("<b>Document</b> (x = 40 pt to value + 80 pt, red box on value)", normal_style)],
                            [ela_img],
                            [Paragraph("<b>ELA</b> (bright = edited, normalised by 99th percentile)", normal_style)],
                        ]
                        stacked_table = Table(stacked_data, colWidths=[content_width + 4])
                        stacked_table.setStyle(
                            TableStyle([
                                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                                ("BACKGROUND", (0, 0), (0, 0), colors.HexColor("#fef2f2")),
                                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#fca5a5")),
                                ("TOPPADDING", (0, 0), (-1, -1), 2),
                                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                                ("LEFTPADDING", (0, 0), (-1, -1), 2),
                                ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                            ])
                        )
                        evidence_elements.append(stacked_table)
                        evidence_elements.append(Spacer(1, 5))

                    if open_pdoc:
                        open_pdoc.close()

        # Case B: QR_MISMATCH
        elif f.code == "QR_MISMATCH" and items:
            item = items[0]
            doc_id = item.get("document_id")
            doc_rec = session.get(Document, doc_id) if doc_id else None
            if doc_rec:
                qr_crop_bytes, qr_data = generate_qr_crop(doc_rec, session)
                qr_img = RLImage(io.BytesIO(qr_crop_bytes), width=55, height=55) if qr_crop_bytes else Paragraph("QR unavailable", normal_style)

                raw_qr = qr_data.get("raw", "N/A") if qr_data else "N/A"
                val_till_qr = qr_data.get("valid_till", "N/A") if qr_data else "N/A"
                holder_qr = qr_data.get("holder", "N/A") if qr_data else "N/A"

                qr_info_text = (
                    f"<b>QR Payload:</b> <code>{raw_qr}</code><br/>"
                    f"<b>Decoded Holder:</b> {holder_qr} &nbsp;|&nbsp; <b>Decoded Valid Till:</b> <font color='#dc2626'><b>{val_till_qr}</b></font><br/>"
                    f"<i>Discrepancy:</i> {f.message}"
                )

                qr_table = Table(
                    [
                        [Paragraph("<b>QR Code Verification Mismatch</b>", bold_style), ""],
                        [qr_img, Paragraph(qr_info_text, normal_style)],
                    ],
                    colWidths=[65, 450]
                )
                qr_table.setStyle(
                    TableStyle([
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("SPAN", (0, 0), (1, 0)),
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#fef2f2")),
                        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#fca5a5")),
                        ("TOPPADDING", (0, 0), (-1, -1), 2),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                        ("LEFTPADDING", (0, 0), (-1, -1), 3),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                    ])
                )
                evidence_elements.append(qr_table)
                evidence_elements.append(Spacer(1, 5))

        # Case C: SOURCE_MISMATCH
        elif f.code == "SOURCE_MISMATCH" and items:
            item = items[0]
            doc_id = item.get("document_id")
            doc_rec = session.get(Document, doc_id) if doc_id else None
            
            verif_row = session.exec(select(Verification).where(Verification.document_id == doc_id)).first() if doc_id else None
            qr_field = session.exec(select(ExtractedField).where(ExtractedField.document_id == doc_id, ExtractedField.name == "qr")).first() if doc_id else None
            
            qr_data = {}
            if qr_field and qr_field.value:
                try:
                    qr_data = json.loads(qr_field.value)
                except Exception:
                    pass

            reg_data = {}
            if verif_row and verif_row.details_json:
                try:
                    reg_data = json.loads(verif_row.details_json).get("registry_record", {})
                except Exception:
                    pass

            printed_fields = session.exec(select(ExtractedField).where(ExtractedField.document_id == doc_id)).all() if doc_id else []
            field_map = {pf.name: pf.value for pf in printed_fields}

            sm_rows = [
                [
                    Paragraph("<b>Attribute</b>", bold_style),
                    Paragraph("<b>Printed on Document</b>", bold_style),
                    Paragraph("<b>Decoded from QR</b>", bold_style),
                    Paragraph("<b>Official Registry Record</b>", bold_style),
                ],
                [
                    Paragraph("NOC / Cert No.", normal_style),
                    Paragraph(str(field_map.get("noc_no") or field_map.get("certificate_no") or item.get("value") or "N/A"), normal_style),
                    Paragraph(str(qr_data.get("reference") or "N/A"), normal_style),
                    Paragraph(str(verif_row.reference if verif_row else "N/A"), normal_style),
                ],
                [
                    Paragraph("Holder Institution", normal_style),
                    Paragraph(f"<b>{app.institution_id}</b>", normal_style),
                    Paragraph(f"<font color='{'#dc2626' if qr_data.get('holder') != app.institution_id else '#334155'}'><b>{qr_data.get('holder', 'N/A')}</b></font>", normal_style),
                    Paragraph(f"<font color='{'#dc2626' if reg_data.get('holder_institution_id') != app.institution_id else '#334155'}'><b>{reg_data.get('holder_institution_id', 'N/A')}</b></font>", normal_style),
                ],
                [
                    Paragraph("Valid Till / Status", normal_style),
                    Paragraph(f"<font color='#dc2626'><b>{field_map.get('valid_till', 'N/A')}</b></font>", normal_style),
                    Paragraph(f"<font color='#dc2626'><b>{qr_data.get('valid_till', 'N/A')}</b></font>", normal_style),
                    Paragraph(f"<font color='#dc2626'><b>{reg_data.get('valid_till', 'N/A')} ({reg_data.get('status', 'N/A')})</b></font>", normal_style),
                ]
            ]
            sm_table = Table(sm_rows, colWidths=[110, 135, 135, 140])
            sm_table.setStyle(
                TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#fef2f2")),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#fca5a5")),
                    ("TOPPADDING", (0, 0), (-1, -1), 2),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                    ("LEFTPADDING", (0, 0), (-1, -1), 4),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ])
            )
            evidence_elements.append(Paragraph("<b>Source Registry Cross-Verification: Printed vs QR vs Registry</b>", bold_style))
            evidence_elements.append(Spacer(1, 2))
            evidence_elements.append(sm_table)
            evidence_elements.append(Spacer(1, 5))

        # Case D: Other visual findings (CROSS_DOC_MISMATCH, EXPIRED_DOC)
        elif items and f.code in ["CROSS_DOC_MISMATCH", "EXPIRED_DOC"]:
            for it in items:
                doc_id = it.get("document_id")
                bbox = it.get("bbox")
                field_name = it.get("field", "unknown")
                crop_key = (doc_id, field_name)
                if crop_key in seen_crops or not doc_id or not bbox:
                    continue
                seen_crops.add(crop_key)
                doc_rec = session.get(Document, doc_id)
                if doc_rec:
                    doc_crop_bytes, crop_rect, open_pdoc = generate_full_line_crop(doc_rec, bbox)
                    if doc_crop_bytes and crop_rect:
                        content_width = 515.0
                        crop_aspect = crop_rect.height / max(1.0, crop_rect.width)
                        disp_height = min(50.0, max(32.0, content_width * crop_aspect))

                        doc_img = RLImage(io.BytesIO(doc_crop_bytes), width=content_width, height=disp_height)
                        cap = f"<b>{f.code}</b> on <i>{doc_rec.doc_type}</i> ({field_name}): {f.title}"
                        other_table = Table(
                            [
                                [Paragraph(cap, bold_style)],
                                [doc_img],
                            ],
                            colWidths=[content_width + 4]
                        )
                        other_table.setStyle(
                            TableStyle([
                                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                                ("BACKGROUND", (0, 0), (0, 0), colors.HexColor("#f1f5f9")),
                                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                                ("TOPPADDING", (0, 0), (-1, -1), 2),
                                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                                ("LEFTPADDING", (0, 0), (-1, -1), 2),
                                ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                            ])
                        )
                        evidence_elements.append(other_table)
                        evidence_elements.append(Spacer(1, 4))
                    if open_pdoc:
                        open_pdoc.close()

    section_num = 4 if unique_uncompleted else 3
    if evidence_elements:
        story.append(Paragraph(f"<b>{section_num}. Document Evidence Highlights & Forensic Crops</b>", bold_style))
        story.append(Spacer(1, 2.5))
        story.append(KeepTogether(evidence_elements))

    doc_pdf.build(story, canvasmaker=NumberedCanvas)
    buf.seek(0)
    return buf.getvalue()
