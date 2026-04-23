import os
import uuid
from datetime import datetime
from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table,
    TableStyle, HRFlowable, PageBreak,
)
from auditmind.orchestrator.state import Finding, RepoContext, Severity
from auditmind.synthesis.scorer import (
    compute_risk_score,
    findings_by_agent,
    rank_findings,
)
from auditmind.config import settings
from auditmind.logger import get_logger

logger = get_logger(__name__)

# --- color palette ---
COLOR_CRITICAL = colors.HexColor("#C0392B")
COLOR_HIGH     = colors.HexColor("#E67E22")
COLOR_MEDIUM   = colors.HexColor("#F1C40F")
COLOR_LOW      = colors.HexColor("#27AE60")
COLOR_INFO     = colors.HexColor("#2980B9")
COLOR_DARK     = colors.HexColor("#1A1A2E")
COLOR_LIGHT    = colors.HexColor("#F8F9FA")
COLOR_BORDER   = colors.HexColor("#DEE2E6")

SEVERITY_COLORS = {
    Severity.CRITICAL: COLOR_CRITICAL,
    Severity.HIGH:     COLOR_HIGH,
    Severity.MEDIUM:   COLOR_MEDIUM,
    Severity.LOW:      COLOR_LOW,
    Severity.INFO:     COLOR_INFO,
}


def generate_pdf(
    audit_id: str,
    repo_context: RepoContext,
    findings: list[Finding],
    severity_counts: dict[str, int],
    executive_summary: str,
) -> str:
    """
    Generates a professional PDF audit report.
    Returns the file path of the generated PDF.
    """
    os.makedirs(settings.report_output_dir, exist_ok=True)
    output_path = os.path.join(
        settings.report_output_dir,
        f"auditmind_{repo_context.repo_name}_{audit_id[:8]}.pdf"
    )

    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        leftMargin=2*cm,
        rightMargin=2*cm,
        topMargin=2*cm,
        bottomMargin=2*cm,
    )

    styles = _build_styles()
    story = []

    # --- cover section ---
    story += _build_cover(repo_context, audit_id, findings, styles)
    story.append(PageBreak())

    # --- executive summary ---
    story += _build_executive_summary(executive_summary, styles)
    story.append(Spacer(1, 0.5*cm))

    # --- severity breakdown table ---
    story += _build_severity_table(severity_counts, findings, styles)
    story.append(PageBreak())

    # --- findings by agent ---
    by_agent = findings_by_agent(rank_findings(findings))
    for agent_name, agent_findings in by_agent.items():
        story += _build_agent_section(agent_name, agent_findings, styles)
        story.append(Spacer(1, 0.4*cm))

    doc.build(story)
    logger.info(f"PDF report generated: {output_path}")
    return output_path


def _build_styles() -> dict:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "title",
            fontSize=28,
            fontName="Helvetica-Bold",
            textColor=COLOR_DARK,
            spaceAfter=8,
        ),
        "subtitle": ParagraphStyle(
            "subtitle",
            fontSize=14,
            fontName="Helvetica",
            textColor=colors.HexColor("#6C757D"),
            spaceAfter=4,
        ),
        "section_heading": ParagraphStyle(
            "section_heading",
            fontSize=16,
            fontName="Helvetica-Bold",
            textColor=COLOR_DARK,
            spaceBefore=12,
            spaceAfter=8,
        ),
        "agent_heading": ParagraphStyle(
            "agent_heading",
            fontSize=13,
            fontName="Helvetica-Bold",
            textColor=COLOR_DARK,
            spaceBefore=10,
            spaceAfter=6,
        ),
        "finding_title": ParagraphStyle(
            "finding_title",
            fontSize=11,
            fontName="Helvetica-Bold",
            textColor=COLOR_DARK,
            spaceAfter=3,
        ),
        "body": ParagraphStyle(
            "body",
            fontSize=10,
            fontName="Helvetica",
            textColor=colors.HexColor("#343A40"),
            spaceAfter=4,
            leading=14,
        ),
        "recommendation": ParagraphStyle(
            "recommendation",
            fontSize=10,
            fontName="Helvetica-Oblique",
            textColor=colors.HexColor("#155724"),
            spaceAfter=6,
            leading=14,
        ),
        "meta": ParagraphStyle(
            "meta",
            fontSize=9,
            fontName="Helvetica",
            textColor=colors.HexColor("#6C757D"),
            spaceAfter=2,
        ),
    }

def _build_cover(
    repo_context: RepoContext,
    audit_id: str,
    findings: list[Finding],
    styles: dict,
) -> list:
    risk_score = compute_risk_score(findings)
    risk_label = (
        "CRITICAL RISK" if risk_score >= 80 else
        "HIGH RISK"     if risk_score >= 50 else
        "MODERATE RISK" if risk_score >= 25 else
        "LOW RISK"
    )
    risk_color = (
        COLOR_CRITICAL if risk_score >= 80 else
        COLOR_HIGH     if risk_score >= 50 else
        COLOR_MEDIUM   if risk_score >= 25 else
        COLOR_LOW
    )

    elements = [
        Spacer(1, 1*cm),
        Paragraph("AuditMind", styles["title"]),
        Paragraph("Autonomous Code &amp; Infrastructure Audit Report", styles["subtitle"]),
        HRFlowable(width="100%", thickness=2, color=COLOR_DARK, spaceAfter=16),
        Spacer(1, 0.5*cm),

        Paragraph(f"Repository: {repo_context.repo_name}", styles["section_heading"]),
        Paragraph(f"URL: {repo_context.repo_url}", styles["body"]),
        Paragraph(
            f"Audit ID: {audit_id}",
            styles["meta"],
        ),
        Paragraph(
            f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
            styles["meta"],
        ),
        Paragraph(
            f"Total files scanned: "
            f"{len(repo_context.python_files) + len(repo_context.yaml_files) + len(repo_context.terraform_files) + len(repo_context.docker_files)} "
            f"| {repo_context.total_lines:,} lines",
            styles["meta"],
        ),
        Spacer(1, 1*cm),

        # risk score badge
        Table(
            [[f"Risk Score: {risk_score}/100   {risk_label}"]],
            colWidths=["100%"],
            style=TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), risk_color),
                ("TEXTCOLOR",  (0, 0), (-1, -1), colors.white),
                ("FONTNAME",   (0, 0), (-1, -1), "Helvetica-Bold"),
                ("FONTSIZE",   (0, 0), (-1, -1), 18),
                ("ALIGN",      (0, 0), (-1, -1), "CENTER"),
                ("TOPPADDING",    (0, 0), (-1, -1), 16),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 16),
                ("ROUNDEDCORNERS", [8]),
            ]),
        ),
    ]
    return elements


