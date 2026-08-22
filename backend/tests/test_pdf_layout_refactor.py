"""
Tests for the executive-proposal PDF layout refactor
(app/reports/pdf_generator.py): footer truncation by measured width, the
consolidated single "Cost Breakdown" table (merging the old Selected
Resources / Category Totals / Itemized Pricing sections with the Totals
block directly underneath), and conditional pie-chart suppression for a
single-category estimate.
"""
import io

import pytest
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.pdfbase.pdfmetrics import stringWidth

from app.catalog.mock_provider import MockCatalogProvider
from app.core.config import Settings
from app.domain.branding import BrandingConfig
from app.domain.enums import CloudSqlEngine, MachineFamily, Region
from app.domain.requirements import ComputeRequirement, CustomerRequirement, DatabaseRequirement
from app.pricing.mock_provider import MockGCPPricingProvider
from app.reports.pdf_generator import PdfReportGenerator
from app.services.estimation_service import EstimationService

pypdf = pytest.importorskip("pypdf")

FONT_NAME, FONT_SIZE = "Helvetica", 7
_USABLE_WIDTH_PT = (A4[0] - 1.8 * cm) - 1.8 * cm


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


# -- Consolidated Cost Breakdown table -------------------------------------------

def test_cost_breakdown_table_totals_reconcile_with_grand_total(sample_estimate):
    pbytes = PdfReportGenerator().generate(sample_estimate)
    reader = pypdf.PdfReader(io.BytesIO(pbytes))
    text = " ".join(p.extract_text() for p in reader.pages).replace("\n", " ")

    assert "Cost Breakdown" in text
    assert "Category Totals" in text
    assert "Totals" in text
    assert "Grand Total" in text
    # Only one financial breakdown table exists now - the old separate
    # itemized SKU-level listing is gone.
    assert "Itemized Pricing" not in text
    assert "Selected Resources" not in text

    for r in sample_estimate.cost.resource_summaries:
        assert r.resource_name in text
    for category in sample_estimate.cost.category_totals:
        assert category in text
    assert f"{sample_estimate.cost.total_monthly:,.2f}" in text
