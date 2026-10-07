"""Script to generate a sample shapefile .zip for testing.

Run this script once to create tests/fixtures/sample_shapefile.zip.
Requires: geopandas, shapely
"""

import os
import sys
import zipfile
import tempfile

import geopandas as gpd
from shapely.geometry import Point, LineString, Polygon

# Create sample geometries (near New York City) - Shapefiles only support one geometry type, so we use Polygons
data = {
    "name": ["Central Park Polygon", "Small Park"],
    "category": ["park", "park"],
    "geometry": [
        Polygon([
            (-73.9712, 40.7644),
            (-73.9512, 40.7644),
            (-73.9512, 40.8006),
            (-73.9712, 40.8006),
            (-73.9712, 40.7644),
        ]),
        Polygon([
            (-73.9857, 40.7484),
            (-73.9857, 40.7490),
            (-73.9850, 40.7490),
            (-73.9850, 40.7484),
            (-73.9857, 40.7484),
        ]),
    ],
}

gdf = gpd.GeoDataFrame(data, crs="EPSG:4326")

# Write to temp directory then zip
fixtures_dir = os.path.join(os.path.dirname(__file__))
zip_path = os.path.join(fixtures_dir, "sample_shapefile.zip")

with tempfile.TemporaryDirectory() as tmp_dir:
    shp_path = os.path.join(tmp_dir, "sample.shp")
    gdf.to_file(shp_path, driver="ESRI Shapefile")

    # Zip all shapefile component files
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for fname in os.listdir(tmp_dir):
            fpath = os.path.join(tmp_dir, fname)
            zf.write(fpath, fname)

print(f"Created: {zip_path}")
