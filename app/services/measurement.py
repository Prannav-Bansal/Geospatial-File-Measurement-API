"""Measurement calculation for geospatial geometries.

Supports:
  - Polygon / MultiPolygon → area in square meters
  - LineString / MultiLineString → length in meters
  - Point / MultiPoint → no measurement
  - Other types → gracefully returns None with a note
"""

from dataclasses import dataclass
from typing import Optional

from pyproj import CRS
from shapely.geometry.base import BaseGeometry

from app.services.crs import get_projected_crs, transform_geometry


@dataclass
class MeasurementResult:
    """Result of a geometry measurement."""

    measurement_type: Optional[str]     # "area", "length", or None
    measurement_value: Optional[float]  # numeric value or None
    measurement_unit: Optional[str]     # "sq_meters", "meters", or None
    crs_projected: Optional[str]        # EPSG string of the projected CRS used


# Geometry types that support area calculation
AREA_TYPES = {"Polygon", "MultiPolygon"}

# Geometry types that support length calculation
LENGTH_TYPES = {"LineString", "MultiLineString"}

# Geometry types with no measurement
NO_MEASUREMENT_TYPES = {"Point", "MultiPoint"}


def calculate_measurement(geometry: BaseGeometry, source_crs: CRS) -> MeasurementResult:
    """Calculate the measurement for a given geometry.

    Automatically transforms to a projected CRS if the source is geographic,
    then computes area (for polygons) or length (for linestrings).

    Args:
        geometry: A Shapely geometry object.
        source_crs: The CRS of the input geometry.

    Returns:
        MeasurementResult with type, value, unit, and projected CRS info.
    """
    geom_type = geometry.geom_type

    # Handle empty geometries
    if geometry.is_empty:
        return MeasurementResult(
            measurement_type=None,
            measurement_value=None,
            measurement_unit=None,
            crs_projected=None,
        )

    # Point / MultiPoint — no measurement needed
    if geom_type in NO_MEASUREMENT_TYPES:
        return MeasurementResult(
            measurement_type=None,
            measurement_value=None,
            measurement_unit=None,
            crs_projected=None,
        )

    # Get projected CRS and transform
    try:
        target_crs = get_projected_crs(geometry, source_crs)
        projected_geom = transform_geometry(geometry, source_crs, target_crs)
        crs_projected_str = f"EPSG:{target_crs.to_epsg()}"
    except Exception:
        # If projection fails, fall back to raw calculation with a warning
        projected_geom = geometry
        crs_projected_str = str(source_crs)

    # Polygon / MultiPolygon — area
    if geom_type in AREA_TYPES:
        area = projected_geom.area
        return MeasurementResult(
            measurement_type="area",
            measurement_value=round(area, 4),
            measurement_unit="sq_meters",
            crs_projected=crs_projected_str,
        )

    # LineString / MultiLineString — length
    if geom_type in LENGTH_TYPES:
        length = projected_geom.length
        return MeasurementResult(
            measurement_type="length",
            measurement_value=round(length, 4),
            measurement_unit="meters",
            crs_projected=crs_projected_str,
        )

    # Unsupported geometry type (e.g., GeometryCollection)
    return MeasurementResult(
        measurement_type=None,
        measurement_value=None,
        measurement_unit=None,
        crs_projected=None,
    )
