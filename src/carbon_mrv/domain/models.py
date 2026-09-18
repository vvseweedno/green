from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class AnalysisRequest(BaseModel):
    geometry: dict[str, Any]
    year_start: int = Field(ge=2019, le=2024)
    year_end: int = Field(ge=2019, le=2024)
    data_mode: Literal["auto", "offline", "online"] = "auto"
    parent_aoi_id: str | None = None
    uncertainty_scenario: Literal["independent", "moderate", "strong"] = "moderate"

    @model_validator(mode="after")
    def _years(self) -> "AnalysisRequest":
        if self.year_end <= self.year_start:
            raise ValueError("year_end must be greater than year_start")
        return self


class CoverageResult(BaseModel):
    requested_area_ha: float
    computed_area_ha: float
    coverage_ratio: float
    missing_area_ha: float
    reason: str | None = None


class StockPoint(BaseModel):
    year: int
    area_ha: float
    total_carbon_t: float
    mean_carbon_t_ha: float
    annual_delta_c_t: float | None = None
    annual_E_tco2e: float | None = None
    cumulative_delta_c_t: float = 0.0
    cumulative_E_tco2e: float = 0.0


class UncertaintyPayload(BaseModel):
    L: float
    U: float
    method: str
    assumptions: dict[str, Any]
    sensitivity: list[dict[str, Any]] = Field(default_factory=list)


class CreditsPayload(BaseModel):
    status: Literal["available", "unavailable"]
    reason: str | None = None
    R: float | None = None
    H: float | None = None
    H_over_R: float | None = None
    UNC: float | None = None
    Radj: float | None = None
    buffer: float | None = None
    Q: int | None = None
    scenario_values_rub: list[dict[str, Any]] = Field(default_factory=list)
    price_scenario_disclaimer: str | None = None


class AnalysisResult(BaseModel):
    run_id: UUID = Field(default_factory=uuid4)
    created_at_utc: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: str = "completed"
    request: AnalysisRequest
    coverage: CoverageResult
    stock: dict[str, Any]
    uncertainty: UncertaintyPayload | None = None
    events: list[dict[str, Any]] = Field(default_factory=list)
    layers: list[dict[str, Any]] = Field(default_factory=list)
    baseline: dict[str, Any] | None = None
    credits: CreditsPayload
    provenance: dict[str, Any] = Field(default_factory=dict)
    limitations: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
