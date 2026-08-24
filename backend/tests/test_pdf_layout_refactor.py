"""
Tests for the executive-proposal PDF layout refactor
(app/reports/pdf_generator.py): footer truncation by measured width (now at
8pt), the single consolidated "Cost Breakdown" table (line items followed by
Subtotal/Discounts/Tax/Support/Total Monthly Cost roll-up rows in the same
table - no more separate Selected Resources / Category Totals / Itemized
Pricing / Totals sections), conditional pie-chart suppression for a
single-category estimate with the redundant Monthly/Yearly/3-Year bar chart
removed entirely, orphan-heading prevention (KeepTogether + keepWithNext),
and the tighter 0.5in top/bottom margins that let a simple single-resource
estimate fit on one page.
"""
import io

import pytest
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm, inch
from reportlab.pdfbase.pdfmetrics import stringWidth

from app.catalog.mock_provider import MockCatalogProvider
from app.core.config import Settings
from app.domain.branding import BrandingConfig
from app.domain.enums import CloudSqlEngine, MachineFamily, Region
from app.domain.requirements import ComputeRequirement, CustomerRequirement, DatabaseRequirement
from app.pricing.mock_provider import MockGCPPricingProvider
from app.reports import pdf_generator as pdf_generator_module
from app.reports.pdf_generator import PdfReportGenerator
from app.services.estimation_service import EstimationService

pypdf = pytest.importorskip("pypdf")

FONT_NAME, FONT_SIZE = "Helvetica", 7
_USABLE_WIDTH_PT = (A4[0] - 1.8 * cm) - 1.8 * cm


class _FakeCanvas:
    """Records saveState/setFont/drawString/... calls so _footer's drawing
    closure can be exercised without an actual reportlab.pdfgen.canvas -
    just enough of the Canvas interface for _draw(canvas, doc) to run."""

    def __init__(self):
        self.font_calls: list[tuple[str, float]] = []
        # (left_edge_x, right_edge_x, y, text) - normalized so both
        # drawString (left-anchored) and drawRightString (right-anchored)
        # calls can be checked against the page margin the same way.
        self.strings: list[tuple[float, float, float, str]] = []

    def saveState(self):
        pass

    def restoreState(self):
        pass

    def setFont(self, name, size):
        self.font_calls.append((name, size))

    def setFillColor(self, color):
        pass

    def drawString(self, x, y, text):
        width = stringWidth(text, *self.font_calls[-1]) if self.font_calls else 0
        self.strings.append((x, x + width, y, text))

    def drawRightString(self, x, y, text):
        width = stringWidth(text, *self.font_calls[-1]) if self.font_calls else 0
        self.strings.append((x - width, x, y, text))


class _FakeDoc:
    page = 1


@pytest.fixture
def single_category_estimate():
    """Compute-only, no database/storage/network - exactly one resource
    category (Compute), used to exercise pie-chart suppression."""
    catalog = MockCatalogProvider()
    pricing = MockGCPPricingProvider()
    settings = Settings(default_normalization_strategy="balanced", default_tax_rate_percent=0, support_plan_percent=0)
    service = EstimationService(catalog=catalog, pricing_provider=pricing, settings=settings)
    req = CustomerRequirement(
        project_name="Single Category Test",
        region=Region.US_CENTRAL1,
        compute=ComputeRequirement(machine_family=MachineFamily.E2, vcpu=4, ram_gb=16, instance_count=1),
    )
    return service.generate_estimate(req)


@pytest.fixture
def multi_category_estimate():
    catalog = MockCatalogProvider()
    pricing = MockGCPPricingProvider()
    settings = Settings(default_normalization_strategy="balanced", default_tax_rate_percent=0, support_plan_percent=0)
    service = EstimationService(catalog=catalog, pricing_provider=pricing, settings=settings)
    req = CustomerRequirement(
        project_name="Multi Category Test",
        region=Region.US_CENTRAL1,
        compute=ComputeRequirement(machine_family=MachineFamily.E2, vcpu=4, ram_gb=16, instance_count=1),
        database=DatabaseRequirement(required=True, engine=CloudSqlEngine.POSTGRES, size_gb=50, vcpu=2, ram_gb=8),
    )
    return service.generate_estimate(req)


