"""
PDF proposal generator.

Builds a sleek, executive-facing cost proposal from an already-computed
EstimateResult: cover + executive summary, recommended architecture, a
single consolidated cost breakdown (table + category totals + grand totals
+ chart), and - only when there's something to say - assumptions,
configuration review, and savings sections. Like the Excel generator, this
module only renders an already-computed EstimateResult and never invents or
recalculates a price.

Design invariants enforced throughout this file:
  - Every table cell whose content length is unbounded (resource/service
    names, requested/used configuration values, reasons, explanations) is
    wrapped in a Paragraph, so ReportLab wraps the text and auto-sizes the
    row height instead of letting it overflow into a neighboring cell. Cells
    with a short, bounded vocabulary (status/severity labels, quantities,
    currency amounts) are left as plain strings where that's what lets a
    TableStyle command (TEXTCOLOR, FONTNAME) style them per-row - those
    commands only affect plain-string cells, not Paragraph flowables, so
    wrapping them would silently break the existing color/bold-row styling
    for no wrapping benefit (all their content is already short).
  - Every table declares explicit colWidths summing to at most ~17.2cm
    (A4's 21cm width minus the 1.8cm left/right margins below).
  - Sections with nothing to report (no assumptions, no validation findings,
    no savings opportunities) are omitted entirely rather than rendered as
    an empty/placeholder heading - see `generate()`.
"""
import io
from datetime import datetime, timezone

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics.shapes import Drawing
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.domain.assumption import humanize_field_code
from app.domain.branding import BrandingConfig
from app.domain.estimate import EstimateResult
from app.domain.explanation import EstimateExplanation

SEVERITY_COLORS = {
    "blocker": colors.HexColor("#D93025"),
    "warning": colors.HexColor("#B06000"),
    "info": colors.HexColor("#188038"),
}
SEVERITY_LABELS = {"blocker": "Needs Attention", "warning": "Worth Reviewing"}

# Usable content width on an A4 page with 1.8cm left/right margins
# (21cm - 1.8cm - 1.8cm). Every table's colWidths must sum to at most this.
_USABLE_WIDTH_CM = 21 - 1.8 - 1.8


