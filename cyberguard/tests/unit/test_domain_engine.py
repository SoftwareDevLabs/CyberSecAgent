from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
DOMAIN_ENGINE_PATH = ROOT / "packages" / "domain-engine"
if str(DOMAIN_ENGINE_PATH) not in sys.path:
    sys.path.insert(0, str(DOMAIN_ENGINE_PATH))

from domain_engine import DomainSelector, DomainType, StandardsMapper


def test_domain_selector_loads_automotive_profile() -> None:
    selector = DomainSelector()

    profile = selector.select_domain(DomainType.AUTOMOTIVE)

    assert profile.domain == DomainType.AUTOMOTIVE
    assert any(standard.id == "iso21434" for standard in profile.standards)
    assert profile.risk_scoring_parameters["asil"] == "A/B/C/D"
    assert "ota-abuse" in profile.threat_categories


def test_standards_mapper_returns_requirements_and_templates() -> None:
    mapper = StandardsMapper()

    requirements = mapper.get_compliance_requirements("unece-r155")
    templates = mapper.get_artifact_templates(DomainType.AUTOMOTIVE, "unece-r155")

    assert "Article 7 CSMS governance evidence" in requirements.requirements
    template_ids = {template.template_id for template in templates}
    assert "cyber-plan" in template_ids
    assert "r155-notification" in template_ids