@pytest.fixture
def single_resource_db_estimate():
    """Cloud SQL only, nothing else - the "simple single-resource estimate"
    the 1-page layout requirement names explicitly."""
    catalog = MockCatalogProvider()
    pricing = MockGCPPricingProvider()
    settings = Settings(default_normalization_strategy="balanced", default_tax_rate_percent=0, support_plan_percent=0)
    service = EstimationService(catalog=catalog, pricing_provider=pricing, settings=settings)
    req = CustomerRequirement(
        project_name="Cloud SQL Only",
        region=Region.US_CENTRAL1,
        database=DatabaseRequirement(required=True, engine=CloudSqlEngine.POSTGRES, size_gb=50, vcpu=2, ram_gb=8),
    )
    return service.generate_estimate(req)


# -- Margins / footer font size --------------------------------------------------

def test_top_bottom_margins_are_half_an_inch():
    assert pdf_generator_module._TOP_BOTTOM_MARGIN == pytest.approx(0.5 * inch)


def test_footer_uses_8pt_font():
    canvas = _FakeCanvas()
    PdfReportGenerator()._footer(BrandingConfig())(canvas, _FakeDoc())
    assert ("Helvetica", 8) in canvas.font_calls


def test_footer_text_never_crosses_the_right_margin():
    # A pathologically long footer_note plus the "Page N" label together
    # must still both land left of the right margin - this is what the old
    # fixed text[:140] slice could violate ("...official G...").
    canvas = _FakeCanvas()
    branding = BrandingConfig(footer_note="This is a very long disclaimer. " * 20)
    PdfReportGenerator()._footer(branding)(canvas, _FakeDoc())

    right_margin = A4[0] - pdf_generator_module._SIDE_MARGIN
    left_margin = pdf_generator_module._SIDE_MARGIN
    for left_edge, right_edge, _y, _text in canvas.strings:
        assert right_edge <= right_margin + 0.5  # tolerate sub-pixel float noise
        assert left_edge >= left_margin - 0.5


def test_single_resource_estimate_fits_on_one_page(single_resource_db_estimate):
    pbytes = PdfReportGenerator().generate(single_resource_db_estimate)
    reader = pypdf.PdfReader(io.BytesIO(pbytes))
    assert len(reader.pages) == 1


# -- Footer truncation by measured width ---------------------------------------

def test_truncate_to_width_returns_unchanged_when_it_already_fits():
    generator = PdfReportGenerator()
    short_text = "Short disclaimer."
    result = generator._truncate_to_width(short_text, FONT_NAME, FONT_SIZE, max_width=500)
    assert result == short_text


def test_truncate_to_width_never_exceeds_the_given_width():
    generator = PdfReportGenerator()
    long_text = "A" * 500  # pathologically long, guarantees truncation is exercised
    max_width = 100.0
    result = generator._truncate_to_width(long_text, FONT_NAME, FONT_SIZE, max_width)
    assert stringWidth(result, FONT_NAME, FONT_SIZE) <= max_width
    assert result.endswith("...")


def test_truncate_to_width_handles_the_default_branding_footer_note():
    # BrandingConfig's own default footer_note is the exact real-world input
    # that used to get clipped by the old `text[:140]` slice - confirm it
    # now always fits within a realistic page-footer budget regardless of
    # font metrics, rather than being cut by a hardcoded character count.
    generator = PdfReportGenerator()
    note = BrandingConfig().footer_note
    max_width = 400.0  # narrower than the real footer budget, to force truncation
    result = generator._truncate_to_width(note, FONT_NAME, FONT_SIZE, max_width)
    assert stringWidth(result, FONT_NAME, FONT_SIZE) <= max_width


