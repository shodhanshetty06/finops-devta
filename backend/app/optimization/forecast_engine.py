"""
Cost forecast engine.

Pure, transparent compounding math over an already-priced monthly total -
this deliberately does NOT try to predict future GCP list-price changes or
customer growth; `monthly_growth_percent` is a customer/consultant-supplied
assumption (e.g. "we expect 5% month-over-month usage growth"), surfaced
back in `methodology_note` so it is never mistaken for a data-driven
prediction.
"""
from app.domain.optimization import CostForecast, CostForecastPoint

MAX_MONTHS = 60


class ForecastEngine:
    def forecast(
        self,
        starting_monthly_cost: float,
        monthly_growth_percent: float,
        months: int,
        currency: str,
    ) -> CostForecast:
        if months < 1 or months > MAX_MONTHS:
            raise ValueError(f"months must be between 1 and {MAX_MONTHS}.")

        points: list[CostForecastPoint] = []
        cumulative = 0.0
        growth_factor = 1 + (monthly_growth_percent / 100)
        for month_index in range(1, months + 1):
            projected = starting_monthly_cost * (growth_factor ** (month_index - 1))
            projected = round(projected, 2)
            cumulative = round(cumulative + projected, 2)
            points.append(CostForecastPoint(
                month_index=month_index, projected_monthly_cost=projected, cumulative_cost=cumulative,
            ))

        return CostForecast(
            starting_monthly_cost=round(starting_monthly_cost, 2),
            monthly_growth_percent=monthly_growth_percent,
            months=months,
            points=points,
            total_projected_cost=cumulative,
            currency=currency,
            methodology_note=(
                f"Compounding projection: month N cost = starting cost x (1 + {monthly_growth_percent}%)^(N-1). "
                "The growth rate is a customer/consultant-supplied assumption about future usage, not a data-driven "
                "prediction - GCP list prices themselves are assumed constant over the forecast window."
            ),
        )
