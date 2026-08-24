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
from reportlab.lib.units import cm, inch
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

# Top/bottom margins are tight (0.5in) so a simple single-resource estimate
# fits on one page; left/right stay at 1.8cm (everything above is sized to
# that width). The footer is drawn inside this same bottom margin band -
# see _footer() - so a smaller bottom margin also moves the footer's y
# position, not just body content.
_TOP_BOTTOM_MARGIN = 0.5 * inch
_SIDE_MARGIN = 1.8 * cm


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
            topMargin=_TOP_BOTTOM_MARGIN, bottomMargin=_TOP_BOTTOM_MARGIN,
            leftMargin=_SIDE_MARGIN, rightMargin=_SIDE_MARGIN,
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
        story.append(Spacer(1, 6))
        if fully_clean:
            story.append(self._validation_status_badge(styles))
            story.append(Spacer(1, 8))
        story += self._architecture_section(estimate, styles, accent)
        story.append(Spacer(1, 8))
        story += self._cost_breakdown_section(estimate, styles, accent)
        if estimate.assumptions:
            story.append(Spacer(1, 8))
            story += self._assumptions_section(estimate, styles, accent, explanation)
        if findings:
            story.append(Spacer(1, 8))
            story += self._validation_section(findings, styles, accent)
        if savings_items:
            story.append(Spacer(1, 8))
            story += self._savings_section(savings_items, styles)

        doc.build(story, onFirstPage=self._footer(branding), onLaterPages=self._footer(branding))
        return buf.getvalue()

    # -- styling ------------------------------------------------------------

    def _build_styles(self, accent):
        styles = getSampleStyleSheet()
        # keepWithNext=True on both heading levels means the layout engine
        # never breaks the page immediately after a heading - a section
        # title always moves to the next page together with (at least the
        # start of) whatever follows it, instead of being left as an orphan
        # alone at the bottom of the previous page. Sections whose heading +
        # table are also small/bounded (Cost Breakdown, Visual Breakdown) go
        # further and wrap the whole thing in KeepTogether below.
        styles.add(ParagraphStyle("H1Accent", parent=styles["Heading1"], textColor=accent, spaceAfter=8, keepWithNext=True))
        styles.add(ParagraphStyle("H2Accent", parent=styles["Heading2"], textColor=accent, spaceBefore=8, spaceAfter=6, keepWithNext=True))
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
            # 8pt (not 7pt) per the disclaimer-legibility fix, and always
            # measured/truncated by actual glyph width (_truncate_to_width)
            # rather than a fixed character count - that's what guarantees
            # the note plus page number can never run past the right margin
            # ("...official G...") regardless of font size or note length.
            font_name, font_size = "Helvetica", 8
            canvas.setFont(font_name, font_size)
            canvas.setFillColor(colors.grey)

            left_x = _SIDE_MARGIN
            right_x = A4[0] - _SIDE_MARGIN
            # Sits inside the bottom margin band, below where body content
            # stops flowing (_TOP_BOTTOM_MARGIN) - kept below that line with
            # headroom so it never collides with the last line of content.
            footer_y = min(0.6 * cm, _TOP_BOTTOM_MARGIN * 0.5)
            page_label = f"Page {doc.page}"
            page_label_width = stringWidth(page_label, font_name, font_size)
            gap = 0.4 * cm
            max_note_width = (right_x - left_x) - page_label_width - gap

            note = self._truncate_to_width(branding.footer_note.strip(), font_name, font_size, max_note_width)
            canvas.drawString(left_x, footer_y, note)
            canvas.drawRightString(right_x, footer_y, page_label)
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
        flow.append(Spacer(1, 14))
        flow.append(Paragraph(branding.company_name, styles["CoverTitle"]))
        flow.append(Paragraph("Google Cloud FinOps Cost Estimate Proposal", styles["Heading2"]))
        flow.append(Spacer(1, 8))
        flow.append(HRFlowable(width="100%", color=accent, thickness=1.2))
        flow.append(Spacer(1, 8))

        meta_rows = [["Project", self._cell(estimate.project_name, styles)]]
        if branding.prepared_for:
            # Omitted rather than shown as "Prepared For: -" when nothing
            # was actually supplied - a placeholder dash reads as a
            # fabricated field, not as "no value given" (same fix as the
            # Excel Summary sheet's Prepared For handling).
            meta_rows.append(["Prepared For", self._cell(branding.prepared_for, styles)])
        meta_rows += [
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
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("TOPPADDING", (0, 0), (-1, -1), 1),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#444444")),
        ]))
        flow.append(meta_table)
        flow.append(Spacer(1, 10))

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
        flow.append(Spacer(1, 8))

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
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        flow.append(metric_table)

        if explanation is not None and explanation.executive_summary:
            flow.append(Spacer(1, 10))
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
        flow.append(Spacer(1, 6))
        rows = [["Layer", "Recommended Service", "Rationale"]]
        for c in estimate.architecture.components:
            rows.append([c.layer, self._cell(c.service, styles), self._cell(c.rationale, styles)])
        table = Table(rows, colWidths=[3 * cm, 5 * cm, 8.5 * cm], repeatRows=1)
        table.setStyle(self._table_style(accent))
        flow.append(table)
        return [KeepTogether(flow)] if len(estimate.architecture.components) <= 1 else flow

    # -- consolidated cost breakdown (one table: line items + roll-up rows) --

    def _cost_breakdown_section(self, estimate: EstimateResult, styles, accent):
        """One table for the whole financial picture - per-resource line
        items immediately followed by the roll-up rows (Subtotal, Discounts,
        Tax, Support, Total Monthly), sharing the same Subtotal/Amount
        column. Replaces the old separate "Selected Resources" / "Category
        Totals" / "Itemized Pricing" / "Totals" tables, which showed the
        same figures three or four times over across separate headed
        sections instead of the one view a reader actually needs.

        Heading + table are wrapped in a single KeepTogether so "Cost
        Breakdown" can never be orphaned alone at the bottom of a page -
        for the bounded size of a real cost estimate (a handful to a few
        dozen resources), keeping the whole thing together is worth it;
        Visual Breakdown (below) intentionally stays a separate flowable so
        it's free to start its own page if the table already filled one."""
        cost = estimate.cost
        columns = ["Category", "Resource", "Configuration", "Qty", "Unit Cost", "Subtotal"]
        rows = [columns]
        style = self._table_style(accent)
        style.add("ALIGN", (3, 1), (5, -1), "RIGHT")

        summaries = cost.resource_summaries
        if summaries:
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
                ])
        else:
            rows.append([self._cell("No priced resources on this estimate.", styles), "", "", "", "", ""])
            style.add("SPAN", (0, 1), (5, 1))

        # Roll-up rows share the table: columns 0-4 span into one label
        # cell, column 5 (the same money column every line item uses)
        # holds the amount - visually and structurally the same table, not
        # a second one bolted on underneath.
        def _summary_row(label: str, value: str, *, bold: bool = False, rule_above: bool = False):
            idx = len(rows)
            rows.append([label, "", "", "", "", value])
            style.add("SPAN", (0, idx), (4, idx))
            if rule_above:
                style.add("LINEABOVE", (0, idx), (-1, idx), 0.75, accent)
            if bold:
                style.add("FONTNAME", (0, idx), (-1, idx), "Helvetica-Bold")
                style.add("BACKGROUND", (0, idx), (-1, idx), colors.HexColor("#F5F5F5"))

        _summary_row("Subtotal", f"{cost.currency} {cost.subtotal_monthly:,.2f}", rule_above=True)
        for d in cost.discounts:
            _summary_row(f"Discount: {d.name} (-{d.percent_off}%)", f"-{cost.currency} {d.monthly_savings:,.2f}")
        _summary_row(f"Tax ({cost.tax_rate_percent}%)", f"{cost.currency} {cost.tax_monthly:,.2f}")
        _summary_row(f"Support Plan ({cost.support_plan_percent}%)", f"{cost.currency} {cost.support_monthly:,.2f}")
        _summary_row("Total Monthly Cost", f"{cost.currency} {cost.total_monthly:,.2f}", bold=True, rule_above=True)

        table = Table(rows, colWidths=[2.2 * cm, 2.8 * cm, 6.5 * cm, 1.2 * cm, 2.3 * cm, 2.4 * cm], repeatRows=1)
        table.setStyle(style)

        flow = [Paragraph("Cost Breakdown", styles["H1Accent"]), table]
        return [KeepTogether(flow)] + self._visual_breakdown(estimate, styles, accent)

    def _visual_breakdown(self, estimate: EstimateResult, styles, accent):
        """Category-mix pie chart only. The old Monthly/Yearly/3-Year bar
        chart was removed - those exact three figures are already the
        headline MONTHLY/YEARLY/3-YEAR metric row on page 1 (see
        _cover_and_executive_summary), so charting them again here added a
        page without adding information. A single-category estimate (e.g.
        100% Database) has nothing for a pie to usefully compare, so it
        gets a one-line statement instead of a degenerate one-slice pie."""
        flow = [Spacer(1, 6), Paragraph("Visual Breakdown", styles["H2Accent"])]

        categories = list(estimate.cost.category_totals.keys())
        values = [round(v, 2) for v in estimate.cost.category_totals.values()]

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
            flow.append(drawing)
        elif categories:
            flow.append(Paragraph(f"All costs are in a single category: <b>{categories[0]}</b> (100%).", styles["BodyText"]))
        else:
            flow.append(Paragraph("No priced line items to chart.", styles["BodyText"]))

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

    def _table_style(self, accent) -> TableStyle:
        return TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), accent),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8.5),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#DDDDDD")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#FAFAFA")]),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ])
