from __future__ import annotations

from domain_engine.models import (
    ArtifactTemplate,
    ComplianceRequirements,
    DomainProfile,
    DomainType,
    Standard,
)


class DomainSelector:
    _PROFILES: dict[DomainType, DomainProfile] = {
        DomainType.AUTOMOTIVE: DomainProfile(
            domain=DomainType.AUTOMOTIVE,
            standards=[
                Standard(id="iso21434", name="ISO/SAE 21434", version="2021"),
                Standard(id="unece-r155", name="UNECE WP.29 R155"),
                Standard(id="unece-r156", name="UNECE WP.29 R156"),
                Standard(id="iso8800", name="ISO 8800"),
            ],
            risk_scoring_parameters={
                "asil": "A/B/C/D",
                "cvss_weight": 1.0,
                "exposure_factor": 1.0,
            },
            threat_categories=[
                "remote-code-execution",
                "ota-abuse",
                "can-bus-injection",
                "supply-chain-compromise",
                "spoofing",
                "denial-of-service",
            ],
        ),
        DomainType.MEDICAL: DomainProfile(
            domain=DomainType.MEDICAL,
            standards=[
                Standard(id="iec62443", name="IEC 62443"),
                Standard(id="fda-cybersecurity", name="FDA Cybersecurity Guidance"),
            ],
            risk_scoring_parameters={
                "sil": "0/1/2/3",
                "cvss_weight": 1.0,
            },
            threat_categories=[
                "remote-code-execution",
                "data-exfiltration",
                "denial-of-service",
                "firmware-tampering",
            ],
        ),
    }

    def select_domain(self, domain: DomainType) -> DomainProfile:
        if domain not in self._PROFILES:
            raise ValueError(f"No profile for domain: {domain}")
        return self._PROFILES[domain]


class StandardsMapper:
    _REQUIREMENTS: dict[str, ComplianceRequirements] = {
        "unece-r155": ComplianceRequirements(
            standard_id="unece-r155",
            requirements=[
                "Article 7 CSMS governance evidence",
                "Article 7(2)(a) risk management process",
                "Article 7(2)(b) security monitoring",
                "Article 7(2)(c) incident response",
            ],
        ),
        "iso21434": ComplianceRequirements(
            standard_id="iso21434",
            requirements=[
                "Clause 8 risk assessment",
                "Clause 9 concept phase",
                "Clause 10 product development",
                "Clause 13 vulnerability management",
            ],
        ),
    }

    _TEMPLATES: dict[tuple[DomainType, str], list[ArtifactTemplate]] = {
        (DomainType.AUTOMOTIVE, "unece-r155"): [
            ArtifactTemplate(
                template_id="cyber-plan",
                name="Cybersecurity Plan",
                standard_id="unece-r155",
            ),
            ArtifactTemplate(
                template_id="r155-notification",
                name="R155 Incident Notification",
                standard_id="unece-r155",
            ),
            ArtifactTemplate(
                template_id="csms-evidence",
                name="CSMS Governance Evidence",
                standard_id="unece-r155",
            ),
        ],
    }

    def get_compliance_requirements(self, standard_id: str) -> ComplianceRequirements:
        if standard_id not in self._REQUIREMENTS:
            return ComplianceRequirements(standard_id=standard_id)
        return self._REQUIREMENTS[standard_id]

    def get_artifact_templates(
        self, domain: DomainType, standard_id: str
    ) -> list[ArtifactTemplate]:
        return self._TEMPLATES.get((domain, standard_id), [])


__all__ = [
    "ArtifactTemplate",
    "ComplianceRequirements",
    "DomainProfile",
    "DomainSelector",
    "DomainType",
    "Standard",
    "StandardsMapper",
]
