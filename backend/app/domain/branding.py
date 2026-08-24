"""Branding/cover-page configuration for generated Excel and PDF reports.
Every field has a sensible default so reports look professional even if the
caller supplies nothing - but a consulting firm can override every field to
white-label the output."""
from pydantic import BaseModel, Field


class BrandingConfig(BaseModel):
    company_name: str = Field(default="GCP FinOps Estimation Platform")
    # Never a fabricated org name (e.g. "FinOps Consulting Team") - this is
    # the platform's own name, shown only when the caller hasn't supplied a
    # real preparer.
    prepared_by: str = Field(default="GCP FinOps Estimation Platform")
    prepared_for: str | None = Field(default=None, description="Customer/client name shown on the cover page")
    contact_email: str | None = Field(default=None)
    primary_color_hex: str = Field(default="1A73E8", description="6-digit hex, no '#', used for header fills/accents")
    footer_note: str = Field(
        default="This estimate is generated from a configurable pricing catalog and is intended for budgetary "
                "planning purposes. Confirm final pricing with official Google Cloud quotes before purchase."
    )
