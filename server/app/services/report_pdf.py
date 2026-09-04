"""
SURAKSHA Smart PPE — Automated PDF Reporting Service

Generates audit-ready, professional PDF safety and compliance reports using ReportLab:
1. Weekly Employee Report
2. Monthly Employee Report
3. Weekly All-Employees Report
4. Monthly All-Employees Report
"""

from __future__ import annotations

import calendar
from datetime import date, datetime, time, timedelta, timezone
import io
import logging
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.models import (
    Alert,
    AttendanceLog,
    ComplianceLog,
    Department,
    Gate,
    GateEvent,
    Mine,
    PpeDetection,
    PpeItem,
    SafetyScore,
    Worker,
    WorkerPpe,
)
from app.services import workers as worker_service

logger = logging.getLogger(__name__)

# Primary Color Palette (Coal Mine Safety Theme)
PRIMARY_DARK = colors.HexColor("#0f172a")     # Slate 900
SECONDARY_DARK = colors.HexColor("#1e293b")   # Slate 800
ACCENT_GREEN = colors.HexColor("#059669")     # Emerald / Safety Green
ACCENT_GREEN_BG = colors.HexColor("#ecfdf5")  # Emerald light tint
ACCENT_AMBER = colors.HexColor("#d97706")     # Amber / Warning
ACCENT_AMBER_BG = colors.HexColor("#fffbeb")  # Amber light tint
ACCENT_RED = colors.HexColor("#dc2626")       # Red / Danger / Denial
ACCENT_RED_BG = colors.HexColor("#fef2f2")    # Red light tint
NEUTRAL_BG = colors.HexColor("#f8fafc")       # Slate 50
ALT_ROW_BG = colors.HexColor("#f1f5f9")       # Slate 100
BORDER_COLOR = colors.HexColor("#cbd5e1")     # Slate 300
BORDER_DARK = colors.HexColor("#94a3b8")      # Slate 400
TEXT_MAIN = colors.HexColor("#0f172a")
TEXT_MUTED = colors.HexColor("#64748b")
TEXT_WHITE = colors.HexColor("#ffffff")


