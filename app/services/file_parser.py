"""Geospatial file parsing for Shapefiles (.zip) and KML (.kml).

Uses Fiona + GeoPandas to read files into a GeoDataFrame,
then extracts per-feature information including geometry and properties.
"""

import os
import tempfile
import zipfile
from pathlib import Path
from typing import Optional

import fiona
import geopandas as gpd
from pyproj import CRS

# Enable KML driver in Fiona
fiona.drvsupport.supported_drivers["KML"] = "r"


class FileParseError(Exception):
    """Raised when a geospatial file cannot be parsed."""
    pass


def _find_shapefile_in_zip(zip_path: str) -> str:
    """Locate the .shp file inside a zip archive.

    Args:
        zip_path: Path to the zip file.

    Returns:
        The virtual filesystem path for reading the shapefile via Fiona.

    Raises:
        FileParseError: If no .shp file is found in the archive.
    """
    with zipfile.ZipFile(zip_path, "r") as zf:
        shp_files = [f for f in zf.namelist() if f.lower().endswith(".shp")]
        if not shp_files:
            raise FileParseError("No .shp file found inside the uploaded zip archive.")
        # Use the first .shp found
        return shp_files[0]


def parse_shapefile_zip(zip_path: str) -> gpd.GeoDataFrame:
    """Parse a zipped Shapefile into a GeoDataFrame.

    Extracts the zip to a temporary directory and reads the .shp file.

    Args:
        zip_path: Path to the .zip file containing a Shapefile.

    Returns:
        A GeoDataFrame with the file's features.

    Raises:
        FileParseError: If the zip cannot be read or contains no shapefile.
    """
    try:
        shp_name = _find_shapefile_in_zip(zip_path)

        # Extract to a temp directory, then read the .shp
        with tempfile.TemporaryDirectory() as tmp_dir:
            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(tmp_dir)

            # Find the extracted .shp (may be in a subdirectory)
            shp_path = None
            for root, dirs, files in os.walk(tmp_dir):
                for f in files:
                    if f.lower().endswith(".shp") and f == os.path.basename(shp_name):
                        shp_path = os.path.join(root, f)
                        break
                if shp_path:
                    break

            if not shp_path:
                raise FileParseError("Could not locate extracted .shp file.")

            gdf = gpd.read_file(shp_path)
            return gdf

    except zipfile.BadZipFile:
        raise FileParseError("The uploaded file is not a valid zip archive.")
    except Exception as e:
        if isinstance(e, FileParseError):
            raise
        raise FileParseError(f"Failed to parse shapefile: {str(e)}")


def parse_kml(kml_path: str) -> gpd.GeoDataFrame:
    """Parse a KML file into a GeoDataFrame.

    Args:
        kml_path: Path to the .kml file.

    Returns:
        A GeoDataFrame with the file's features.

    Raises:
        FileParseError: If the KML cannot be read.
    """
    try:
        gdf = gpd.read_file(kml_path, driver="KML")
        return gdf
    except Exception as e:
        raise FileParseError(f"Failed to parse KML file: {str(e)}")


def parse_file(file_path: str) -> gpd.GeoDataFrame:
    """Parse a geospatial file based on its extension.

    Supports:
      - .zip → Shapefile
      - .kml → KML

    Args:
        file_path: Path to the uploaded file.

    Returns:
        A GeoDataFrame with the file's features.

    Raises:
        FileParseError: If the file type is unsupported or parsing fails.
    """
    ext = Path(file_path).suffix.lower()

    if ext == ".zip":
        return parse_shapefile_zip(file_path)
    elif ext == ".kml":
        return parse_kml(file_path)
    else:
        raise FileParseError(f"Unsupported file type: {ext}. Expected .zip or .kml")


def get_crs_string(gdf: gpd.GeoDataFrame) -> Optional[str]:
    """Extract a human-readable CRS string from a GeoDataFrame.

    Args:
        gdf: A GeoDataFrame.

    Returns:
        CRS string like "EPSG:4326", or None if no CRS is set.
    """
    if gdf.crs is None:
        return None

    epsg = gdf.crs.to_epsg()
    if epsg:
        return f"EPSG:{epsg}"

    # Fall back to WKT representation
    return str(gdf.crs)
