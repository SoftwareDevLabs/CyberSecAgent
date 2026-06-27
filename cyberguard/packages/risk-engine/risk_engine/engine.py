from __future__ import annotations

from domain_engine.models import DomainType

# ASIL weight multipliers (ISO 26262)
_ASIL_WEIGHTS: dict[str, float] = {
    "A": 1.0,
    "B": 1.5,
    "C": 2.0,
    "D": 3.0,
}

# SIL weight multipliers (IEC 62443)
_SIL_WEIGHTS: dict[int, float] = {
    0: 0.5,
    1: 1.0,
    2: 1.5,
    3: 2.0,
}


def contextual_risk_score(
    *,
    domain: DomainType,
    cvss_v3: float,
    reachability_score: float = 1.0,
    exposure_factor: float = 1.0,
    asil: str | None = None,
    sil: int | None = None,
) -> float:
    """Compute a domain-contextual risk score.

    For AUTOMOTIVE domains the score incorporates ASIL safety integrity level.
    For MEDICAL domains it uses SIL (IEC 62443) instead.

    Returns a float rounded to 2 decimal places.
    """
    base = cvss_v3 * reachability_score

    if domain == DomainType.AUTOMOTIVE:
        if asil is None:
            raise ValueError("asil parameter is required for AUTOMOTIVE domain")
        asil_upper = asil.upper()
        if asil_upper not in _ASIL_WEIGHTS:
            raise ValueError(f"Unknown ASIL level: {asil!r}. Must be one of A/B/C/D")
        domain_weight = _ASIL_WEIGHTS[asil_upper]
        score = base * exposure_factor * domain_weight

    elif domain == DomainType.MEDICAL:
        if sil is None:
            raise ValueError("sil parameter is required for MEDICAL domain")
        if sil not in _SIL_WEIGHTS:
            raise ValueError(f"Unknown SIL level: {sil}. Must be 0/1/2/3")
        domain_weight = _SIL_WEIGHTS[sil]
        score = base * domain_weight

    else:
        score = base * exposure_factor

    return round(score, 2)
