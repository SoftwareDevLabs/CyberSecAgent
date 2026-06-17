from __future__ import annotations

from pydantic import BaseModel

from domain_engine import DomainType

try:
    from fastapi import FastAPI
except ImportError:  # pragma: no cover
    FastAPI = None


class RiskScoreRequest(BaseModel):
    sbom_id: str
    domain: DomainType
    asset_context: dict = {}


if FastAPI:
    app = FastAPI(title="CyberGuard API Gateway", version="0.1.0")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/api/v1/risk/score")
    def score_risk(request: RiskScoreRequest) -> dict:
        return {"sbom_id": request.sbom_id, "domain": request.domain, "scores": []}
else:
    app = None
