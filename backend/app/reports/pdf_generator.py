"""
PDF proposal generator.

Builds a client-ready proposal document: executive summary, recommended
architecture, itemized pricing, assumptions, validation results, savings
opportunities, cost charts, totals, and a signature area. Like the Excel
generator, this module only renders an already-computed EstimateResult and
never invents or recalculates a price.
"""
import io
from datetime import datetime, timezone

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.charts.legends import Legend
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics.shapes import Drawing, String
from reportlab.platypus import (
    HRFlowable,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.domain.branding import BrandingConfig
from app.domain.estimate import EstimateResult
from app.domain.explanation import EstimateExplanation

SEVERITY_COLORS = {
    "blocker": colors.HexColor("#D93025"),
    "warning": colors.HexColor("#B06000"),
    "info": colors.HexColor("#188038"),
}


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

        story = []
        story += self._cover_and_executive_summary(estimate, branding, styles, accent, explanation)
        story.append(PageBreak())
        story += self._architecture_section(estimate, styles, accent)
        story.append(Spacer(1, 12))
        story += self._resource_summary_section(estimate, styles, accent)
        story.append(Spacer(1, 12))
        story += self._pricing_section(estimate, styles, accent)
        story.append(PageBreak())
        story += self._charts_section(estimate, styles, accent)
        story.append(Spacer(1, 12))
        story += self._assumptions_section(estimate, styles, accent, explanation)
        story.append(PageBreak())
        story += self._validation_section(estimate, styles, accent)
        story.append(Spacer(1, 12))
        story += self._savings_section(estimate, styles, accent)
        story.append(PageBreak())
        story += self._totals_section(estimate, styles, accent)
        story.append(Spacer(1, 24))
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
        return styles

    def _footer(self, branding: BrandingConfig):
        def _draw(canvas, doc):
            canvas.saveState()
            canvas.setFont("Helvetica", 7)
            canvas.setFillColor(colors.grey)
            canvas.drawString(1.8 * cm, 1.2 * cm, branding.footer_note[:140])
            canvas.drawRightString(A4[0] - 1.8 * cm, 1.2 * cm, f"Page {doc.page}")
            canvas.restoreState()
        return _draw

    # -- sections ------------------------------------------------------------

    def _cover_and_executive_summary(
        self, estimate: EstimateResult, branding: BrandingConfig, styles, accent,
        explanation: EstimateExplanation | None = None,
    ):
        flow = []
        flow.append(Spacer(1, 40))
        flow.append(Paragraph(branding.company_name, styles["CoverTitle"]))
        flow.append(Paragraph("Google Cloud FinOps Cost Estimate Proposal", styles["Heading2"]))
        flow.append(Spacer(1, 20))
        flow.append(HRFlowable(width="100%", color=accent, thickness=1.2))
        flow.append(Spacer(1, 20))

        meta_rows = [
            ["Project", estimate.project_name],
            ["Prepared For", branding.prepared_for or "-"],
            ["Prepared By", branding.prepared_by],
            ["Region", estimate.normalized_spec.region],
            ["Normalization Strategy", estimate.strategy_used.capitalize()],
            ["Date", datetime.now(timezone.utc).strftime("%Y-%m-%d")],
            ["Estimate ID", estimate.estimate_id],
        ]
        meta_table = Table(meta_rows, colWidths=[5 * cm, 10 * cm])
        meta_table.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#444444")),
        ]))
        flow.append(meta_table)
        flow.append(Spacer(1, 24))

        flow.append(Paragraph("Executive Summary", styles["H1Accent"]))
        summary_text = (
            f"This proposal presents a Google Cloud infrastructure estimate for <b>{estimate.project_name}</b>, "
            f"deployed in <b>{estimate.normalized_spec.region}</b>. The recommended configuration resolves to a "
            f"total estimated cost of <b>{estimate.cost.currency} {estimate.cost.total_monthly:,.2f} per month</b> "
            f"({estimate.cost.currency} {estimate.cost.total_yearly:,.2f} per year). "
            f"The request was validated against {len(estimate.validation.results)} rule(s), producing "
            f"{estimate.validation.warning_count} warning(s) and {estimate.validation.blocker_count} blocker(s). "
            f"{len(estimate.assumptions)} configuration assumption(s) were made to map the request onto valid "
            f"Google Cloud resources; each is documented in the Assumptions section below with full reasoning."
        )
        flow.append(Paragraph(summary_text, styles["BodyText"]))
        flow.append(Spacer(1, 16))

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
            flow.append(Spacer(1, 16))
            flow.append(Paragraph("AI-Generated Summary", styles["H2Accent"]))
            flow.append(Paragraph(explanation.executive_summary, styles["BodyText"]))
        return flow

    def _architecture_section(self, estimate: EstimateResult, styles, accent):
        flow = [Paragraph("Recommended Architecture", styles["H1Accent"])]
        flow.append(Paragraph(estimate.architecture.summary, styles["BodyText"]))
        flow.append(Spacer(1, 8))
        rows = [["Layer", "Recommended Service", "Rationale"]]
        for c in estimate.architecture.components:
            rows.append([c.layer, c.service, Paragraph(c.rationale, styles["BodySmall"])])
        table = Table(rows, colWidths=[3 * cm, 5 * cm, 8.5 * cm], repeatRows=1)
        table.setStyle(self._table_style(accent))
        flow.append(table)
        return flow

    def _resource_summary_section(self, estimate: EstimateResult, styles, accent):
        summaries = estimate.cost.resource_summaries
        if not summaries:
            return []
        flow = [Paragraph("Selected Resources", styles["H1Accent"])]
        rows = [["Category", "Resource", "Configuration", "Qty", "Unit Cost", "Subtotal", "Status"]]
        grand_total = 0.0
        for s in summaries:
            config_text = s.normalized_configuration or s.configuration
            if s.status != "valid" and s.assumption_reason:
                config_text = f"{config_text}<br/><i>{s.assumption_reason}</i>"
            rows.append([
                s.category or "-",
                s.resource_name,
                Paragraph(config_text, styles["BodySmall"]),
                str(s.quantity),
                f"{s.currency} {s.unit_cost:,.2f}",
                f"{s.currency} {s.subtotal:,.2f}",
                s.status.replace("_", " ").title(),
            ])
            grand_total += s.subtotal
        rows.append(["", "", "", "", "", "Grand Total", f"{estimate.cost.currency} {grand_total:,.2f}"])
        table = Table(rows, colWidths=[2.2 * cm, 2.8 * cm, 5.5 * cm, 1.2 * cm, 2.3 * cm, 2.3 * cm, 2.2 * cm], repeatRows=1)
        style = self._table_style(accent)
        style.add("ALIGN", (3, 1), (5, -1), "RIGHT")
        style.add("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold")
        style.add("LINEABOVE", (0, -1), (-1, -1), 0.75, accent)
        table.setStyle(style)
        flow.append(table)

        if estimate.cost.category_totals:
            flow.append(Spacer(1, 10))
            flow.append(Paragraph("Category Totals", styles["H2Accent"]))
            cat_rows = [["Category", "Total"]]
            for category, total in estimate.cost.category_totals.items():
                cat_rows.append([category, f"{estimate.cost.currency} {total:,.2f}"])
            cat_rows.append(["Sum of Category Totals", f"{estimate.cost.currency} {sum(estimate.cost.category_totals.values()):,.2f}"])
            cat_table = Table(cat_rows, colWidths=[8 * cm, 6 * cm], repeatRows=1)
            cat_style = self._table_style(accent)
            cat_style.add("ALIGN", (1, 1), (1, -1), "RIGHT")
            cat_style.add("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold")
            cat_style.add("LINEABOVE", (0, -1), (-1, -1), 0.75, accent)
            cat_table.setStyle(cat_style)
            flow.append(cat_table)
        return flow

    def _pricing_section(self, estimate: EstimateResult, styles, accent):
        flow = [Paragraph("Itemized Pricing", styles["H1Accent"])]
        rows = [["Category", "Description", "Monthly Amount"]]
        for li in estimate.cost.line_items:
            rows.append([li.category, Paragraph(li.description, styles["BodySmall"]), f"{li.currency} {li.monthly_amount:,.2f}"])
        table = Table(rows, colWidths=[2.5 * cm, 10.5 * cm, 3.5 * cm], repeatRows=1)
        style = self._table_style(accent)
        style.add("ALIGN", (2, 1), (2, -1), "RIGHT")
        table.setStyle(style)
        flow.append(table)
        return flow

    def _charts_section(self, estimate: EstimateResult, styles, accent):
        flow = [Paragraph("Cost Breakdown", styles["H1Accent"])]

        by_category: dict[str, float] = {}
        for li in estimate.cost.line_items:
            by_category[li.category] = by_category.get(li.category, 0) + li.monthly_amount
        categories = list(by_category.keys())
        values = [round(v, 2) for v in by_category.values()]

        if categories:
            drawing = Drawing(420, 220)
            pie = Pie()
            pie.x, pie.y = 60, 20
            pie.width, pie.height = 170, 170
            pie.data = values
            pie.labels = [f"{c} ({v:,.0f})" for c, v in zip(categories, values)]
            palette = [accent, colors.HexColor("#34A853"), colors.HexColor("#FBBC04"),
                       colors.HexColor("#EA4335"), colors.HexColor("#A142F4"), colors.HexColor("#00ACC1")]
            for i in range(len(values)):
                pie.slices[i].fillColor = palette[i % len(palette)]
            drawing.add(pie)
            flow.append(drawing)
        else:
            flow.append(Paragraph("No priced line items to chart.", styles["BodyText"]))

        flow.append(Spacer(1, 12))
        flow.append(Paragraph("Monthly vs. Yearly vs. 3-Year Cost", styles["H2Accent"]))
        bar_drawing = Drawing(420, 200)
        chart = VerticalBarChart()
        chart.x, chart.y = 50, 30
        chart.width, chart.height = 320, 140
        chart.data = [[estimate.cost.total_monthly, estimate.cost.total_yearly, estimate.cost.total_three_year]]
        chart.categoryAxis.categoryNames = ["Monthly", "Yearly", "3-Year"]
        chart.bars[0].fillColor = accent
        chart.valueAxis.valueMin = 0
        bar_drawing.add(chart)
        flow.append(bar_drawing)
        return flow

    def _assumptions_section(
        self, estimate: EstimateResult, styles, accent, explanation: EstimateExplanation | None = None,
    ):
        flow = [Paragraph("Assumptions", styles["H1Accent"])]
        if not estimate.assumptions:
            flow.append(Paragraph("No assumptions were necessary; every requested value was directly supported.", styles["BodyText"]))
            return flow

        has_ai_column = (
            explanation is not None
            and len(explanation.assumption_explanations) == len(estimate.assumptions)
        )
        if has_ai_column:
            rows = [["Field", "Requested", "Used", "Reason", "Customer-Friendly Explanation"]]
            for a, exp in zip(estimate.assumptions, explanation.assumption_explanations):
                rows.append([
                    a.field, a.requested_value, a.used_value,
                    Paragraph(a.reason, styles["BodySmall"]),
                    Paragraph(exp.explanation, styles["BodySmall"]),
                ])
            table = Table(rows, colWidths=[2.3 * cm, 2.3 * cm, 2.7 * cm, 4.6 * cm, 4.6 * cm], repeatRows=1)
        else:
            rows = [["Field", "Requested", "Used", "Reason"]]
            for a in estimate.assumptions:
                rows.append([a.field, a.requested_value, a.used_value, Paragraph(a.reason, styles["BodySmall"])])
            table = Table(rows, colWidths=[3 * cm, 3 * cm, 3.5 * cm, 6.5 * cm], repeatRows=1)
        table.setStyle(self._table_style(accent))
        flow.append(table)
        return flow

    def _validation_section(self, estimate: EstimateResult, styles, accent):
        flow = [Paragraph("Validation Results", styles["H1Accent"])]
        rows = [["Field", "Severity", "Reason"]]
        row_colors = []
        for r in estimate.validation.results:
            rows.append([r.field, r.severity.value.upper(), Paragraph(r.reason, styles["BodySmall"])])
            row_colors.append(SEVERITY_COLORS.get(r.severity.value, colors.black))
        table = Table(rows, colWidths=[4 * cm, 2.5 * cm, 9.5 * cm], repeatRows=1)
        style = self._table_style(accent)
        for i, c in enumerate(row_colors, start=1):
            style.add("TEXTCOLOR", (1, i), (1, i), c)
            style.add("FONTNAME", (1, i), (1, i), "Helvetica-Bold")
        table.setStyle(style)
        flow.append(table)
        return flow

    def _savings_section(self, estimate: EstimateResult, styles, accent):
        flow = [Paragraph("Savings Opportunities & Optimization Recommendations", styles["H1Accent"])]
        items = []
        for d in estimate.cost.discounts:
            items.append(f"<b>{d.name}</b> is already applied, saving {estimate.cost.currency} {d.monthly_savings:,.2f}/month ({d.percent_off}%).")
        for r in estimate.validation.results:
            if r.severity.value in ("warning", "blocker") and r.recommendation and r.recommendation != "No action needed.":
                items.append(f"<b>{r.field}</b>: {r.recommendation}")
        if not items:
            items.append("No additional optimization opportunities identified for this configuration.")
        for text in items:
            flow.append(Paragraph(f"&bull; {text}", styles["BodyText"]))
            flow.append(Spacer(1, 4))
        return flow

    def _totals_section(self, estimate: EstimateResult, styles, accent):
        flow = [Paragraph("Totals", styles["H1Accent"])]
        rows = [
            ["Subtotal", f"{estimate.cost.currency} {estimate.cost.subtotal_monthly:,.2f}"],
            ["Discounts", f"-{estimate.cost.currency} {estimate.cost.discount_total_monthly:,.2f}"],
            [f"Tax ({estimate.cost.tax_rate_percent}%)", f"{estimate.cost.currency} {estimate.cost.tax_monthly:,.2f}"],
            [f"Support Plan ({estimate.cost.support_plan_percent}%)", f"{estimate.cost.currency} {estimate.cost.support_monthly:,.2f}"],
            ["Total Monthly", f"{estimate.cost.currency} {estimate.cost.total_monthly:,.2f}"],
            ["Total Yearly", f"{estimate.cost.currency} {estimate.cost.total_yearly:,.2f}"],
            ["Total 3-Year", f"{estimate.cost.currency} {estimate.cost.total_three_year:,.2f}"],
        ]
        table = Table(rows, colWidths=[8 * cm, 6 * cm])
        table.setStyle(TableStyle([
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("ALIGN", (1, 0), (1, -1), "RIGHT"),
            ("LINEABOVE", (0, 4), (-1, 4), 0.75, accent),
            ("FONTNAME", (0, 4), (-1, 6), "Helvetica-Bold"),
            ("BACKGROUND", (0, 6), (-1, 6), colors.HexColor("#F5F5F5")),
        ]))
        flow.append(table)
        return flow

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
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ])
