"""Tests for file upload endpoints."""

import io
from pathlib import Path

import pytest


@pytest.mark.asyncio
async def test_upload_kml(client, sample_kml_path):
    """Test uploading a valid KML file."""
    with open(sample_kml_path, "rb") as f:
        response = await client.post(
            "/api/files/",
            files={"file": ("test.kml", f, "application/vnd.google-earth.kml+xml")},
        )

    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "COMPLETED"
    assert data["filename"] == "test.kml"
    assert data["feature_count"] == 3  # polygon, linestring, point
    assert data["crs"] is not None
    assert "id" in data


@pytest.mark.asyncio
async def test_upload_shapefile_zip(client, sample_shapefile_zip_path):
    """Test uploading a valid shapefile zip."""
    with open(sample_shapefile_zip_path, "rb") as f:
        response = await client.post(
            "/api/files/",
            files={"file": ("test.zip", f, "application/zip")},
        )

    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "COMPLETED"
    assert data["feature_count"] == 2
    assert data["crs"] == "EPSG:4326"


@pytest.mark.asyncio
async def test_upload_invalid_extension(client):
    """Test uploading a file with unsupported extension."""
    content = b"not a geospatial file"
    response = await client.post(
        "/api/files/",
        files={"file": ("test.txt", io.BytesIO(content), "text/plain")},
    )

    assert response.status_code == 400
    assert "Unsupported file type" in response.json()["detail"]


@pytest.mark.asyncio
async def test_upload_invalid_zip(client):
    """Test uploading a zip that doesn't contain a shapefile."""
    import zipfile
    import tempfile
    import os

    # Create a zip with no .shp file
    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
        with zipfile.ZipFile(tmp, "w") as zf:
            zf.writestr("readme.txt", "This is not a shapefile")
        tmp_path = tmp.name

    try:
        with open(tmp_path, "rb") as f:
            response = await client.post(
                "/api/files/",
                files={"file": ("bad.zip", f, "application/zip")},
            )

        assert response.status_code == 422
        assert "No .shp file found" in response.json()["detail"]
    finally:
        os.unlink(tmp_path)


@pytest.mark.asyncio
async def test_get_file_info(client, sample_kml_path):
    """Test getting file information after upload."""
    # Upload first
    with open(sample_kml_path, "rb") as f:
        upload_response = await client.post(
            "/api/files/",
            files={"file": ("survey.kml", f, "application/vnd.google-earth.kml+xml")},
        )

    file_id = upload_response.json()["id"]

    # Get file info
    response = await client.get(f"/api/files/{file_id}/")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == file_id
    assert data["filename"] == "survey.kml"
    assert data["status"] == "COMPLETED"
    assert data["uploaded_at"] is not None


@pytest.mark.asyncio
async def test_get_file_info_not_found(client):
    """Test getting info for non-existent file."""
    response = await client.get("/api/files/nonexist/")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_health_check(client):
    """Test the root health check endpoint."""
    response = await client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "running"