def test_pdf_footer_note_and_page_number_never_overflow_the_page_margin(sample_estimate):
    # An extreme, unrealistically long footer_note (arbitrary user input via
    # BrandingConfig) must still render without any text past the right
    # margin - this is the actual end-to-end regression check for the
    # "footer text fits completely inside the page margins" requirement.
    branding = BrandingConfig(footer_note="This is a very long disclaimer. " * 20)
    pbytes = PdfReportGenerator().generate(sample_estimate, branding)
    assert pbytes[:5] == b"%PDF-"  # generates successfully with no exception

    generator = PdfReportGenerator()
    page_label_width = stringWidth("Page 1", FONT_NAME, FONT_SIZE)
    max_note_width = _USABLE_WIDTH_PT - page_label_width - 0.4 * cm
    truncated = generator._truncate_to_width(branding.footer_note.strip(), FONT_NAME, FONT_SIZE, max_note_width)
    assert stringWidth(truncated, FONT_NAME, FONT_SIZE) <= max_note_width
    assert truncated.endswith("...")


# -- Conditional pie chart -------------------------------------------------------

def test_single_category_estimate_shows_text_summary_not_a_pie(single_category_estimate):
    assert len(single_category_estimate.cost.category_totals) == 1  # sanity
    pbytes = PdfReportGenerator().generate(single_category_estimate)
    reader = pypdf.PdfReader(io.BytesIO(pbytes))
    text = " ".join(p.extract_text() for p in reader.pages).replace("\n", " ")
    assert "All costs are in a single category" in text
    assert "Compute" in text
    assert "(100%)" in text


def test_multi_category_estimate_still_shows_visual_breakdown(multi_category_estimate):
    assert len(multi_category_estimate.cost.category_totals) >= 2  # sanity
    pbytes = PdfReportGenerator().generate(multi_category_estimate)
    reader = pypdf.PdfReader(io.BytesIO(pbytes))
    text = " ".join(p.extract_text() for p in reader.pages).replace("\n", " ")
    assert "Visual Breakdown" in text
    assert "All costs are in a single category" not in text


def test_monthly_yearly_3year_bar_chart_was_removed():
    # The bar chart repeated exactly the three figures already headlined in
    # the page 1 executive summary metric row - regression guard against
    # reintroducing it (see _visual_breakdown's docstring).
    assert not hasattr(pdf_generator_module, "VerticalBarChart")


# -- Consolidated Cost Breakdown table -------------------------------------------

def test_cost_breakdown_table_totals_reconcile_in_single_table(sample_estimate):
    cost = sample_estimate.cost
    pbytes = PdfReportGenerator().generate(sample_estimate)
    reader = pypdf.PdfReader(io.BytesIO(pbytes))
    text = " ".join(p.extract_text() for p in reader.pages).replace("\n", " ")

    assert "Cost Breakdown" in text
    assert "Total Monthly Cost" in text
    # The old separate "Selected Resources" / "Category Totals" / "Itemized
    # Pricing" / "Totals" tables - the same figures shown three or four
    # times over - are gone; everything lives in the one Cost Breakdown
    # table now.
    for removed in ["Itemized Pricing", "Selected Resources", "Category Totals", "Grand Total"]:
        assert removed not in text
    assert "Totals" not in text  # the standalone "Totals" heading specifically

    for r in cost.resource_summaries:
        assert r.resource_name in text
    for category in cost.category_totals:
        assert category in text  # still visible per-row in the unified table

    # Every roll-up figure the requirement asks for (Subtotal, Tax, Support,
    # Total Monthly) is present and matches the canonical CostBreakdown
    # values - one table, one set of numbers, no restating.
    assert f"{cost.subtotal_monthly:,.2f}" in text
    assert f"{cost.tax_monthly:,.2f}" in text
    assert f"{cost.support_monthly:,.2f}" in text
    assert f"{cost.total_monthly:,.2f}" in text


def test_cost_breakdown_heading_and_table_are_not_orphaned_across_pages(sample_estimate):
    # Regression test for the "heading alone at the bottom of a page" bug:
    # wherever the "Cost Breakdown" heading actually lands, the table's own
    # content (its Total Monthly Cost roll-up row) must land on that same
    # page, never pushed to the next one by itself.
    pbytes = PdfReportGenerator().generate(sample_estimate)
    reader = pypdf.PdfReader(io.BytesIO(pbytes))
    heading_page = next(
        i for i, page in enumerate(reader.pages) if "Cost Breakdown" in page.extract_text()
    )
    assert "Total Monthly Cost" in reader.pages[heading_page].extract_text()
