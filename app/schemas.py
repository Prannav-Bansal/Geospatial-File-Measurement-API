"""Pydantic schemas for API request/response validation."""

from __future__ import annotations

from typing import Any, Optional
from pydantic import BaseModel


class FileUploadResponse(BaseModel):
    """Response after uploading a file."""

    id: str
    filename: str
    feature_count: int
    crs: Optional[str] = None
    status: str

    model_config = {"from_attributes": True}


class FileInfoResponse(BaseModel):
    """Detailed file information."""

    id: str
    filename: str
    feature_count: int
    crs: Optional[str] = None
    status: str
    uploaded_at: Optional[str] = None
    error_message: Optional[str] = None

    model_config = {"from_attributes": True}


class FeatureMeasurement(BaseModel):
    """Measurement data for a single feature."""

    feature_index: int
    geometry_type: Optional[str] = None
    geometry_wkt: Optional[str] = None
    properties: Optional[dict[str, Any]] = None
    crs_projected: Optional[str] = None
    measurement_type: Optional[str] = None
    measurement_value: Optional[float] = None
    measurement_unit: Optional[str] = None


class MeasurementsResponse(BaseModel):
    """Response containing measurements for all features in a file."""

    file_id: str
    filename: str
    crs_original: Optional[str] = None
    features: list[FeatureMeasurement] = []


class ErrorResponse(BaseModel):
    """Standard error response."""

    detail: str
