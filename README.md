# Geospatial File Measurement API

A production-quality REST API built with **FastAPI** that accepts geospatial files (Shapefile `.zip` or `.kml`), extracts features, and calculates measurements (area for polygons, length for linestrings) with automatic CRS transformation.

---

## Table of Contents

- [Setup](#setup)
- [API Documentation](#api-documentation)
- [Architecture](#architecture)
- [Design Decisions](#design-decisions)
- [Learnings](#learnings)
- [Future Scope](#future-scope)

---

## Setup

### Prerequisites

- Python 3.10+
- pip

### Installation

```bash
# Clone the repository
git clone https://github.com/<your-username>/geo-measurement-api.git
cd geo-measurement-api

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Running the Application

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`.

Interactive API docs (Swagger UI): `http://localhost:8000/docs`

### Running Tests

```bash
# Generate the shapefile test fixture (one-time)
python tests/fixtures/create_shapefile_fixture.py

# Run all tests
pytest tests/ -v
```

---

## API Documentation

### Health Check

```
GET /
```

**Response:**
```json
{
  "service": "Geospatial File Measurement API",
  "status": "running",
  "docs": "/docs"
}
```

---

### Upload a File

```
POST /api/files/
```

Upload a geospatial file for processing. Accepts `.zip` (Shapefile) or `.kml`.

**Request:**
```bash
# Upload a KML file
curl -X POST http://localhost:8000/api/files/ \
  -F "file=@survey.kml"

# Upload a Shapefile zip
curl -X POST http://localhost:8000/api/files/ \
  -F "file=@survey.zip"
```

**Response (201 Created):**
```json
{
  "id": "a1b2c3d4",
  "filename": "survey.kml",
  "feature_count": 120,
  "crs": "EPSG:4326",
  "status": "COMPLETED"
}
```

**Error Responses:**
- `400` — Unsupported file type
- `413` — File too large (max 50 MB)
- `422` — File cannot be parsed (invalid shapefile/KML)
- `500` — Unexpected server error

---

### Get File Information

```
GET /api/files/{id}/
```

Returns metadata about a previously uploaded file.

**Request:**
```bash
curl http://localhost:8000/api/files/a1b2c3d4/
```

**Response (200 OK):**
```json
{
  "id": "a1b2c3d4",
  "filename": "survey.kml",
  "feature_count": 120,
  "crs": "EPSG:4326",
  "status": "COMPLETED",
  "uploaded_at": "2024-01-15T10:30:00",
  "error_message": null
}
```

**Error Responses:**
- `404` — File not found

---

### Get Measurements

```
GET /api/files/{id}/measurements/
```

Returns per-feature measurements for all features in the uploaded file.

**Request:**
```bash
curl http://localhost:8000/api/files/a1b2c3d4/measurements/
```

**Response (200 OK):**
```json
{
  "file_id": "a1b2c3d4",
  "filename": "survey.kml",
  "crs_original": "EPSG:4326",
  "features": [
    {
      "feature_index": 0,
      "geometry_type": "Polygon",
      "geometry_wkt": "POLYGON ((77.5946 12.9716, ...))",
      "properties": {"name": "Plot A", "description": "A rectangular plot"},
      "crs_projected": "EPSG:32643",
      "measurement_type": "area",
      "measurement_value": 125430.56,
      "measurement_unit": "sq_meters"
    },
    {
      "feature_index": 1,
      "geometry_type": "LineString",
      "geometry_wkt": "LINESTRING (77.5946 12.9716, ...)",
      "properties": {"name": "Road B"},
      "crs_projected": "EPSG:32643",
      "measurement_type": "length",
      "measurement_value": 3421.78,
      "measurement_unit": "meters"
    },
    {
      "feature_index": 2,
      "geometry_type": "Point",
      "geometry_wkt": "POINT (77.5946 12.9716)",
      "properties": {"name": "Station C"},
      "crs_projected": null,
      "measurement_type": null,
      "measurement_value": null,
      "measurement_unit": null
    }
  ]
}
```

**Error Responses:**
- `404` — File not found
- `409` — File processing not completed (status is PENDING/PROCESSING/FAILED)

---

## Architecture

### Application Structure

```
app/
├── main.py              # FastAPI app entry point, lifespan events, middleware
├── config.py            # Environment-based configuration
├── database.py          # SQLAlchemy async engine and session management
├── models.py            # ORM models (UploadedFile, Feature)
├── schemas.py           # Pydantic request/response schemas
├── routers/
│   └── files.py         # /api/files/ endpoint handlers
└── services/
    ├── file_parser.py   # Shapefile/KML parsing via Fiona + GeoPandas
    ├── measurement.py   # Area/length calculation with CRS transformation
    └── crs.py           # UTM zone auto-detection and geometry transformation
```

### File-Processing Flow

1. **Upload** — Client sends a `POST /api/files/` with a file attachment
2. **Validation** — File extension is checked (`.zip` or `.kml` only)
3. **Save** — File is saved to `uploads/` directory with a unique ID
4. **Parse** — Fiona/GeoPandas reads the file into a GeoDataFrame
   - `.zip`: Extracted to temp dir → locate `.shp` → read
   - `.kml`: Read directly with Fiona's KML driver
5. **Extract CRS** — Read from file metadata; defaults to EPSG:4326 if absent
6. **Process Features** — For each feature:
   - Extract geometry type, WKT, and properties
   - Calculate measurements (if applicable)
7. **Persist** — Store file metadata and feature data in SQLite
8. **Response** — Return file ID, feature count, CRS, and status

### Measurement Calculation Flow

1. Check geometry type (Polygon, LineString, Point, etc.)
2. If the source CRS is geographic (lat/lon), compute the target UTM zone
3. Transform geometry from source CRS to projected CRS
4. Calculate area (polygons) or length (linestrings) in metric units
5. For unsupported geometry types, return `null` measurements gracefully

### CRS Handling

The application uses **automatic UTM zone selection** based on each geometry's centroid:

- **UTM zone number** = `floor((longitude + 180) / 6) + 1`
- **EPSG code** = `326xx` (northern hemisphere) or `327xx` (southern hemisphere)

This ensures accurate metric measurements for any location worldwide. Geographic coordinates (lat/lon degrees) are **never** used directly for area or distance calculations.

---

## Design Decisions

### FastAPI over Django

FastAPI was chosen for its:
- **Async-native** design (better for I/O-bound file operations)
- **Auto-generated OpenAPI docs** at `/docs` (no extra setup)
- **Pydantic validation** for type-safe request/response handling
- **Lightweight footprint** — no ORM/admin overhead when not needed

Django + DRF would be a stronger choice for projects needing admin panels, authentication, or an extensive ORM.

### SQLite over PostgreSQL

SQLite provides zero-configuration setup, making the project easy to clone and run. The schema is designed to be compatible with PostgreSQL — switching requires only changing `DATABASE_URL`.

### Synchronous Processing

File processing happens during the upload request. This keeps the API simple and stateless. For large files, this could be moved to a background task queue (Celery, ARQ) — see [Future Scope](#future-scope).

### UTM Auto-Projection

Rather than requiring users to specify a target CRS, the application auto-detects the appropriate UTM zone from each geometry's centroid. This balances accuracy and usability for worldwide data.

**Alternative considered:** Using a geodesic library (e.g., `geographiclib`) for direct lat/lon calculations. UTM projection was chosen for its simplicity and compatibility with Shapely's native area/length functions.

### Short IDs

8-character hex UUIDs provide URL-friendly identifiers with negligible collision risk for the expected scale. Full UUIDs would be more appropriate for a distributed system.

---

## Learnings

- **Fiona KML driver** requires explicit registration (`fiona.drvsupport.supported_drivers["KML"] = "r"`) as it's not enabled by default
- **CRS detection** in KML files can be tricky — KML is always EPSG:4326 by specification, but GeoPandas may report it differently
- **Shapefile zip handling** requires careful extraction — shapefiles are multi-file formats (`.shp`, `.shx`, `.dbf`, `.prj`) and all components must be present
- **PyProj's `always_xy=True`** is critical when creating transformers to maintain consistent longitude/latitude ordering
- **Async SQLAlchemy** with `aiosqlite` provides non-blocking database access that integrates naturally with FastAPI's async endpoints

---

## Future Scope

- **Background processing** — Use Celery or ARQ for large file processing with status polling
- **PostgreSQL + PostGIS** — Full spatial database with native geometry storage and spatial indexing
- **GeoJSON support** — Accept `.geojson` files in addition to Shapefile and KML
- **Pagination** — Paginate the measurements endpoint for files with thousands of features
- **Authentication** — API key or OAuth2 authentication for production deployment
- **File deletion** — `DELETE /api/files/{id}/` endpoint
- **Export** — Export processed features as GeoJSON or CSV
- **Docker** — Dockerfile and docker-compose for containerized deployment
- **CI/CD** — GitHub Actions for automated testing and deployment
- **Multi-geometry support** — Handle GeometryCollection by decomposing into individual geometries
- **Custom CRS input** — Allow users to specify a target projected CRS
- **Geodesic calculations** — Alternative measurement using geodesic distances for higher accuracy at extreme latitudes
