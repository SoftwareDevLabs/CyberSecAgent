from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class DomainType(str, Enum):
    AUTOMOTIVE = "automotive"
    MEDICAL = "medical"
    RAILWAY = "railway"
    AEROSPACE = "aerospace"


@dataclass
class Standard:
    id: str
    name: str
    version: str = ""


@dataclass
class DomainProfile:
    domain: DomainType
    standards: list[Standard] = field(default_factory=list)
    risk_scoring_parameters: dict = field(default_factory=dict)
    threat_categories: list[str] = field(default_factory=list)


@dataclass
class ComplianceRequirements:
    standard_id: str
    requirements: list[str] = field(default_factory=list)


@dataclass
class ArtifactTemplate:
    template_id: str
    name: str
    standard_id: str