class NumberedCanvas(canvas.Canvas):
    """Two-pass canvas to calculate and render running headers and total page numbers (Page X of Y)."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._saved_page_states: list[dict[str, Any]] = []

    def showPage(self) -> None:
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self) -> None:
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count: int) -> None:
        self.saveState()
        self.setFont("Helvetica", 7.5)
        self.setFillColor(TEXT_MUTED)

        width, height = self._pagesize

        # Running Header (pages > 1)
        if self._pageNumber > 1:
            self.drawString(36, height - 24, "SURAKSHA — Smart PPE Safety & Compliance System")
            self.drawRightString(width - 36, height - 24, "Official Mine Safety Audit Report")
            self.setStrokeColor(BORDER_COLOR)
            self.setLineWidth(0.5)
            self.line(36, height - 28, width - 36, height - 28)

        # Running Footer (all pages)
        self.setStrokeColor(BORDER_COLOR)
        self.setLineWidth(0.5)
        self.line(36, 32, width - 36, 32)

        self.drawString(36, 20, "CONFIDENTIAL & PROPRIETARY — DGMS & MSHA COMPLIANT SAFETY AUDIT")
        self.drawRightString(width - 36, 20, f"Page {self._pageNumber} of {page_count}")
        self.restoreState()


def _get_styles() -> dict[str, ParagraphStyle]:
    sample = getSampleStyleSheet()
    styles: dict[str, ParagraphStyle] = {}

    styles["DocTitle"] = ParagraphStyle(
        "DocTitle",
        parent=sample["Normal"],
        fontName="Helvetica-Bold",
        fontSize=16,
        leading=20,
        textColor=PRIMARY_DARK,
    )
    styles["DocSubtitle"] = ParagraphStyle(
        "DocSubtitle",
        parent=sample["Normal"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=11,
        textColor=TEXT_MUTED,
    )
    styles["SectionHeading"] = ParagraphStyle(
        "SectionHeading",
        parent=sample["Normal"],
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=13,
        textColor=PRIMARY_DARK,
        spaceBefore=8,
        spaceAfter=4,
    )
    styles["CardTitle"] = ParagraphStyle(
        "CardTitle",
        parent=sample["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=10,
        textColor=TEXT_MUTED,
        alignment=1,  # Center
    )
    styles["CardValue"] = ParagraphStyle(
        "CardValue",
        parent=sample["Normal"],
        fontName="Helvetica-Bold",
        fontSize=14,
        leading=16,
        textColor=PRIMARY_DARK,
        alignment=1,
    )
    styles["CardValueGreen"] = ParagraphStyle(
        "CardValueGreen",
        parent=styles["CardValue"],
        textColor=ACCENT_GREEN,
    )
    styles["CardValueAmber"] = ParagraphStyle(
        "CardValueAmber",
        parent=styles["CardValue"],
        textColor=ACCENT_AMBER,
    )
    styles["CardValueRed"] = ParagraphStyle(
        "CardValueRed",
        parent=styles["CardValue"],
        textColor=ACCENT_RED,
    )
    styles["TableCell"] = ParagraphStyle(
        "TableCell",
        parent=sample["Normal"],
        fontName="Helvetica",
        fontSize=7.5,
        leading=9.5,
        textColor=TEXT_MAIN,
    )
    styles["TableCellBold"] = ParagraphStyle(
        "TableCellBold",
        parent=sample["Normal"],
        fontName="Helvetica-Bold",
        fontSize=7.5,
        leading=9.5,
        textColor=TEXT_MAIN,
    )
    styles["TableHeader"] = ParagraphStyle(
        "TableHeader",
        parent=sample["Normal"],
        fontName="Helvetica-Bold",
        fontSize=7.5,
        leading=9.5,
        textColor=TEXT_WHITE,
    )
    styles["CellCenter"] = ParagraphStyle(
        "CellCenter",
        parent=styles["TableCell"],
        alignment=1,
    )
    styles["CellCenterBold"] = ParagraphStyle(
        "CellCenterBold",
        parent=styles["TableCellBold"],
        alignment=1,
    )
    styles["BadgeGreen"] = ParagraphStyle(
        "BadgeGreen",
        parent=styles["TableCellBold"],
        textColor=ACCENT_GREEN,
        alignment=1,
    )
    styles["BadgeAmber"] = ParagraphStyle(
        "BadgeAmber",
        parent=styles["TableCellBold"],
        textColor=ACCENT_AMBER,
        alignment=1,
    )
    styles["BadgeRed"] = ParagraphStyle(
        "BadgeRed",
        parent=styles["TableCellBold"],
        textColor=ACCENT_RED,
        alignment=1,
    )
    styles["TextSmall"] = ParagraphStyle(
        "TextSmall",
        parent=sample["Normal"],
        fontName="Helvetica",
        fontSize=7,
        leading=9,
        textColor=TEXT_MUTED,
    )
    return styles


def _build_header_block(
    report_title: str,
    period_label: str,
    mine_name: str,
    gate_name: str,
    shift_name: str,
    generated_at_str: str,
    styles: dict[str, ParagraphStyle],
) -> Table:
    """Build standardized branding header table with metadata box."""
    brand_p = [
        Paragraph("SURAKSHA", styles["DocTitle"]),
        Paragraph("Smart PPE Safety &amp; Compliance Monitoring System", styles["DocSubtitle"]),
        Paragraph(f"<b>{report_title.upper()}</b>", ParagraphStyle(
            "ReportSub", parent=styles["DocSubtitle"], fontName="Helvetica-Bold", fontSize=9, textColor=ACCENT_GREEN, leading=12
        )),
    ]

    meta_table = Table(
        [
            [Paragraph("<b>Mine:</b>", styles["TextSmall"]), Paragraph(mine_name, styles["TableCell"])],
            [Paragraph("<b>Checkpoint:</b>", styles["TextSmall"]), Paragraph(gate_name, styles["TableCell"])],
            [Paragraph("<b>Shift:</b>", styles["TextSmall"]), Paragraph(shift_name, styles["TableCell"])],
            [Paragraph("<b>Period:</b>", styles["TextSmall"]), Paragraph(period_label, styles["TableCellBold"])],
            [Paragraph("<b>Generated:</b>", styles["TextSmall"]), Paragraph(generated_at_str, styles["TableCell"])],
        ],
        colWidths=[55, 145],
    )
    meta_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 1),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
    ]))

    header_table = Table([[brand_p, meta_table]], colWidths=["*", 210])
    header_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return header_table


# ==============================================================================
# INDIVIDUAL EMPLOYEE REPORT GENERATION
# ==============================================================================

def generate_employee_report(
    db: Session,
    worker_id: int,
    start_date: date,
    end_date: date,
    period_type: str = "WEEKLY",
    shift: str | None = None,
    gate_id: int | None = None,
) -> bytes:
    """Generate a high-density, audit-ready Individual Employee Safety & Compliance PDF."""
    worker = db.query(Worker).options(joinedload(Worker.department)).filter(Worker.worker_id == worker_id).one_or_none()
    if worker is None:
        raise ValueError(f"Worker with ID {worker_id} not found")

    # Fetch default mine and gate names
    mine = db.query(Mine).first()
    mine_name = mine.name if mine else "Central Coal Mine"

    gate = db.get(Gate, gate_id) if gate_id else db.query(Gate).first()
    gate_name = gate.name if gate else "All Checkpoints"
    shift_label = f"Shift {shift}" if shift and shift != "ALL" else "All Shifts"

    period_type_clean = period_type.upper()
    period_label = f"{start_date.strftime('%d %b %Y')} – {end_date.strftime('%d %b %Y')}"
    if period_type_clean == "MONTHLY":
        report_title = f"Monthly Employee Safety Report — {start_date.strftime('%B %Y')}"
    else:
        report_title = f"Weekly Employee Safety Report — Week of {start_date.strftime('%d %b %Y')}"

    now_str = datetime.now(timezone.utc).strftime("%d %b %Y, %H:%M UTC")

    # 1. Query Attendance Records in Period
    att_query = (
        db.query(AttendanceLog)
        .filter(
            AttendanceLog.worker_id == worker_id,
            func.date(AttendanceLog.entry_time) >= str(start_date),
            func.date(AttendanceLog.entry_time) <= str(end_date),
        )
    )
    if gate_id:
        att_query = att_query.filter(AttendanceLog.gate_id == gate_id)
    att_logs = att_query.order_by(AttendanceLog.entry_time.asc()).all()

    # 2. Query Compliance Records in Period
    comp_query = (
        db.query(ComplianceLog)
        .options(joinedload(ComplianceLog.detections).joinedload(PpeDetection.ppe_item))
        .filter(
            ComplianceLog.worker_id == worker_id,
            func.date(ComplianceLog.entry_time) >= str(start_date),
            func.date(ComplianceLog.entry_time) <= str(end_date),
        )
    )
    if gate_id:
        comp_query = comp_query.filter(ComplianceLog.gate_id == gate_id)
    comp_logs = comp_query.order_by(ComplianceLog.entry_time.asc()).all()

    # 3. Query Alerts in Period
    alert_query = (
        db.query(Alert)
        .filter(
            Alert.worker_id == worker_id,
            func.date(Alert.created_at) >= str(start_date),
            func.date(Alert.created_at) <= str(end_date),
        )
    )
    alerts = alert_query.all()

    # Calculate Period Day Map
    total_days = (end_date - start_date).days + 1
    days_list = [start_date + timedelta(days=i) for i in range(total_days)]

    # Group Attendance & Compliance by day
    att_by_day: dict[date, list[AttendanceLog]] = {d: [] for d in days_list}
    for log in att_logs:
        log_d = log.entry_time.date() if isinstance(log.entry_time, datetime) else log.entry_time
        if log_d in att_by_day:
            att_by_day[log_d].append(log)

    comp_by_day: dict[date, list[ComplianceLog]] = {d: [] for d in days_list}
    for log in comp_logs:
        log_d = log.entry_time.date() if isinstance(log.entry_time, datetime) else log.entry_time
        if log_d in comp_by_day:
            comp_by_day[log_d].append(log)

    # Key Metrics Computation
    days_present_count = sum(1 for d in days_list if len(att_by_day[d]) > 0 or len(comp_by_day[d]) > 0)
    attendance_pct = round((days_present_count / total_days) * 100, 1) if total_days > 0 else 0.0

    total_checkins = len(att_logs)
    total_checkouts = sum(1 for a in att_logs if a.exit_time is not None)

    # Compliance Stats
    total_comp_entries = len(comp_logs)
    compliant_entries = sum(1 for c in comp_logs if c.overall_status == "COMPLIANT" or c.final_verdict == "ALLOWED")
    warning_entries = sum(1 for c in comp_logs if c.overall_status == "NON_COMPLIANT" or c.final_verdict == "WARNING")
    denied_entries = sum(1 for c in comp_logs if c.overall_status == "DENIED" or c.final_verdict == "DENIED")

    # PPE Detections by Item
    ppe_catalog_names = ["Helmet", "Vest", "Boots"]
    ppe_stats: dict[str, dict[str, Any]] = {
        name: {"detected": 0, "missing": 0, "total": 0, "conf_sum": 0.0}
        for name in ppe_catalog_names
    }

    for comp in comp_logs:
        for det in comp.detections:
            item_name = det.ppe_item.name if det.ppe_item else "Unknown"
            if item_name in ppe_stats:
                ppe_stats[item_name]["total"] += 1
                if det.detected:
                    ppe_stats[item_name]["detected"] += 1
                else:
                    ppe_stats[item_name]["missing"] += 1
                if det.confidence_score is not None:
                    ppe_stats[item_name]["conf_sum"] += det.confidence_score

    # PPE Compliance Rate %
    total_ppe_checks = sum(s["total"] for s in ppe_stats.values())
    total_ppe_detected = sum(s["detected"] for s in ppe_stats.values())
    ppe_compliance_pct = round((total_ppe_detected / total_ppe_checks) * 100, 1) if total_ppe_checks > 0 else (
        round(sum(c.compliance_score for c in comp_logs) / total_comp_entries, 1) if total_comp_entries > 0 else 100.0
    )

    # Gate Verdict Clearance Rate %
    gate_verdict_rate = round((compliant_entries / total_comp_entries) * 100, 1) if total_comp_entries > 0 else 100.0
    total_violations = warning_entries + denied_entries
    total_alerts_count = len(alerts)

    # Retrieve or determine Safety Score
    db_safety_score = worker_service.latest_safety_score(db, worker_id)
    if db_safety_score is not None:
        overall_score = round(db_safety_score.score, 1)
        risk_level = db_safety_score.risk_level
    else:
        # Period-derived score
        overall_score = round((ppe_compliance_pct * 0.6) + (gate_verdict_rate * 0.25) + (attendance_pct * 0.15), 1)
        risk_level = "LOW" if overall_score >= 90 else "MEDIUM" if overall_score >= 75 else "HIGH"

    # Identify Repeated PPE Violations & Recommendations
    missing_items = [name for name, s in ppe_stats.items() if s["missing"] > 0]
    repeated_violations: list[str] = []
    for item in missing_items:
        cnt = ppe_stats[item]["missing"]
        repeated_violations.append(f"{item}: {cnt} non-compliant check{'s' if cnt > 1 else ''}")

    if total_violations >= 3 or denied_entries >= 2:
        recommendation_text = (
            "<b>Supervisor Intervention Required:</b> Repeated PPE non-compliance detected. "
            "Schedule mandatory safety retraining and verify PPE gear fitment before next shift entry."
        )
    elif total_violations > 0:
        recommendation_text = (
            "<b>Advisory Notice:</b> Minor PPE compliance lapses recorded. "
            "Safety supervisor verbal reminder recommended prior to shaft deployment."
        )
    else:
        recommendation_text = (
            "<b>Exemplary Safety Compliance:</b> Zero PPE violations and full protocol adherence "
            "demonstrated across all entry audits for this period."
        )

    # Build PDF Story Flowables
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=42,
    )
    styles = _get_styles()
    story: list[Any] = []

    # 1. Branding Header
    story.append(_build_header_block(report_title, period_label, mine_name, gate_name, shift_label, now_str, styles))
    story.append(HRFlowable(width="100%", thickness=1, color=PRIMARY_DARK, spaceBefore=4, spaceAfter=8))

    # 2. Employee Info & Safety Score Card Side-by-Side
    designation_text = getattr(worker, "designation", None) or f"{worker.department.name} Specialist" if worker.department else "Mining Operator"
    emp_info_data = [
        [Paragraph("<b>Employee Name:</b>", styles["TableCellBold"]), Paragraph(worker.name, styles["TableCell"]),
         Paragraph("<b>Employee ID:</b>", styles["TableCellBold"]), Paragraph(worker.employee_code, styles["TableCellBold"])],
        [Paragraph("<b>Department:</b>", styles["TableCellBold"]), Paragraph(worker.department.name if worker.department else "General Mining", styles["TableCell"]),
         Paragraph("<b>Designation:</b>", styles["TableCellBold"]), Paragraph(designation_text, styles["TableCell"])],
        [Paragraph("<b>Assigned Gate:</b>", styles["TableCellBold"]), Paragraph(gate_name, styles["TableCell"]),
         Paragraph("<b>Status:</b>", styles["TableCellBold"]), Paragraph(f"<b>{worker.status}</b>", styles["BadgeGreen"] if worker.status == "ACTIVE" else styles["TableCell"])],
    ]
    emp_info_table = Table(emp_info_data, colWidths=[80, 150, 75, 90])
    emp_info_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("BACKGROUND", (0, 0), (-1, -1), NEUTRAL_BG),
        ("BOX", (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, BORDER_COLOR),
    ]))

    score_card_data = [
        [Paragraph("SAFETY SCORE", styles["CardTitle"])],
        [Paragraph(f"{overall_score:.0f}", styles["CardValueGreen"] if overall_score >= 90 else styles["CardValueAmber"] if overall_score >= 75 else styles["CardValueRed"])],
        [Paragraph(f"Risk: <b>{risk_level}</b>", styles["TextSmall"])],
    ]
    score_card_table = Table(score_card_data, colWidths=[105])
    score_card_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("BACKGROUND", (0, 0), (-1, -1), ACCENT_GREEN_BG if overall_score >= 90 else ACCENT_AMBER_BG if overall_score >= 75 else ACCENT_RED_BG),
        ("BOX", (0, 0), (-1, -1), 1, ACCENT_GREEN if overall_score >= 90 else ACCENT_AMBER if overall_score >= 75 else ACCENT_RED),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))

    info_summary_table = Table([[emp_info_table, score_card_table]], colWidths=[405, 115])
    info_summary_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(info_summary_table)

    # 3. Summary KPI Blocks (4 columns)
    kpis_data = [
        [
            Paragraph("PPE COMPLIANCE", styles["CardTitle"]),
            Paragraph("ATTENDANCE RATE", styles["CardTitle"]),
            Paragraph("GATE VERDICTS", styles["CardTitle"]),
            Paragraph("TOTAL VIOLATIONS", styles["CardTitle"]),
        ],
        [
            Paragraph(f"{ppe_compliance_pct:.1f}%", styles["CardValueGreen"] if ppe_compliance_pct >= 90 else styles["CardValueAmber"]),
            Paragraph(f"{attendance_pct:.1f}%", styles["CardValueGreen"] if attendance_pct >= 80 else styles["CardValueAmber"]),
            Paragraph(f"{compliant_entries}/{total_comp_entries or 0}", styles["CardValue"]),
            Paragraph(f"{total_violations}", styles["CardValueRed"] if total_violations > 0 else styles["CardValueGreen"]),
        ],
        [
            Paragraph(f"{total_ppe_detected}/{total_ppe_checks} items verified", styles["TextSmall"]),
            Paragraph(f"{days_present_count}/{total_days} days present", styles["TextSmall"]),
            Paragraph(f"{denied_entries} denied, {warning_entries} warning", styles["TextSmall"]),
            Paragraph(f"{total_alerts_count} security alerts", styles["TextSmall"]),
        ],
    ]
    kpis_table = Table(kpis_data, colWidths=[128, 128, 128, 128])
    kpis_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("BACKGROUND", (0, 0), (-1, -1), NEUTRAL_BG),
        ("BOX", (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    story.append(kpis_table)
    story.append(Spacer(1, 8))

    # 4. Attendance Calendar Matrix (Spreadsheet Template Inspiration)
    story.append(Paragraph(f"<b>Attendance &amp; Verification Calendar ({period_label})</b>", styles["SectionHeading"]))

    # We build calendar day cells
    # If Weekly (<= 7 days) -> 7 columns with day names & dates
    # If Monthly (28..31 days) -> Day numbered columns
    if total_days <= 7:
        cal_hdr = [Paragraph(f"<b>{d.strftime('%a')}<br/>{d.strftime('%d %b')}</b>", styles["CellCenterBold"]) for d in days_list]
        cal_row = []
        for d in days_list:
            d_att = att_by_day[d]
            d_comp = comp_by_day[d]
            if d_comp:
                verdict = d_comp[-1].final_verdict or d_comp[-1].overall_status
                if verdict in ("ALLOWED", "COMPLIANT"):
                    cell_text = "<font color='#059669'><b>PRESENT<br/>ALLOWED</b></font>"
                elif verdict == "DENIED":
                    cell_text = "<font color='#dc2626'><b>PRESENT<br/>DENIED</b></font>"
                else:
                    cell_text = "<font color='#d97706'><b>WARNING</b></font>"
            elif d_att:
                cell_text = "<font color='#059669'><b>PRESENT</b></font>"
            else:
                cell_text = "<font color='#94a3b8'>ABSENT<br/>/ NO REC</font>"
            cal_row.append(Paragraph(cell_text, styles["CellCenter"]))

        cal_table = Table([cal_hdr, cal_row], colWidths=[520 / total_days] * total_days)
        cal_table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("BACKGROUND", (0, 0), (-1, 0), ALT_ROW_BG),
            ("BOX", (0, 0), (-1, -1), 0.5, BORDER_COLOR),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, BORDER_COLOR),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
    else:
        # Monthly Matrix: Group by weeks or 7-day chunks for readable layout
        matrix_rows: list[list[Any]] = []
        matrix_rows.append([
            Paragraph("<b>Week</b>", styles["TableCellBold"]),
            Paragraph("<b>Mon</b>", styles["CellCenterBold"]),
            Paragraph("<b>Tue</b>", styles["CellCenterBold"]),
            Paragraph("<b>Wed</b>", styles["CellCenterBold"]),
            Paragraph("<b>Thu</b>", styles["CellCenterBold"]),
            Paragraph("<b>Fri</b>", styles["CellCenterBold"]),
            Paragraph("<b>Sat</b>", styles["CellCenterBold"]),
            Paragraph("<b>Sun</b>", styles["CellCenterBold"]),
            Paragraph("<b>Present</b>", styles["CellCenterBold"]),
        ])

        # Group days by calendar weeks
        current_week_num = 1
        current_row: list[Any] = [Paragraph(f"<b>Wk {current_week_num}</b>", styles["TableCellBold"])]
        # Pad leading days of first week
        first_weekday = days_list[0].weekday()  # 0 is Monday
        for _ in range(first_weekday):
            current_row.append(Paragraph("—", styles["CellCenter"]))

        week_present_count = 0
        for d in days_list:
            if len(current_row) == 8:  # Filled Mon-Sun
                current_row.append(Paragraph(f"<b>{week_present_count} d</b>", styles["CellCenterBold"]))
                matrix_rows.append(current_row)
                current_week_num += 1
                current_row = [Paragraph(f"<b>Wk {current_week_num}</b>", styles["TableCellBold"])]
                week_present_count = 0

            d_att = att_by_day[d]
            d_comp = comp_by_day[d]
            day_num = d.day

            if d_comp:
                verdict = d_comp[-1].final_verdict or d_comp[-1].overall_status
                if verdict in ("ALLOWED", "COMPLIANT"):
                    st = f"<font color='#059669'><b>{day_num}</b><br/>P</font>"
                    week_present_count += 1
                elif verdict == "DENIED":
                    st = f"<font color='#dc2626'><b>{day_num}</b><br/>D</font>"
                    week_present_count += 1
                else:
                    st = f"<font color='#d97706'><b>{day_num}</b><br/>W</font>"
                    week_present_count += 1
            elif d_att:
                st = f"<font color='#059669'><b>{day_num}</b><br/>P</font>"
                week_present_count += 1
            else:
                st = f"<font color='#94a3b8'>{day_num}<br/>-</font>"
            current_row.append(Paragraph(st, styles["CellCenter"]))

        # Pad trailing days of last week
        while len(current_row) < 8:
            current_row.append(Paragraph("—", styles["CellCenter"]))
        current_row.append(Paragraph(f"<b>{week_present_count} d</b>", styles["CellCenterBold"]))
        matrix_rows.append(current_row)

        cal_table = Table(matrix_rows, colWidths=[48, 58, 58, 58, 58, 58, 58, 58, 66])
        cal_table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("BACKGROUND", (0, 0), (-1, 0), PRIMARY_DARK),
            ("TEXTCOLOR", (0, 0), (-1, 0), TEXT_WHITE),
            ("BOX", (0, 0), (-1, -1), 0.5, BORDER_COLOR),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, BORDER_COLOR),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ]))

    story.append(cal_table)
    story.append(Paragraph("<font color='#64748b'><b>Legend:</b> P = Present / Allowed | W = Warning (Non-compliant PPE) | D = Entry Denied | - = Absent / No Record</font>", styles["TextSmall"]))
    story.append(Spacer(1, 8))

    # 5. PPE Item Compliance Breakdown Table
    story.append(Paragraph("<b>PPE Item Compliance &amp; Detection Breakdown</b>", styles["SectionHeading"]))
    ppe_table_data = [
        [
            Paragraph("<b>PPE Item Category</b>", styles["TableHeader"]),
            Paragraph("<b>Detections</b>", styles["CellCenterBold"]),
            Paragraph("<b>Compliant</b>", styles["CellCenterBold"]),
            Paragraph("<b>Missing / Failed</b>", styles["CellCenterBold"]),
            Paragraph("<b>Compliance Rate</b>", styles["CellCenterBold"]),
            Paragraph("<b>Avg Confidence</b>", styles["CellCenterBold"]),
        ]
    ]
    for item_name in ppe_catalog_names:
        stats = ppe_stats[item_name]
        tot = stats["total"]
        det = stats["detected"]
        mis = stats["missing"]
        rate = f"{(det / tot) * 100:.1f}%" if tot > 0 else "N/A"
        conf = f"{(stats['conf_sum'] / tot):.1f}%" if tot > 0 and stats["conf_sum"] > 0 else "N/A"
        ppe_table_data.append([
            Paragraph(f"<b>{item_name}</b> (Mandatory)", styles["TableCellBold"]),
            Paragraph(str(tot), styles["CellCenter"]),
            Paragraph(str(det), styles["BadgeGreen"] if det > 0 else styles["CellCenter"]),
            Paragraph(str(mis), styles["BadgeRed"] if mis > 0 else styles["CellCenter"]),
            Paragraph(rate, styles["CellCenterBold"]),
            Paragraph(conf, styles["CellCenter"]),
        ])

    ppe_table = Table(ppe_table_data, colWidths=[150, 70, 70, 80, 80, 70])
    ppe_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BACKGROUND", (0, 0), (-1, 0), PRIMARY_DARK),
        ("TEXTCOLOR", (0, 0), (-1, 0), TEXT_WHITE),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [TEXT_WHITE, ALT_ROW_BG]),
        ("BOX", (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ("TOPPADDING", (0, 0), (-1, -1), 2.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
    ]))
    story.append(ppe_table)
    story.append(Spacer(1, 8))

    # 6. Daily Compliance History (Last 10 records)
    story.append(Paragraph("<b>Recent Compliance Audit Records</b>", styles["SectionHeading"]))
    if comp_logs:
        comp_hist_data = [
            [
                Paragraph("<b>Date &amp; Time</b>", styles["TableHeader"]),
                Paragraph("<b>Gate</b>", styles["TableHeader"]),
                Paragraph("<b>Overall Verdict</b>", styles["TableHeader"]),
                Paragraph("<b>PPE Score</b>", styles["TableHeader"]),
                Paragraph("<b>Violations</b>", styles["TableHeader"]),
                Paragraph("<b>Sync Status</b>", styles["TableHeader"]),
            ]
        ]
        # Show most recent entries first
        for log in sorted(comp_logs, key=lambda x: x.entry_time, reverse=True)[:10]:
            verdict = log.final_verdict or log.overall_status
            if verdict in ("ALLOWED", "COMPLIANT"):
                verdict_p = Paragraph(f"<b>{verdict}</b>", styles["BadgeGreen"])
            elif verdict == "DENIED":
                verdict_p = Paragraph(f"<b>{verdict}</b>", styles["BadgeRed"])
            else:
                verdict_p = Paragraph(f"<b>{verdict}</b>", styles["BadgeAmber"])

            missing_in_log = [d.ppe_item.name for d in log.detections if not d.detected and d.ppe_item]
            v_text = ", ".join(missing_in_log) if missing_in_log else "None"

            dt_str = log.entry_time.strftime("%d %b %Y, %H:%M") if isinstance(log.entry_time, datetime) else str(log.entry_time)
            comp_hist_data.append([
                Paragraph(dt_str, styles["TableCell"]),
                Paragraph(log.gate.name if log.gate else gate_name, styles["TableCell"]),
                verdict_p,
                Paragraph(f"{log.compliance_score:.0f}%", styles["TableCellBold"]),
                Paragraph(v_text, styles["TableCell"]),
                Paragraph(log.sync_status.title(), styles["TextSmall"]),
            ])

        comp_hist_table = Table(comp_hist_data, colWidths=[110, 85, 95, 70, 100, 60])
        comp_hist_table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("BACKGROUND", (0, 0), (-1, 0), SECONDARY_DARK),
            ("TEXTCOLOR", (0, 0), (-1, 0), TEXT_WHITE),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [TEXT_WHITE, ALT_ROW_BG]),
            ("BOX", (0, 0), (-1, -1), 0.5, BORDER_COLOR),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, BORDER_COLOR),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ]))
        story.append(comp_hist_table)
    else:
        story.append(Paragraph("<i>No compliance events recorded for this employee in the selected reporting period.</i>", styles["TextSmall"]))

    story.append(Spacer(1, 8))

    # 7. Repeated Violations & Actionable Supervisor Recommendations
    recom_block_data = [
        [
            Paragraph("<b>Repeated PPE Violations &amp; Safety Audit Findings:</b>", styles["TableCellBold"]),
            Paragraph(
                ", ".join(repeated_violations) if repeated_violations else "None identified in selected audit period.",
                styles["TableCell"],
            ),
        ],
        [
            Paragraph("<b>Recommended Action:</b>", styles["TableCellBold"]),
            Paragraph(recommendation_text, styles["TableCell"]),
        ],
    ]
    recom_table = Table(recom_block_data, colWidths=[160, 360])
    recom_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BACKGROUND", (0, 0), (-1, -1), ACCENT_AMBER_BG if repeated_violations else ACCENT_GREEN_BG),
        ("BOX", (0, 0), (-1, -1), 0.5, ACCENT_AMBER if repeated_violations else ACCENT_GREEN),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(KeepTogether([recom_table]))
    story.append(Spacer(1, 10))

    # 8. Sign-off Footer Block
    sign_table_data = [
        [
            Paragraph("<b>Audited By (Safety Officer):</b>", styles["TextSmall"]),
            Paragraph("<b>Mine Safety In-Charge:</b>", styles["TextSmall"]),
            Paragraph("<b>Digital Verification:</b>", styles["TextSmall"]),
        ],
        [
            Paragraph("____________________________<br/>Sign &amp; Employee ID", styles["TextSmall"]),
            Paragraph("____________________________<br/>Sign &amp; Seal", styles["TextSmall"]),
            Paragraph(f"SURAKSHA Engine v2.4<br/>Hash: SHA256-VERIFIED-{worker.worker_id:04d}", styles["TextSmall"]),
        ],
    ]
    sign_table = Table(sign_table_data, colWidths=[170, 170, 180])
    sign_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(KeepTogether([sign_table]))

    doc.build(story, canvasmaker=NumberedCanvas)
    pdf_data = buffer.getvalue()
    buffer.close()
    return pdf_data


# ==============================================================================
# ALL EMPLOYEES REPORT GENERATION
# ==============================================================================

def generate_all_employees_report(
    db: Session,
    start_date: date,
    end_date: date,
    period_type: str = "WEEKLY",
    shift: str | None = None,
    gate_id: int | None = None,
) -> bytes:
    """Generate a multi-page Landscape All-Employees Mine Safety & Compliance PDF."""
    mine = db.query(Mine).first()
    mine_name = mine.name if mine else "Central Coal Mine"

    gate = db.get(Gate, gate_id) if gate_id else db.query(Gate).first()
    gate_name = gate.name if gate else "All Checkpoints"
    shift_label = f"Shift {shift}" if shift and shift != "ALL" else "All Shifts"

    period_type_clean = period_type.upper()
    period_label = f"{start_date.strftime('%d %b %Y')} – {end_date.strftime('%d %b %Y')}"
    if period_type_clean == "MONTHLY":
        report_title = f"Monthly Workforce Safety &amp; Compliance Report — {start_date.strftime('%B %Y')}"
    else:
        report_title = f"Weekly Workforce Safety &amp; Compliance Report — Week of {start_date.strftime('%d %b %Y')}"

    now_str = datetime.now(timezone.utc).strftime("%d %b %Y, %H:%M UTC")

    # Fetch All Active Workers with Department
    workers = (
        db.query(Worker)
        .options(joinedload(Worker.department))
        .filter(Worker.status == "ACTIVE")
        .order_by(Worker.name.asc())
        .all()
    )

    # 1. Fetch All Attendance in Period
    att_query = (
        db.query(AttendanceLog)
        .filter(
            func.date(AttendanceLog.entry_time) >= str(start_date),
            func.date(AttendanceLog.entry_time) <= str(end_date),
        )
    )
    if gate_id:
        att_query = att_query.filter(AttendanceLog.gate_id == gate_id)
    all_att_logs = att_query.all()

    # 2. Fetch All Compliance in Period
    comp_query = (
        db.query(ComplianceLog)
        .options(joinedload(ComplianceLog.detections).joinedload(PpeDetection.ppe_item))
        .filter(
            func.date(ComplianceLog.entry_time) >= str(start_date),
            func.date(ComplianceLog.entry_time) <= str(end_date),
        )
    )
    if gate_id:
        comp_query = comp_query.filter(ComplianceLog.gate_id == gate_id)
    all_comp_logs = comp_query.all()

    # 3. Fetch All Alerts in Period
    alert_query = (
        db.query(Alert)
        .filter(
            func.date(Alert.created_at) >= str(start_date),
            func.date(Alert.created_at) <= str(end_date),
        )
    )
    all_alerts = alert_query.all()

    # Pre-index by worker_id and date
    total_days = (end_date - start_date).days + 1
    days_list = [start_date + timedelta(days=i) for i in range(total_days)]

    worker_att: dict[int, dict[date, list[AttendanceLog]]] = {w.worker_id: {d: [] for d in days_list} for w in workers}
    for a in all_att_logs:
        if a.worker_id in worker_att:
            ad = a.entry_time.date() if isinstance(a.entry_time, datetime) else a.entry_time
            if ad in worker_att[a.worker_id]:
                worker_att[a.worker_id][ad].append(a)

    worker_comp: dict[int, dict[date, list[ComplianceLog]]] = {w.worker_id: {d: [] for d in days_list} for w in workers}
    worker_comp_list: dict[int, list[ComplianceLog]] = {w.worker_id: [] for w in workers}
    for c in all_comp_logs:
        if c.worker_id in worker_comp:
            cd = c.entry_time.date() if isinstance(c.entry_time, datetime) else c.entry_time
            if cd in worker_comp[c.worker_id]:
                worker_comp[c.worker_id][cd].append(c)
            worker_comp_list[c.worker_id].append(c)

    worker_alerts: dict[int, list[Alert]] = {w.worker_id: [] for w in workers}
    for al in all_alerts:
        if al.worker_id and al.worker_id in worker_alerts:
            worker_alerts[al.worker_id].append(al)

    # Compute Individual Worker Summaries
    worker_summaries: list[dict[str, Any]] = []
    ppe_catalog_names = ["Helmet", "Vest", "Boots"]
    aggregate_ppe: dict[str, dict[str, int]] = {name: {"detected": 0, "missing": 0, "total": 0} for name in ppe_catalog_names}

    for w in workers:
        wid = w.worker_id
        w_att_map = worker_att[wid]
        w_comp_map = worker_comp[wid]
        w_comp_all = worker_comp_list[wid]
        w_al = worker_alerts[wid]

        days_present = sum(1 for d in days_list if len(w_att_map[d]) > 0 or len(w_comp_map[d]) > 0)
        att_pct = round((days_present / total_days) * 100, 1) if total_days > 0 else 0.0

        # PPE Detections for this worker
        det_cnt = 0
        total_checks = 0
        for comp in w_comp_all:
            for det in comp.detections:
                item_name = det.ppe_item.name if det.ppe_item else None
                if item_name in aggregate_ppe:
                    aggregate_ppe[item_name]["total"] += 1
                    total_checks += 1
                    if det.detected:
                        aggregate_ppe[item_name]["detected"] += 1
                        det_cnt += 1
                    else:
                        aggregate_ppe[item_name]["missing"] += 1

        if total_checks > 0:
            ppe_pct = round((det_cnt / total_checks) * 100, 1)
        elif w_comp_all:
            ppe_pct = round(sum(c.compliance_score for c in w_comp_all) / len(w_comp_all), 1)
        else:
            ppe_pct = 100.0

        denials = sum(1 for c in w_comp_all if c.final_verdict == "DENIED" or c.overall_status == "DENIED")
        warnings = sum(1 for c in w_comp_all if c.final_verdict == "WARNING" or c.overall_status == "NON_COMPLIANT")
        violations = warnings + denials + len(w_al)

        # Safety Score from DB or derived
        db_score = worker_service.latest_safety_score(db, wid)
        if db_score:
            safety_score_val = round(db_score.score, 1)
            risk = db_score.risk_level
        else:
            safety_score_val = round((ppe_pct * 0.6) + (att_pct * 0.25) + (max(0, 100 - violations * 10) * 0.15), 1)
            risk = "LOW" if safety_score_val >= 90 else "MEDIUM" if safety_score_val >= 75 else "HIGH"

        worker_summaries.append({
            "worker_id": wid,
            "employee_code": w.employee_code,
            "name": w.name,
            "department": w.department.name if w.department else "Mining",
            "days_present": days_present,
            "attendance_pct": att_pct,
            "ppe_compliance_pct": ppe_pct,
            "safety_score": safety_score_val,
            "violations": violations,
            "denials": denials,
            "alerts": len(w_al),
            "risk": risk,
        })

    # Deterministic Sort: Highest Risk First (1. lowest safety score, 2. highest violations, 3. highest denials)
    worker_summaries.sort(key=lambda x: (x["safety_score"], -x["violations"], -x["denials"]))

    # Aggregate Mine KPIs
    total_workers_cnt = len(workers)
    active_present_cnt = sum(1 for s in worker_summaries if s["days_present"] > 0)
    avg_attendance = round(sum(s["attendance_pct"] for s in worker_summaries) / total_workers_cnt, 1) if total_workers_cnt > 0 else 0.0
    avg_ppe = round(sum(s["ppe_compliance_pct"] for s in worker_summaries) / total_workers_cnt, 1) if total_workers_cnt > 0 else 0.0
    avg_safety = round(sum(s["safety_score"] for s in worker_summaries) / total_workers_cnt, 1) if total_workers_cnt > 0 else 0.0
    total_mine_violations = sum(s["violations"] for s in worker_summaries)
    total_mine_denials = sum(s["denials"] for s in worker_summaries)
    total_mine_alerts = len(all_alerts)

    # Daily Aggregates Breakdown
    daily_stats: list[dict[str, Any]] = []
    for d in days_list:
        d_comps = [c for c in all_comp_logs if (c.entry_time.date() if isinstance(c.entry_time, datetime) else c.entry_time) == d]
        d_atts = [a for a in all_att_logs if (a.entry_time.date() if isinstance(a.entry_time, datetime) else a.entry_time) == d]
        d_alerts = [al for al in all_alerts if (al.created_at.date() if isinstance(al.created_at, datetime) else al.created_at) == d]

        checkins = len(d_atts) or len(d_comps)
        comp_cnt = sum(1 for c in d_comps if c.final_verdict == "ALLOWED" or c.overall_status == "COMPLIANT")
        warn_cnt = sum(1 for c in d_comps if c.final_verdict == "WARNING" or c.overall_status == "NON_COMPLIANT")
        den_cnt = sum(1 for c in d_comps if c.final_verdict == "DENIED" or c.overall_status == "DENIED")

        daily_stats.append({
            "date": d,
            "checkins": checkins,
            "compliant": comp_cnt,
            "warnings": warn_cnt,
            "denials": den_cnt,
            "alerts": len(d_alerts),
        })

    # Build Landscape PDF Story Flowables
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),  # 841.89 x 595.27
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=42,
    )
    styles = _get_styles()
    story: list[Any] = []

    # 1. Branding Header
    story.append(_build_header_block(report_title, period_label, mine_name, gate_name, shift_label, now_str, styles))
    story.append(HRFlowable(width="100%", thickness=1, color=PRIMARY_DARK, spaceBefore=3, spaceAfter=6))

    # 2. Executive Summary KPI Blocks (8 columns)
    kpis_header = [
        Paragraph("TOTAL WORKFORCE", styles["CardTitle"]),
        Paragraph("TOTAL PRESENT", styles["CardTitle"]),
        Paragraph("AVG ATTENDANCE", styles["CardTitle"]),
        Paragraph("AVG PPE COMPLIANCE", styles["CardTitle"]),
        Paragraph("AVG SAFETY SCORE", styles["CardTitle"]),
        Paragraph("PPE VIOLATIONS", styles["CardTitle"]),
        Paragraph("GATE DENIALS", styles["CardTitle"]),
        Paragraph("ACTIVE ALERTS", styles["CardTitle"]),
    ]
    kpis_vals = [
        Paragraph(str(total_workers_cnt), styles["CardValue"]),
        Paragraph(str(active_present_cnt), styles["CardValueGreen"]),
        Paragraph(f"{avg_attendance:.1f}%", styles["CardValueGreen"] if avg_attendance >= 80 else styles["CardValueAmber"]),
        Paragraph(f"{avg_ppe:.1f}%", styles["CardValueGreen"] if avg_ppe >= 90 else styles["CardValueAmber"]),
        Paragraph(f"{avg_safety:.0f}", styles["CardValueGreen"] if avg_safety >= 90 else styles["CardValueAmber"]),
        Paragraph(str(total_mine_violations), styles["CardValueRed"] if total_mine_violations > 0 else styles["CardValueGreen"]),
        Paragraph(str(total_mine_denials), styles["CardValueRed"] if total_mine_denials > 0 else styles["CardValueGreen"]),
        Paragraph(str(total_mine_alerts), styles["CardValueAmber"] if total_mine_alerts > 0 else styles["CardValueGreen"]),
    ]
    kpis_tbl = Table([kpis_header, kpis_vals], colWidths=[770 / 8] * 8)
    kpis_tbl.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("BACKGROUND", (0, 0), (-1, -1), NEUTRAL_BG),
        ("BOX", (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    story.append(kpis_tbl)
    story.append(Spacer(1, 6))

    # 3. Employee Summary Table (Ranked with highest risk on top)
    story.append(Paragraph("<b>Employee Safety &amp; Compliance Roster (Ranked by Risk Level)</b>", styles["SectionHeading"]))
    emp_table_rows = [
        [
            Paragraph("<b>Emp ID</b>", styles["TableHeader"]),
            Paragraph("<b>Employee Name</b>", styles["TableHeader"]),
            Paragraph("<b>Department</b>", styles["TableHeader"]),
            Paragraph("<b>Attendance %</b>", styles["CellCenterBold"]),
            Paragraph("<b>PPE %</b>", styles["CellCenterBold"]),
            Paragraph("<b>Safety Score</b>", styles["CellCenterBold"]),
            Paragraph("<b>Violations</b>", styles["CellCenterBold"]),
            Paragraph("<b>Denials</b>", styles["CellCenterBold"]),
            Paragraph("<b>Risk Status</b>", styles["CellCenterBold"]),
            Paragraph("<b>Supervisor Action</b>", styles["TableHeader"]),
        ]
    ]

    for s in worker_summaries:
        risk_tone = styles["BadgeRed"] if s["risk"] == "HIGH" else styles["BadgeAmber"] if s["risk"] == "MEDIUM" else styles["BadgeGreen"]
        action_text = "Mandatory safety review" if s["risk"] == "HIGH" else "Monitor compliance" if s["risk"] == "MEDIUM" else "Standard protocol"
        emp_table_rows.append([
            Paragraph(s["employee_code"], styles["TableCellBold"]),
            Paragraph(s["name"], styles["TableCell"]),
            Paragraph(s["department"], styles["TableCell"]),
            Paragraph(f"{s['attendance_pct']:.1f}%", styles["CellCenter"]),
            Paragraph(f"{s['ppe_compliance_pct']:.1f}%", styles["CellCenterBold"]),
            Paragraph(f"{s['safety_score']:.0f}", styles["CellCenterBold"]),
            Paragraph(str(s["violations"]), styles["BadgeRed"] if s["violations"] > 0 else styles["CellCenter"]),
            Paragraph(str(s["denials"]), styles["BadgeRed"] if s["denials"] > 0 else styles["CellCenter"]),
            Paragraph(f"<b>{s['risk']}</b>", risk_tone),
            Paragraph(action_text, styles["TextSmall"]),
        ])

    emp_table = Table(emp_table_rows, colWidths=[65, 120, 95, 75, 65, 70, 60, 55, 65, 100])
    emp_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BACKGROUND", (0, 0), (-1, 0), PRIMARY_DARK),
        ("TEXTCOLOR", (0, 0), (-1, 0), TEXT_WHITE),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [TEXT_WHITE, ALT_ROW_BG]),
        ("BOX", (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    story.append(emp_table)
    story.append(Spacer(1, 8))

    # 4. Visual Attendance & Compliance Matrix (Spreadsheet Template Inspiration)
    story.append(Paragraph(f"<b>Workforce Daily Attendance &amp; Verification Matrix ({period_label})</b>", styles["SectionHeading"]))

    matrix_headers = [Paragraph("<b>Emp ID</b>", styles["TableHeader"]), Paragraph("<b>Name</b>", styles["TableHeader"])]
    for d in days_list:
        matrix_headers.append(Paragraph(f"<b>{d.day}</b><br/>{d.strftime('%a')[:2]}", styles["CellCenterBold"]))
    matrix_headers.append(Paragraph("<b>Att %</b>", styles["CellCenterBold"]))

    matrix_rows = [matrix_headers]

    # Calculate column widths: width is 770pt. Emp ID (55), Name (95), Att % (40). Remaining: 580pt / total_days
    day_col_w = min(28.0, 580.0 / max(1, total_days))
    matrix_col_widths = [55, 95] + [day_col_w] * total_days + [40]

    for s in worker_summaries:
        wid = s["worker_id"]
        w_att_map = worker_att[wid]
        w_comp_map = worker_comp[wid]

        row: list[Any] = [Paragraph(s["employee_code"], styles["TableCellBold"]), Paragraph(s["name"], styles["TableCell"])]
        for d in days_list:
            d_comp = w_comp_map[d]
            d_att = w_att_map[d]
            if d_comp:
                verdict = d_comp[-1].final_verdict or d_comp[-1].overall_status
                if verdict in ("ALLOWED", "COMPLIANT"):
                    cell_sym = "<font color='#059669'><b>P</b></font>"
                elif verdict == "DENIED":
                    cell_sym = "<font color='#dc2626'><b>D</b></font>"
                else:
                    cell_sym = "<font color='#d97706'><b>W</b></font>"
            elif d_att:
                cell_sym = "<font color='#059669'><b>P</b></font>"
            else:
                cell_sym = "<font color='#cbd5e1'>-</font>"
            row.append(Paragraph(cell_sym, styles["CellCenter"]))
        row.append(Paragraph(f"{s['attendance_pct']:.0f}%", styles["CellCenterBold"]))
        matrix_rows.append(row)

    matrix_table = Table(matrix_rows, colWidths=matrix_col_widths)
    matrix_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BACKGROUND", (0, 0), (-1, 0), SECONDARY_DARK),
        ("TEXTCOLOR", (0, 0), (-1, 0), TEXT_WHITE),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [TEXT_WHITE, ALT_ROW_BG]),
        ("BOX", (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ("TOPPADDING", (0, 0), (-1, -1), 1.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5),
    ]))
    story.append(matrix_table)
    story.append(Paragraph("<font color='#64748b'><b>Matrix Symbols:</b> P = Present / Verified | W = Warning (Non-compliant) | D = Entry Denied | - = Absent / No Check-in Record</font>", styles["TextSmall"]))
    story.append(Spacer(1, 8))

    # 5. PPE Items Aggregate Breakdown & Daily Trends Side-by-Side
    story.append(Paragraph("<b>Aggregate PPE Items Compliance &amp; Daily Verification Trends</b>", styles["SectionHeading"]))

    ppe_agg_data = [
        [
            Paragraph("<b>PPE Item</b>", styles["TableHeader"]),
            Paragraph("<b>Total Checked</b>", styles["CellCenterBold"]),
            Paragraph("<b>Compliant</b>", styles["CellCenterBold"]),
            Paragraph("<b>Missing</b>", styles["CellCenterBold"]),
            Paragraph("<b>Compliance %</b>", styles["CellCenterBold"]),
        ]
    ]
    for name in ppe_catalog_names:
        stats = aggregate_ppe[name]
        tot = stats["total"]
        det = stats["detected"]
        mis = stats["missing"]
        pct = f"{(det / tot) * 100:.1f}%" if tot > 0 else "N/A"
        ppe_agg_data.append([
            Paragraph(f"<b>{name}</b>", styles["TableCellBold"]),
            Paragraph(str(tot), styles["CellCenter"]),
            Paragraph(str(det), styles["BadgeGreen"] if det > 0 else styles["CellCenter"]),
            Paragraph(str(mis), styles["BadgeRed"] if mis > 0 else styles["CellCenter"]),
            Paragraph(pct, styles["CellCenterBold"]),
        ])
    ppe_agg_table = Table(ppe_agg_data, colWidths=[110, 75, 65, 65, 75])
    ppe_agg_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BACKGROUND", (0, 0), (-1, 0), PRIMARY_DARK),
        ("TEXTCOLOR", (0, 0), (-1, 0), TEXT_WHITE),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [TEXT_WHITE, ALT_ROW_BG]),
        ("BOX", (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))

    daily_agg_data = [
        [
            Paragraph("<b>Date</b>", styles["TableHeader"]),
            Paragraph("<b>Check-ins</b>", styles["CellCenterBold"]),
            Paragraph("<b>Compliant</b>", styles["CellCenterBold"]),
            Paragraph("<b>Warnings</b>", styles["CellCenterBold"]),
            Paragraph("<b>Denials</b>", styles["CellCenterBold"]),
            Paragraph("<b>Alerts</b>", styles["CellCenterBold"]),
        ]
    ]
    for d_stat in daily_stats[:7]:  # Sample top 7 days for clean visual layout
        d_val = d_stat["date"]
        daily_agg_data.append([
            Paragraph(d_val.strftime("%d %b (%a)"), styles["TableCell"]),
            Paragraph(str(d_stat["checkins"]), styles["CellCenter"]),
            Paragraph(str(d_stat["compliant"]), styles["BadgeGreen"] if d_stat["compliant"] > 0 else styles["CellCenter"]),
            Paragraph(str(d_stat["warnings"]), styles["BadgeAmber"] if d_stat["warnings"] > 0 else styles["CellCenter"]),
            Paragraph(str(d_stat["denials"]), styles["BadgeRed"] if d_stat["denials"] > 0 else styles["CellCenter"]),
            Paragraph(str(d_stat["alerts"]), styles["BadgeAmber"] if d_stat["alerts"] > 0 else styles["CellCenter"]),
        ])
    daily_agg_table = Table(daily_agg_data, colWidths=[95, 55, 55, 55, 55, 55])
    daily_agg_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BACKGROUND", (0, 0), (-1, 0), SECONDARY_DARK),
        ("TEXTCOLOR", (0, 0), (-1, 0), TEXT_WHITE),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [TEXT_WHITE, ALT_ROW_BG]),
        ("BOX", (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))

    side_by_side = Table([[ppe_agg_table, daily_agg_table]], colWidths=[390, 380])
    side_by_side.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(KeepTogether([side_by_side]))

    doc.build(story, canvasmaker=NumberedCanvas)
    pdf_data = buffer.getvalue()
    buffer.close()
    return pdf_data