def _build_executive_summary(summary: str, styles: dict) -> list:
    return [
        Paragraph("Executive Summary", styles["section_heading"]),
        HRFlowable(width="100%", thickness=0.5, color=COLOR_BORDER, spaceAfter=8),
        Paragraph(summary.replace("\n", "<br/>"), styles["body"]),
    ]


def _build_severity_table(
    severity_counts: dict[str, int],
    findings: list[Finding],
    styles: dict,
) -> list:
    data = [["Severity", "Count", "Agent Breakdown"]]

    for severity in ["critical", "high", "medium", "low", "info"]:
        count = severity_counts.get(severity, 0)
        if count == 0:
            continue

        # agent breakdown for this severity
        sev_enum = Severity(severity)
        agents = {}
        for f in findings:
            if f.severity == sev_enum:
                agents[f.agent] = agents.get(f.agent, 0) + 1
        agent_str = "  ".join(f"{a}: {c}" for a, c in agents.items())

        data.append([severity.upper(), str(count), agent_str])

    color_map = {
        "CRITICAL": COLOR_CRITICAL,
        "HIGH":     COLOR_HIGH,
        "MEDIUM":   COLOR_MEDIUM,
        "LOW":      COLOR_LOW,
        "INFO":     COLOR_INFO,
    }

    table_style = [
        ("BACKGROUND",  (0, 0), (-1, 0),  COLOR_DARK),
        ("TEXTCOLOR",   (0, 0), (-1, 0),  colors.white),
        ("FONTNAME",    (0, 0), (-1, 0),  "Helvetica-Bold"),
        ("FONTSIZE",    (0, 0), (-1, -1), 10),
        ("ALIGN",       (0, 0), (-1, -1), "LEFT"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [COLOR_LIGHT, colors.white]),
        ("GRID",        (0, 0), (-1, -1), 0.5, COLOR_BORDER),
        ("TOPPADDING",    (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING",   (0, 0), (-1, -1), 10),
    ]

    # color the severity column cells
    for i, row in enumerate(data[1:], start=1):
        sev = row[0]
        if sev in color_map:
            table_style.append(
                ("TEXTCOLOR", (0, i), (0, i), color_map[sev])
            )
            table_style.append(
                ("FONTNAME", (0, i), (0, i), "Helvetica-Bold")
            )

    return [
        Paragraph("Findings Summary", styles["section_heading"]),
        HRFlowable(width="100%", thickness=0.5, color=COLOR_BORDER, spaceAfter=8),
        Table(
            data,
            colWidths=[3.5*cm, 2*cm, 11*cm],
            style=TableStyle(table_style),
        ),
    ]


def _build_agent_section(
    agent_name: str,
    findings: list[Finding],
    styles: dict,
) -> list:
    elements = [
        Paragraph(
            f"{agent_name.upper()} AGENT — {len(findings)} findings",
            styles["agent_heading"],
        ),
        HRFlowable(width="100%", thickness=0.5, color=COLOR_BORDER, spaceAfter=6),
    ]

    for f in findings:
        sev_color = SEVERITY_COLORS.get(f.severity, COLOR_INFO)

        badge_table = Table(
            [[f.severity.value.upper(), f.title]],
            colWidths=[2.2*cm, 14*cm],
            style=TableStyle([
                ("BACKGROUND", (0, 0), (0, 0), sev_color),
                ("TEXTCOLOR",  (0, 0), (0, 0), colors.white),
                ("FONTNAME",   (0, 0), (0, 0), "Helvetica-Bold"),
                ("FONTNAME",   (1, 0), (1, 0), "Helvetica-Bold"),
                ("FONTSIZE",   (0, 0), (-1, -1), 9),
                ("ALIGN",      (0, 0), (0, 0), "CENTER"),
                ("TOPPADDING",    (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING",   (1, 0), (1, 0), 8),
            ]),
        )
        elements.append(badge_table)

        # description
        elements.append(
            Paragraph(f.description, styles["body"])
        )

        # file + line
        if f.file_path:
            loc = f.file_path
            if f.line_number:
                loc += f" : line {f.line_number}"
            elements.append(Paragraph(f"📄 {loc}", styles["meta"]))

        # recommendation
        if f.recommendation:
            elements.append(
                Paragraph(f"→ {f.recommendation}", styles["recommendation"])
            )

        elements.append(
            HRFlowable(width="100%", thickness=0.3, color=COLOR_BORDER, spaceAfter=4)
        )

    return elements