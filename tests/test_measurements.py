"""Tests for measurement calculations and the measurements endpoint."""

import pytest
from shapely.geometry import Point, LineString, Polygon, GeometryCollection
from pyproj import CRS

from app.services.measurement import calculate_measurement
from app.services.crs import get_utm_epsg, is_geographic_crs


# ── Unit tests for CRS utilities ──────────────────────────────────────────────


class TestCRSUtils:
    """Tests for CRS utility functions."""

    def test_utm_epsg_northern_hemisphere(self):
        """Test UTM zone calculation for a point in the northern hemisphere."""
        # New York City: lon=-74, lat=40.7 → UTM zone 18N → EPSG:32618
        epsg = get_utm_epsg(-74.0, 40.7)
        assert epsg == 32618

    def test_utm_epsg_southern_hemisphere(self):
        """Test UTM zone calculation for a point in the southern hemisphere."""
        # Sydney: lon=151.2, lat=-33.9 → UTM zone 56S → EPSG:32756
        epsg = get_utm_epsg(151.2, -33.9)
        assert epsg == 32756

    def test_utm_epsg_india(self):
        """Test UTM zone for Bangalore, India."""
        # Bangalore: lon=77.6, lat=12.97 → UTM zone 43N → EPSG:32643
        epsg = get_utm_epsg(77.6, 12.97)
        assert epsg == 32643

    def test_is_geographic_crs(self):
        """Test geographic CRS detection."""
        assert is_geographic_crs(CRS.from_epsg(4326)) is True
        assert is_geographic_crs(CRS.from_epsg(32618)) is False


# ── Unit tests for measurements ───────────────────────────────────────────────


class TestMeasurements:
    """Tests for measurement calculation."""

    def test_polygon_area(self):
        """Test area calculation for a polygon."""
        # ~100m x 100m square near the equator
        poly = Polygon([
            (77.5946, 12.9716),
            (77.5956, 12.9716),
            (77.5956, 12.9726),
            (77.5946, 12.9726),
            (77.5946, 12.9716),
        ])
        crs = CRS.from_epsg(4326)
        result = calculate_measurement(poly, crs)

        assert result.measurement_type == "area"
        assert result.measurement_unit == "sq_meters"
        assert result.measurement_value > 0
        # Should be roughly in the range of 100,000 sq meters (0.001° ≈ 111m)
        assert result.measurement_value > 10000
        assert result.crs_projected is not None

    def test_linestring_length(self):
        """Test length calculation for a linestring."""
        line = LineString([
            (77.5946, 12.9716),
            (77.5960, 12.9730),
            (77.5975, 12.9740),
        ])
        crs = CRS.from_epsg(4326)
        result = calculate_measurement(line, crs)

        assert result.measurement_type == "length"
        assert result.measurement_unit == "meters"
        assert result.measurement_value > 0
        # Should be a few hundred meters
        assert result.measurement_value > 100
        assert result.crs_projected is not None

    def test_point_no_measurement(self):
        """Test that points return no measurement."""
        point = Point(77.5946, 12.9716)
        crs = CRS.from_epsg(4326)
        result = calculate_measurement(point, crs)

        assert result.measurement_type is None
        assert result.measurement_value is None
        assert result.measurement_unit is None

    def test_geometry_collection_graceful(self):
        """Test that unsupported geometry types are handled gracefully."""
        gc = GeometryCollection([Point(0, 0), LineString([(0, 0), (1, 1)])])
        crs = CRS.from_epsg(4326)
        result = calculate_measurement(gc, crs)

        assert result.measurement_type is None
        assert result.measurement_value is None

    def test_empty_geometry(self):
        """Test that empty geometries are handled gracefully."""
        empty_poly = Polygon()
        crs = CRS.from_epsg(4326)
        result = calculate_measurement(empty_poly, crs)

        assert result.measurement_type is None
        assert result.measurement_value is None

    def test_measurement_not_in_degrees(self):
        """Verify that area is in meters, not degrees (key CRS requirement)."""
        # A 1° x 1° polygon at the equator is ~12,300 km²
        poly = Polygon([
            (0.0, 0.0),
            (1.0, 0.0),
            (1.0, 1.0),
            (0.0, 1.0),
            (0.0, 0.0),
        ])
        crs = CRS.from_epsg(4326)
        result = calculate_measurement(poly, crs)

        # If calculated in degrees, area would be 1.0
        # In sq meters, it should be ~12.3 billion sq meters
        assert result.measurement_value > 1_000_000_000  # > 1 billion sq_m


# ── Integration tests for the measurements endpoint ───────────────────────────


@pytest.mark.asyncio
async def test_measurements_endpoint(client, sample_kml_path):
    """Test the measurements endpoint returns correct data."""
    # Upload first
    with open(sample_kml_path, "rb") as f:
        upload_response = await client.post(
            "/api/files/",
            files={"file": ("test.kml", f, "application/vnd.google-earth.kml+xml")},
        )

    file_id = upload_response.json()["id"]

    # Get measurements
    response = await client.get(f"/api/files/{file_id}/measurements/")

    assert response.status_code == 200
    data = response.json()
    assert data["file_id"] == file_id
    assert data["crs_original"] is not None
    assert len(data["features"]) == 3

    # Check that we have the expected measurement types
    types = {f["geometry_type"] for f in data["features"]}
    assert "Polygon" in types
    assert "LineString" in types
    assert "Point" in types

    # Find the polygon feature and verify area measurement
    polygon_feature = next(f for f in data["features"] if f["geometry_type"] == "Polygon")
    assert polygon_feature["measurement_type"] == "area"
    assert polygon_feature["measurement_value"] > 0
    assert polygon_feature["measurement_unit"] == "sq_meters"

    # Find the linestring feature and verify length measurement
    line_feature = next(f for f in data["features"] if f["geometry_type"] == "LineString")
    assert line_feature["measurement_type"] == "length"
    assert line_feature["measurement_value"] > 0
    assert line_feature["measurement_unit"] == "meters"

    # Find the point feature and verify no measurement
    point_feature = next(f for f in data["features"] if f["geometry_type"] == "Point")
    assert point_feature["measurement_type"] is None
    assert point_feature["measurement_value"] is None


@pytest.mark.asyncio
async def test_measurements_not_found(client):
    """Test measurements for non-existent file."""
    response = await client.get("/api/files/nonexist/measurements/")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_measurements_shapefile(client, sample_shapefile_zip_path):
    """Test measurements for an uploaded shapefile."""
    with open(sample_shapefile_zip_path, "rb") as f:
        upload_response = await client.post(
            "/api/files/",
            files={"file": ("survey.zip", f, "application/zip")},
        )

    file_id = upload_response.json()["id"]

    response = await client.get(f"/api/files/{file_id}/measurements/")

    assert response.status_code == 200
    data = response.json()
    assert len(data["features"]) == 2

    # All measurements should be in metric units, not degrees
    for feat in data["features"]:
        if feat["measurement_value"] is not None:
            assert feat["measurement_unit"] in ("sq_meters", "meters")