class PdfReportGenerator:
    def generate(
        self, estimate: EstimateResult, branding: BrandingConfig | None = None,
        explanation: EstimateExplanation | None = None,
    ) -> bytes:
        branding = branding or BrandingConfig()
        accent = colors.HexColor(f"#{branding.primary_color_hex}")
        styles = self._build_styles(accent)

        buf = io.BytesIO()
        doc = SimpleDocTemplate(
            buf, pagesize=A4,
            topMargin=1.8 * cm, bottomMargin=1.8 * cm, leftMargin=1.8 * cm, rightMargin=1.8 * cm,
            title=f"{estimate.project_name} - Cost Estimate Proposal",
            author=branding.company_name,
        )

        findings = [r for r in estimate.validation.results if r.severity.value in ("warning", "blocker")]
        savings_items = self._savings_items(estimate)
        # "Clean" is about the customer's own request needing no adjustment
        # and raising no flags - NOT about savings_items, which almost
        # always has at least an automatically-applied Sustained/Committed
        # Use Discount line even for a perfectly-matched request. A discount
        # notice is good news, not a warning, so it shouldn't gate the badge
        # off; it's still shown in its own Savings section whenever present,
        # badge or no badge.
        fully_clean = not estimate.assumptions and not findings

        # No forced PageBreaks anywhere below - content flows naturally and
        # only spills onto another page when it genuinely doesn't fit, which
        # is what keeps a straightforward estimate to one or two pages
        # instead of the fixed ~7-page skeleton this used to always produce.
        story = []
        story += self._cover_and_executive_summary(estimate, branding, styles, accent, explanation)
        story.append(Spacer(1, 10))
        if fully_clean:
            story.append(self._validation_status_badge(styles))
            story.append(Spacer(1, 14))
        story += self._architecture_section(estimate, styles, accent)
        story.append(Spacer(1, 12))
        story += self._cost_breakdown_section(estimate, styles, accent)
        if estimate.assumptions:
            story.append(Spacer(1, 14))
            story += self._assumptions_section(estimate, styles, accent, explanation)
        if findings:
            story.append(Spacer(1, 14))
            story += self._validation_section(findings, styles, accent)
        if savings_items:
            story.append(Spacer(1, 14))
            story += self._savings_section(savings_items, styles)
        story.append(Spacer(1, 16))
        story += self._signature_section(branding, styles)

        doc.build(story, onFirstPage=self._footer(branding), onLaterPages=self._footer(branding))
        return buf.getvalue()

    # -- styling ------------------------------------------------------------

    def _build_styles(self, accent):
        styles = getSampleStyleSheet()
        styles.add(ParagraphStyle("H1Accent", parent=styles["Heading1"], textColor=accent, spaceAfter=10))
        styles.add(ParagraphStyle("H2Accent", parent=styles["Heading2"], textColor=accent, spaceBefore=14, spaceAfter=8))
        styles.add(ParagraphStyle("BodySmall", parent=styles["BodyText"], fontSize=9, leading=12))
        styles.add(ParagraphStyle("CoverTitle", parent=styles["Title"], textColor=accent, fontSize=26))
        styles.add(ParagraphStyle("MetricLabel", parent=styles["BodyText"], fontSize=9, textColor=colors.grey))
        styles.add(ParagraphStyle("MetricValue", parent=styles["Heading2"], textColor=accent, spaceAfter=0))
        styles.add(ParagraphStyle("BadgeText", parent=styles["BodyText"], fontName="Helvetica-Bold", textColor=colors.HexColor("#188038")))
        return styles

    def _cell(self, value, styles, style_name: str = "BodySmall") -> Paragraph:
        """Wraps a table-cell value in a Paragraph (unless it already is
        one) so ReportLab wraps long text and auto-sizes the row height -
        see the module docstring for which cells this is and isn't used
        for."""
        if isinstance(value, Paragraph):
            return value
        return Paragraph(str(value), styles[style_name])

    def _footer(self, branding: BrandingConfig):
        def _draw(canvas, doc):
            canvas.saveState()
            font_name, font_size = "Helvetica", 7
            canvas.setFont(font_name, font_size)
            canvas.setFillColor(colors.grey)

            left_x = 1.8 * cm
            right_x = A4[0] - 1.8 * cm
            page_label = f"Page {doc.page}"
            page_label_width = stringWidth(page_label, font_name, font_size)
            gap = 0.4 * cm
            max_note_width = (right_x - left_x) - page_label_width - gap

            note = self._truncate_to_width(branding.footer_note.strip(), font_name, font_size, max_note_width)
            canvas.drawString(left_x, 1.2 * cm, note)
            canvas.drawRightString(right_x, 1.2 * cm, page_label)
            canvas.restoreState()
        return _draw

    def _truncate_to_width(self, text: str, font_name: str, font_size: float, max_width: float) -> str:
        """Truncates `text` (appending "...") so its rendered width at
        `font_name`/`font_size` never exceeds `max_width` - measured by
        actual glyph width (stringWidth), not character count. A fixed
        `text[:140]` slice can still overflow past the margin for a wide
        string, and just as often cuts the text far short of where it would
        actually still fit; measuring the real rendered width is what
        guarantees the footer note plus page number never overlaps or gets
        clipped at the page edge. Returns `text` unchanged if it already
        fits."""
        if stringWidth(text, font_name, font_size) <= max_width:
            return text
        ellipsis = "..."
        ellipsis_width = stringWidth(ellipsis, font_name, font_size)
        while text and stringWidth(text, font_name, font_size) + ellipsis_width > max_width:
            text = text[:-1]
        return text.rstrip() + ellipsis

    # -- cover / executive summary -------------------------------------------

    def _cover_and_executive_summary(
        self, estimate: EstimateResult, branding: BrandingConfig, styles, accent,
        explanation: EstimateExplanation | None = None,
    ):
        flow = []
        flow.append(Spacer(1, 30))
        flow.append(Paragraph(branding.company_name, styles["CoverTitle"]))
        flow.append(Paragraph("Google Cloud FinOps Cost Estimate Proposal", styles["Heading2"]))
        flow.append(Spacer(1, 14))
        flow.append(HRFlowable(width="100%", color=accent, thickness=1.2))
        flow.append(Spacer(1, 14))

        meta_rows = [
            ["Project", self._cell(estimate.project_name, styles)],
            ["Prepared For", self._cell(branding.prepared_for or "-", styles)],
            ["Prepared By", self._cell(branding.prepared_by, styles)],
            ["Region", self._cell(estimate.normalized_spec.region, styles)],
            ["Normalization Strategy", estimate.strategy_used.capitalize()],
            ["Date", datetime.now(timezone.utc).strftime("%Y-%m-%d")],
            ["Estimate ID", self._cell(estimate.estimate_id, styles)],
        ]
        meta_table = Table(meta_rows, colWidths=[5 * cm, 10 * cm])
        meta_table.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#444444")),
        ]))
        flow.append(meta_table)
        flow.append(Spacer(1, 18))

        flow.append(Paragraph("Executive Summary", styles["H1Accent"]))
        # Pricing-first, plain language: no "validated against N rules"
        # jargon, and validation issues are only mentioned when there
        # actually are any - a clean estimate should read as good news, not
        # as a report card with a bunch of zero-value technical counters.
        summary_text = (
            f"This proposal presents a Google Cloud infrastructure estimate for <b>{estimate.project_name}</b>, "
            f"deployed in <b>{estimate.normalized_spec.region}</b>. The recommended configuration comes to a "
            f"total estimated cost of <b>{estimate.cost.currency} {estimate.cost.total_monthly:,.2f} per month</b> "
            f"({estimate.cost.currency} {estimate.cost.total_yearly:,.2f} per year). "
        )
        if estimate.assumptions:
            plural = "s" if len(estimate.assumptions) != 1 else ""
            summary_text += (
                f"{len(estimate.assumptions)} part{plural} of the request could not be matched exactly and "
                f"{'were' if plural else 'was'} adjusted to the nearest available option - see the Assumptions "
                f"section below for what changed and why, in plain language. "
            )
        else:
            summary_text += "Every part of the requested configuration was available exactly as specified - no changes were needed. "
        issue_count = estimate.validation.blocker_count + estimate.validation.warning_count
        if issue_count:
            plural = "s" if issue_count != 1 else ""
            summary_text += (
                f"{issue_count} item{plural} need{'s' if not plural else ''} a second look before this is "
                f"finalized - see the Configuration Review section for details."
            )
        flow.append(Paragraph(summary_text, styles["BodyText"]))
        flow.append(Spacer(1, 14))

        metric_cells = [
            [Paragraph("MONTHLY", styles["MetricLabel"]), Paragraph("YEARLY", styles["MetricLabel"]), Paragraph("3-YEAR", styles["MetricLabel"])],
            [
                Paragraph(f"{estimate.cost.currency} {estimate.cost.total_monthly:,.2f}", styles["MetricValue"]),
                Paragraph(f"{estimate.cost.currency} {estimate.cost.total_yearly:,.2f}", styles["MetricValue"]),
                Paragraph(f"{estimate.cost.currency} {estimate.cost.total_three_year:,.2f}", styles["MetricValue"]),
            ],
        ]
        metric_table = Table(metric_cells, colWidths=[5 * cm, 5 * cm, 5 * cm])
        metric_table.setStyle(TableStyle([
            ("BOX", (0, 0), (-1, -1), 0.75, colors.HexColor("#E0E0E0")),
            ("INNERGRID", (0, 0), (-1, -1), 0.75, colors.HexColor("#E0E0E0")),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F5F5F5")),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ]))
        flow.append(metric_table)

        if explanation is not None and explanation.executive_summary:
            flow.append(Spacer(1, 14))
            flow.append(Paragraph("AI-Generated Summary", styles["H2Accent"]))
            flow.append(Paragraph(explanation.executive_summary, styles["BodyText"]))
        return [KeepTogether(flow)]

    # -- clean-estimate badge -------------------------------------------------

    def _validation_status_badge(self, styles) -> Table:
        text = (
            "Validation Status: Passed - your requested configuration needed no adjustments and passed "
            "every check."
        )
        badge = Table([[self._cell(text, styles, "BadgeText")]], colWidths=[_USABLE_WIDTH_CM * cm])
        badge.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#E6F4EA")),
            ("BOX", (0, 0), (-1, -1), 0.75, colors.HexColor("#188038")),
            ("LEFTPADDING", (0, 0), (-1, -1), 10),
            ("RIGHTPADDING", (0, 0), (-1, -1), 10),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ]))
        return badge

    # -- architecture ---------------------------------------------------------

    def _architecture_section(self, estimate: EstimateResult, styles, accent):
        flow = [Paragraph("Recommended Architecture", styles["H1Accent"])]
        flow.append(Paragraph(estimate.architecture.summary, styles["BodyText"]))
        flow.append(Spacer(1, 8))
        rows = [["Layer", "Recommended Service", "Rationale"]]
        for c in estimate.architecture.components:
            rows.append([c.layer, self._cell(c.service, styles), self._cell(c.rationale, styles)])
        table = Table(rows, colWidths=[3 * cm, 5 * cm, 8.5 * cm], repeatRows=1)
        table.setStyle(self._table_style(accent))
        flow.append(table)
        return [KeepTogether(flow)] if len(estimate.architecture.components) <= 1 else flow

    # -- consolidated cost breakdown (table + category totals + grand totals) -

    def _cost_breakdown_section(self, estimate: EstimateResult, styles, accent):
        """Replaces the old separate "Selected Resources", "Category
        Totals", and "Itemized Pricing" sections/tables with one - the
        per-resource rows already reconcile exactly with both the category
        totals and the pricing engine's own line-item totals (see
        CostBreakdown's own invariant docs in app/domain/pricing.py), so
        showing all three was the same numbers three times over, not three
        different views a reader actually needs."""
        flow = [Paragraph("Cost Breakdown", styles["H1Accent"])]
        summaries = estimate.cost.resource_summaries

        if summaries:
            rows = [["Category", "Resource", "Configuration", "Qty", "Unit Cost", "Subtotal", "Status"]]
            grand_total = 0.0
            for s in summaries:
                config_text = s.normalized_configuration or s.configuration
                if s.status != "valid" and s.assumption_reason:
                    config_text = f"{config_text}<br/><i>{s.assumption_reason}</i>"
                rows.append([
                    s.category or "-",
                    self._cell(s.resource_name, styles),
                    self._cell(config_text, styles),
                    str(s.quantity),
                    f"{s.currency} {s.unit_cost:,.2f}",
                    f"{s.currency} {s.subtotal:,.2f}",
                    s.status.replace("_", " ").title(),
                ])
                grand_total += s.subtotal
            rows.append(["", "", "", "", "", "Grand Total", f"{estimate.cost.currency} {grand_total:,.2f}"])
            table = Table(rows, colWidths=[2.0 * cm, 2.6 * cm, 5.1 * cm, 1.1 * cm, 2.2 * cm, 2.2 * cm, 2.0 * cm], repeatRows=1)
            style = self._table_style(accent)
            style.add("ALIGN", (3, 1), (5, -1), "RIGHT")
            style.add("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold")
            style.add("LINEABOVE", (0, -1), (-1, -1), 0.75, accent)
            table.setStyle(style)
            flow.append(table)
        else:
            flow.append(Paragraph("No priced resources on this estimate.", styles["BodyText"]))

        if estimate.cost.category_totals:
            flow.append(Spacer(1, 10))
            flow.append(Paragraph("Category Totals", styles["H2Accent"]))
            cat_rows = [["Category", "Total"]]
            for category, total in estimate.cost.category_totals.items():
                cat_rows.append([category, f"{estimate.cost.currency} {total:,.2f}"])
            cat_table = Table(cat_rows, colWidths=[8 * cm, 6 * cm], repeatRows=1)
            cat_style = self._table_style(accent)
            cat_style.add("ALIGN", (1, 1), (1, -1), "RIGHT")
            cat_table.setStyle(cat_style)
            flow.append(cat_table)

        # Totals roll-up, directly underneath the cost breakdown table above
        # rather than in its own section pages later in the document.
        flow.append(Spacer(1, 10))
        flow.append(Paragraph("Totals", styles["H2Accent"]))
        totals_rows = [
            ["Subtotal", f"{estimate.cost.currency} {estimate.cost.subtotal_monthly:,.2f}"],
            ["Discounts", f"-{estimate.cost.currency} {estimate.cost.discount_total_monthly:,.2f}"],
            [f"Tax ({estimate.cost.tax_rate_percent}%)", f"{estimate.cost.currency} {estimate.cost.tax_monthly:,.2f}"],
            [f"Support Plan ({estimate.cost.support_plan_percent}%)", f"{estimate.cost.currency} {estimate.cost.support_monthly:,.2f}"],
            ["Total Monthly", f"{estimate.cost.currency} {estimate.cost.total_monthly:,.2f}"],
            ["Total Yearly", f"{estimate.cost.currency} {estimate.cost.total_yearly:,.2f}"],
            ["Total 3-Year", f"{estimate.cost.currency} {estimate.cost.total_three_year:,.2f}"],
        ]
        totals_table = Table(totals_rows, colWidths=[8 * cm, 6 * cm])
        totals_table.setStyle(TableStyle([
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("ALIGN", (1, 0), (1, -1), "RIGHT"),
            ("LINEABOVE", (0, 4), (-1, 4), 0.75, accent),
            ("FONTNAME", (0, 4), (-1, 6), "Helvetica-Bold"),
            ("BACKGROUND", (0, 6), (-1, 6), colors.HexColor("#F5F5F5")),
        ]))
        flow.append(totals_table)

        flow += self._visual_breakdown(estimate, styles, accent)
        return flow

    def _visual_breakdown(self, estimate: EstimateResult, styles, accent):
        """Pie chart only when there's actually something to compare - a
        single-category estimate (e.g. 100% Database) has nothing for a pie
        to usefully show, so it's replaced with a one-line statement
        instead of a degenerate one-slice pie."""
        flow = [Spacer(1, 10), Paragraph("Visual Breakdown", styles["H2Accent"])]

        categories = list(estimate.cost.category_totals.keys())
        values = [round(v, 2) for v in estimate.cost.category_totals.values()]

        chart_row = []
        if len(categories) >= 2:
            drawing = Drawing(260, 200)
            pie = Pie()
            pie.x, pie.y = 20, 15
            pie.width, pie.height = 150, 150
            pie.data = values
            pie.labels = [f"{c} ({v:,.0f})" for c, v in zip(categories, values)]
            pie.slices.fontSize = 7
            palette = [accent, colors.HexColor("#34A853"), colors.HexColor("#FBBC04"),
                       colors.HexColor("#EA4335"), colors.HexColor("#A142F4"), colors.HexColor("#00ACC1")]
            for i in range(len(values)):
                pie.slices[i].fillColor = palette[i % len(palette)]
            drawing.add(pie)
            chart_row.append(drawing)
        elif categories:
            flow.append(Paragraph(f"All costs are in a single category: <b>{categories[0]}</b> (100%).", styles["BodyText"]))
        else:
            flow.append(Paragraph("No priced line items to chart.", styles["BodyText"]))

        bar_drawing = Drawing(260, 200)
        chart = VerticalBarChart()
        chart.x, chart.y = 40, 30
        chart.width, chart.height = 190, 140
        chart.data = [[estimate.cost.total_monthly, estimate.cost.total_yearly, estimate.cost.total_three_year]]
        chart.categoryAxis.categoryNames = ["Monthly", "Yearly", "3-Year"]
        chart.categoryAxis.labels.fontSize = 7
        chart.valueAxis.labels.fontSize = 7
        chart.bars[0].fillColor = accent
        chart.valueAxis.valueMin = 0
        bar_drawing.add(chart)
        chart_row.append(bar_drawing)

        if chart_row:
            row_table = Table([chart_row], colWidths=[_USABLE_WIDTH_CM / len(chart_row) * cm] * len(chart_row))
            row_table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
            flow.append(row_table)
        return [KeepTogether(flow)]

    # -- assumptions ------------------------------------------------------------

    def _assumptions_section(
        self, estimate: EstimateResult, styles, accent, explanation: EstimateExplanation | None = None,
    ):
        flow = [Paragraph("Assumptions", styles["H1Accent"])]
        has_ai_column = (
            explanation is not None
            and len(explanation.assumption_explanations) == len(estimate.assumptions)
        )
        if has_ai_column:
            rows = [["What Changed", "You Requested", "We Used", "Why", "Customer-Friendly Explanation"]]
            for a, exp in zip(estimate.assumptions, explanation.assumption_explanations):
                rows.append([
                    self._cell(humanize_field_code(a.field), styles),
                    self._cell(a.requested_value, styles),
                    self._cell(a.used_value, styles),
                    self._cell(a.reason, styles),
                    self._cell(exp.explanation, styles),
                ])
            table = Table(rows, colWidths=[2.3 * cm, 2.3 * cm, 2.7 * cm, 4.6 * cm, 4.6 * cm], repeatRows=1)
        else:
            rows = [["What Changed", "You Requested", "We Used", "Why"]]
            for a in estimate.assumptions:
                rows.append([
                    self._cell(humanize_field_code(a.field), styles),
                    self._cell(a.requested_value, styles),
                    self._cell(a.used_value, styles),
                    self._cell(a.reason, styles),
                ])
            table = Table(rows, colWidths=[3 * cm, 3 * cm, 3.5 * cm, 6.5 * cm], repeatRows=1)
        table.setStyle(self._table_style(accent))
        flow.append(table)
        return flow

    # -- configuration review (only called when there are findings) -----------

    def _validation_section(self, findings, styles, accent):
        flow = [Paragraph("Configuration Review", styles["H1Accent"])]
        rows = [["What Changed", "Priority", "Details"]]
        for r in findings:
            hexcolor = SEVERITY_COLORS.get(r.severity.value, colors.black).hexval()[2:]
            priority_text = SEVERITY_LABELS.get(r.severity.value, r.severity.value.title())
            # Color is baked into the Paragraph markup itself (rather than a
            # TableStyle TEXTCOLOR command) specifically so this column can
            # be a wrapping Paragraph - TableStyle's per-cell TEXTCOLOR/
            # FONTNAME commands only style plain-string cells, not Paragraph
            # flowables, so this is what keeps both the color-coding AND the
            # overflow-safety at once.
            priority_cell = Paragraph(f'<font color="#{hexcolor}"><b>{priority_text}</b></font>', styles["BodySmall"])
            rows.append([self._cell(humanize_field_code(r.field), styles), priority_cell, self._cell(r.reason, styles)])
        table = Table(rows, colWidths=[3.8 * cm, 2.8 * cm, 9.6 * cm], repeatRows=1)
        table.setStyle(self._table_style(accent))
        flow.append(table)
        return flow

    # -- savings (only called when there's at least one item) -----------------

    def _savings_items(self, estimate: EstimateResult) -> list[str]:
        items = []
        for d in estimate.cost.discounts:
            items.append(f"<b>{d.name}</b> is already applied, saving {estimate.cost.currency} {d.monthly_savings:,.2f}/month ({d.percent_off}%).")
        for r in estimate.validation.results:
            if r.severity.value in ("warning", "blocker") and r.recommendation and r.recommendation != "No action needed.":
                items.append(f"<b>{humanize_field_code(r.field)}</b>: {r.recommendation}")
        return items

    def _savings_section(self, items: list[str], styles):
        flow = [Paragraph("Savings Opportunities & Optimization Recommendations", styles["H1Accent"])]
        for text in items:
            flow.append(Paragraph(f"&bull; {text}", styles["BodyText"]))
            flow.append(Spacer(1, 4))
        return flow

    # -- signature ------------------------------------------------------------

    def _signature_section(self, branding: BrandingConfig, styles):
        flow = [Paragraph("Approval", styles["H1Accent"])]
        rows = [
            ["Prepared By:", branding.prepared_by, "Date:", ""],
            ["", "_" * 30, "", "_" * 20],
            ["Approved By:", branding.prepared_for or "", "Date:", ""],
            ["", "_" * 30, "", "_" * 20],
        ]
        table = Table(rows, colWidths=[3 * cm, 6 * cm, 2 * cm, 4 * cm])
        table.setStyle(TableStyle([
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("TOPPADDING", (0, 0), (-1, -1), 10),
        ]))
        flow.append(table)
        return [KeepTogether(flow)]

    def _table_style(self, accent) -> TableStyle:
        return TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), accent),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8.5),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#DDDDDD")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#FAFAFA")]),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ])
