"""Selection strategies used to resolve an unsupported requested numeric value
(e.g. vCPU count) to the nearest supported value from a discrete catalog set.

- CONSERVATIVE: nearest lower supported value (favors cost control)
- BALANCED:     mathematically closest supported value (ties favor higher)
- PERFORMANCE:  nearest higher supported value (favors headroom/SLA)

If no value exists on the requested side (e.g. performance strategy but
requested value exceeds every supported option), the engine falls back to the
closest available value and this is called out in the reason string.
"""
from app.core.config import NormalizationStrategy


def select_value(requested: float, supported_values: list[float], strategy: NormalizationStrategy) -> tuple[float, str]:
    """Returns (selected_value, reason_suffix)."""
    if not supported_values:
        raise ValueError("No supported values to select from.")

    options = sorted(set(supported_values))

    if requested in options:
        return requested, "exact match"

    lower_options = [v for v in options if v < requested]
    higher_options = [v for v in options if v > requested]

    if strategy == NormalizationStrategy.CONSERVATIVE:
        if lower_options:
            return max(lower_options), "nearest lower supported value (conservative strategy)"
        return min(higher_options), "no lower value available; used nearest higher value"

    if strategy == NormalizationStrategy.PERFORMANCE:
        if higher_options:
            return min(higher_options), "nearest higher supported value (performance strategy)"
        return max(lower_options), "no higher value available; used nearest lower value"

    # BALANCED (default): mathematically closest, ties resolved upward.
    best = min(options, key=lambda v: (abs(v - requested), -v))
    return best, "mathematically closest supported value (balanced strategy)"
