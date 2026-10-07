"""API routes for file upload, information, and measurements."""

import os
import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pyproj import CRS

from app.config import UPLOAD_DIR, MAX_FILE_SIZE_BYTES, ALLOWED_EXTENSIONS
from app.database import get_db
from app.models import UploadedFile, Feature, generate_short_id
from app.schemas import (
    FileUploadResponse,
    FileInfoResponse,
    FeatureMeasurement,
    MeasurementsResponse,
)
from app.services.file_parser import parse_file, get_crs_string, FileParseError
from app.services.measurement import calculate_measurement

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/files", tags=["files"])


def _validate_file_extension(filename: str) -> str:
    """Validate uploaded file extension. Returns the lowercased extension."""
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type '{ext}'. Allowed: {', '.join(ALLOWED_EXTENSIONS)}",
        )
    return ext


async def _save_upload(upload_file: UploadFile, file_id: str) -> str:
    """Save uploaded file to disk, return the saved path."""
    ext = Path(upload_file.filename).suffix.lower()
    saved_filename = f"{file_id}{ext}"
    file_path = UPLOAD_DIR / saved_filename

    content = await upload_file.read()

    if len(content) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds maximum size of {MAX_FILE_SIZE_BYTES // (1024 * 1024)} MB.",
        )

    with open(file_path, "wb") as f:
        f.write(content)

    return str(file_path)


@router.post(
    "/",
    response_model=FileUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a geospatial file",
    description="Upload a .zip (Shapefile) or .kml file for processing. "
                "The file is parsed and measurements are calculated synchronously.",
)
async def upload_file(
    file: UploadFile = File(..., description="A .zip (Shapefile) or .kml file"),
    db: AsyncSession = Depends(get_db),
):
    """Upload and process a geospatial file."""

    # Validate extension
    _validate_file_extension(file.filename)

    # Create DB record
    file_id = generate_short_id()
    db_file = UploadedFile(
        id=file_id,
        filename=f"{file_id}{Path(file.filename).suffix.lower()}",
        original_filename=file.filename,
        file_path="",  # will be updated after save
        status="PROCESSING",
    )
    db.add(db_file)

    try:
        # Save file to disk
        saved_path = await _save_upload(file, file_id)
        db_file.file_path = saved_path

        # Parse the geospatial file
        gdf = parse_file(saved_path)

        # Extract CRS
        crs_string = get_crs_string(gdf)
        db_file.crs = crs_string

        # Determine source CRS for measurement transformation
        source_crs = gdf.crs
        if source_crs is None:
            # Default to EPSG:4326 if no CRS specified
            source_crs = CRS.from_epsg(4326)
            db_file.crs = "EPSG:4326 (assumed)"

        # Process each feature
        features = []
        for idx, row in gdf.iterrows():
            geom = row.geometry

            # Extract properties (all columns except geometry)
            props = {}
            for col in gdf.columns:
                if col != "geometry" and col != gdf.geometry.name:
                    val = row[col]
                    # Convert numpy/pandas types to native Python
                    if hasattr(val, "item"):
                        val = val.item()
                    elif hasattr(val, "__str__") and not isinstance(val, (str, int, float, bool, type(None))):
                        val = str(val)
                    props[col] = val

            # Handle null geometry gracefully
            if geom is None or geom.is_empty:
                feature = Feature(
                    file_id=file_id,
                    feature_index=int(idx) if not isinstance(idx, int) else idx,
                    geometry_type=None,
                    geometry_wkt=None,
                    properties=props,
                    crs_projected=None,
                    measurement_type=None,
                    measurement_value=None,
                    measurement_unit=None,
                )
            else:
                # Calculate measurement
                result = calculate_measurement(geom, source_crs)

                feature = Feature(
                    file_id=file_id,
                    feature_index=int(idx) if not isinstance(idx, int) else idx,
                    geometry_type=geom.geom_type,
                    geometry_wkt=geom.wkt,
                    properties=props,
                    crs_projected=result.crs_projected,
                    measurement_type=result.measurement_type,
                    measurement_value=result.measurement_value,
                    measurement_unit=result.measurement_unit,
                )

            features.append(feature)

        db.add_all(features)
        db_file.feature_count = len(features)
        db_file.status = "COMPLETED"

        await db.commit()
        await db.refresh(db_file)

        return FileUploadResponse(
            id=db_file.id,
            filename=db_file.original_filename,
            feature_count=db_file.feature_count,
            crs=db_file.crs,
            status=db_file.status,
        )

    except FileParseError as e:
        db_file.status = "FAILED"
        db_file.error_message = str(e)
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unexpected error processing file")
        db_file.status = "FAILED"
        db_file.error_message = str(e)
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred: {str(e)}",
        )


@router.get(
    "/{file_id}/",
    response_model=FileInfoResponse,
    summary="Get file information",
    description="Returns metadata about an uploaded file, including CRS, feature count, and status.",
)
async def get_file_info(
    file_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get information about an uploaded file."""
    result = await db.execute(
        select(UploadedFile).where(UploadedFile.id == file_id)
    )
    db_file = result.scalar_one_or_none()

    if db_file is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File with id '{file_id}' not found.",
        )

    return FileInfoResponse(
        id=db_file.id,
        filename=db_file.original_filename,
        feature_count=db_file.feature_count,
        crs=db_file.crs,
        status=db_file.status,
        uploaded_at=db_file.uploaded_at.isoformat() if db_file.uploaded_at else None,
        error_message=db_file.error_message,
    )


@router.get(
    "/{file_id}/measurements/",
    response_model=MeasurementsResponse,
    summary="Get feature measurements",
    description="Returns per-feature measurements (area, length) for the uploaded file.",
)
async def get_measurements(
    file_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get measurements for all features in an uploaded file."""
    # Fetch the file
    result = await db.execute(
        select(UploadedFile).where(UploadedFile.id == file_id)
    )
    db_file = result.scalar_one_or_none()

    if db_file is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File with id '{file_id}' not found.",
        )

    if db_file.status != "COMPLETED":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"File processing has not completed. Current status: {db_file.status}",
        )

    # Fetch features ordered by index
    result = await db.execute(
        select(Feature)
        .where(Feature.file_id == file_id)
        .order_by(Feature.feature_index)
    )
    features = result.scalars().all()

    return MeasurementsResponse(
        file_id=db_file.id,
        filename=db_file.original_filename,
        crs_original=db_file.crs,
        features=[
            FeatureMeasurement(
                feature_index=f.feature_index,
                geometry_type=f.geometry_type,
                geometry_wkt=f.geometry_wkt,
                properties=f.properties,
                crs_projected=f.crs_projected,
                measurement_type=f.measurement_type,
                measurement_value=f.measurement_value,
                measurement_unit=f.measurement_unit,
            )
            for f in features
        ],
    )
