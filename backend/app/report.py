"""Full compliance audit report → PDF (reportlab).

Composes company + parties, KYC/DVO results, risk + escalation, lease, R&L
decision, per-stage reasoning/insights, final verdict, and the action log.
"""
from __future__ import annotations

import io
from datetime import datetime
from typing import Any, Optional

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable, ListFlowable, ListItem, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)

ACCENT = colors.HexColor("#574fcf")
MUTED = colors.HexColor("#6b6b85")
_STAGE_TITLES = {"dvo": "DVO — Document Verification", "compliance": "Compliance & Risk",
                 "lease": "Lease (CRM)", "rnl": "Registry & Licensing"}
_VERDICT = {"license_issued": "LICENSE ISSUED", "flagged": "FLAGGED AT DVO", "blocked": "BLOCKED AT R&L"}


def _styles():
    ss = getSampleStyleSheet()
    ss.add(ParagraphStyle("H", fontName="Helvetica-Bold", fontSize=18, textColor=ACCENT, spaceAfter=2))
    ss.add(ParagraphStyle("Sub", fontName="Helvetica", fontSize=9, textColor=MUTED, spaceAfter=8))
    ss.add(ParagraphStyle("Sec", fontName="Helvetica-Bold", fontSize=12, textColor=colors.HexColor("#1e1b33"),
                          spaceBefore=10, spaceAfter=4))
    ss.add(ParagraphStyle("Body", fontName="Helvetica", fontSize=9.5, leading=13, alignment=TA_LEFT))
    ss.add(ParagraphStyle("Muted", fontName="Helvetica", fontSize=8.5, textColor=MUTED, leading=12))
    ss.add(ParagraphStyle("Bul", fontName="Helvetica", fontSize=9, leading=12))
    return ss


def _kv_table(rows: list[tuple[str, Any]], s) -> Table:
    data = [[Paragraph(f"<font color='#6b6b85'>{k}</font>", s["Muted"]),
             Paragraph(str(v if v not in (None, "") else "—"), s["Body"])] for k, v in rows]
    t = Table(data, colWidths=[45 * mm, 120 * mm])
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"),
                           ("BOTTOMPADDING", (0, 0), (-1, -1), 3), ("TOPPADDING", (0, 0), (-1, -1), 3),
                           ("LINEBELOW", (0, 0), (-1, -1), 0.3, colors.HexColor("#e7e7ef"))]))
    return t


def build_audit_report(*, company, people, pvs, run, lease, license, audit) -> bytes:
    s = _styles()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=18 * mm, bottomMargin=16 * mm,
                            leftMargin=18 * mm, rightMargin=18 * mm, title=f"Audit Report {company.sr}")
    E: list = []

    E.append(Paragraph("Compliance Audit Report", s["H"]))
    E.append(Paragraph(f"{company.name} &nbsp;·&nbsp; {company.sr} &nbsp;·&nbsp; "
                       f"generated {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}", s["Sub"]))
    final_status = run.status if run else "not_run"
    verdict = _VERDICT.get(final_status, final_status.replace("_", " ").upper())
    E.append(Table([[Paragraph(f"<b>Final verdict:</b> {verdict}", s["Body"])]],
                   colWidths=[165 * mm],
                   style=TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f2f1fb")),
                                     ("BOX", (0, 0), (-1, -1), 0.5, ACCENT),
                                     ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                                     ("LEFTPADDING", (0, 0), (-1, -1), 8)])))
    E.append(Spacer(1, 6))

    # Entity
    E.append(Paragraph("Entity", s["Sec"]))
    E.append(_kv_table([("Company type", company.company_type), ("Activity", company.activity),
                        ("Activity class", company.activity_class), ("Risk tier", company.risk_tier),
                        ("Jurisdiction", company.jurisdiction), ("Package", company.package),
                        ("Visa quota", company.visa_quota), ("Premium", "Yes" if company.premium else "No"),
                        ("Token issuing", "Yes" if company.token_issuing else "No"),
                        ("Pre-approval", company.preapproval_status or "—")], s))

    # Parties + KYC
    E.append(Paragraph("Parties & KYC", s["Sec"]))
    pv_by = {pv.person_name: pv for pv in pvs}
    for p in people:
        pv = pv_by.get(p.name)
        verdict_p = (pv.overall if pv else "not verified")
        E.append(Paragraph(f"<b>{p.name}</b> — {p.role} &nbsp; "
                           f"<font color='{'#0f766e' if verdict_p == 'verified' else '#b45309'}'>[{verdict_p}]</font>",
                           s["Body"]))
        if pv:
            c = pv.checks or {}
            E.append(Paragraph(f"passport expiry {c.get('expiry','—')} ({'ok' if c.get('expiry_ok') else 'FAIL'}) · "
                               f"PoA {c.get('poa_date','—')} ({'ok' if c.get('poa_ok') else 'FAIL'}) · "
                               f"face score {pv.face_match_score} ({'ok' if c.get('face_passed') else 'FAIL'})",
                               s["Muted"]))
    E.append(Spacer(1, 4))

    # Stages
    if run and run.stages:
        E.append(Paragraph("Compliance stages", s["Sec"]))
        for st in run.stages:
            d = st.detail or {}
            E.append(HRFlowable(width="100%", thickness=0.4, color=colors.HexColor("#e7e7ef"), spaceBefore=4, spaceAfter=4))
            E.append(Paragraph(f"<b>{_STAGE_TITLES.get(st.stage, st.stage)}</b> — "
                               f"{st.decision.replace('_', ' ')}", s["Body"]))
            an = d.get("analysis") or {}
            if an.get("reasoning"):
                E.append(Paragraph(an["reasoning"], s["Muted"]))
            if an.get("insights"):
                E.append(ListFlowable([ListItem(Paragraph(i, s["Bul"]), leftIndent=6) for i in an["insights"]],
                                      bulletType="bullet", start="•", leftIndent=10))
            docs = d.get("documents") or []
            if docs:
                E.append(Paragraph("Documents reviewed: " +
                                   ", ".join(f"{x['doc_key']} ({x.get('status','?')})" for x in docs), s["Muted"]))

    # Lease / License
    if lease:
        E.append(Paragraph("Lease", s["Sec"]))
        E.append(_kv_table([("Package", lease.package), ("Term", lease.term), ("Fee", lease.fee),
                            ("Visa quota", lease.visa_quota), ("CRM ref", lease.crm_ref)], s))
    if license:
        E.append(Paragraph("Licence", s["Sec"]))
        E.append(_kv_table([("Certificate", license.cert_no), ("Licence no.", license.license_no),
                            ("Establishment card", license.establishment_card_no),
                            ("Documents visible", "Yes" if license.documents_visible else "No")], s))

    # Action log
    if audit:
        E.append(Paragraph("Action log", s["Sec"]))
        for a in audit:
            ts = a.get("created_at")
            ts = ts.strftime("%Y-%m-%d %H:%M:%S") if isinstance(ts, datetime) else str(ts)
            E.append(Paragraph(f"<font color='#6b6b85'>{ts}</font> &nbsp; "
                               f"<b>{a.get('action')}</b> &nbsp; <font color='#6b6b85'>{a.get('actor','')}</font>",
                               s["Muted"]))

    doc.build(E)
    return buf.getvalue()
