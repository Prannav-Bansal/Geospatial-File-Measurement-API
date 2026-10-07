"""CRS detection and projection utilities.

Strategy: Auto-select the appropriate UTM zone from the geometry's centroid.
This ensures accurate metric measurements for any location worldwide.

UTM zone calculation:
  zone_number = floor((longitude + 180) / 6) + 1
  EPSG = 326xx (northern hemisphere) or 327xx (southern hemisphere)
"""

import math

from pyproj import CRS, Transformer
from shapely.geometry import shape as shapely_shape
from shapely.ops import transform


def is_geographic_crs(crs: CRS) -> bool:
    """Check if a CRS uses geographic (lat/lon) coordinates."""
    return crs.is_geographic


def get_utm_epsg(longitude: float, latitude: float) -> int:
    """Calculate the EPSG code for the UTM zone covering the given point.

    Args:
        longitude: Longitude in degrees (-180 to 180).
        latitude: Latitude in degrees (-90 to 90).

    Returns:
        EPSG code for the appropriate UTM zone.
    """
    zone_number = int(math.floor((longitude + 180) / 6)) + 1

    # Clamp zone number to valid range
    zone_number = max(1, min(60, zone_number))

    if latitude >= 0:
        # Northern hemisphere: EPSG:326xx
        return 32600 + zone_number
    else:
        # Southern hemisphere: EPSG:327xx
        return 32700 + zone_number


def get_projected_crs(geometry, source_crs: CRS) -> CRS:
    """Determine the best projected CRS for measuring a geometry.

    If the source CRS is already projected (metric), return it as-is.
    If it's geographic, auto-detect the UTM zone from the geometry centroid.

    Args:
        geometry: A Shapely geometry object.
        source_crs: The source CRS of the geometry.

    Returns:
        A projected CRS suitable for metric measurements.
    """
    if not is_geographic_crs(source_crs):
        return source_crs

    centroid = geometry.centroid
    utm_epsg = get_utm_epsg(centroid.x, centroid.y)
    return CRS.from_epsg(utm_epsg)


def transform_geometry(geometry, source_crs: CRS, target_crs: CRS):
    """Transform a Shapely geometry from one CRS to another.

    Args:
        geometry: A Shapely geometry object.
        source_crs: The source CRS.
        target_crs: The target CRS.

    Returns:
        The transformed geometry.
    """
    if source_crs == target_crs:
        return geometry

    transformer = Transformer.from_crs(source_crs, target_crs, always_xy=True)
    return transform(transformer.transform, geometry)
