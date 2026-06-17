from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
for package_dir in [
    ROOT / "packages" / "domain-engine",
    ROOT / "packages" / "risk-engine",
]:
    if str(package_dir) not in sys.path:
        sys.path.insert(0, str(package_dir))

from domain_engine import DomainType
from risk_engine.engine import contextual_risk_score


def test_automotive_contextual_risk_score_uses_asil_weight() -> None:
    score = contextual_risk_score(
        domain=DomainType.AUTOMOTIVE,
        cvss_v3=8.0,
        reachability_score=1.2,
        exposure_factor=1.1,
        asil="D",
    )

    assert score == pytest.approx(8.0 * 3.0 * 1.2 * 1.1)


def test_medical_contextual_risk_score_uses_sil_weight() -> None:
    score = contextual_risk_score(
        domain=DomainType.MEDICAL,
        cvss_v3=7.0,
        reachability_score=1.0,
        sil=3,
    )

    assert score == pytest.approx(7.0 * 2.0 * 1.0)
