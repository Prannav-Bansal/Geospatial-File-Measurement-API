"""SQLAlchemy ORM models for uploaded files and their features."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, Integer, Float, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship

from app.database import Base


def generate_short_id() -> str:
    """Generate a short 8-character hex ID."""
    return uuid.uuid4().hex[:8]


class UploadedFile(Base):
    """Represents an uploaded geospatial file."""

    __tablename__ = "uploaded_files"

    id = Column(String(8), primary_key=True, default=generate_short_id)
    filename = Column(String(255), nullable=False)
    original_filename = Column(String(255), nullable=False)
    file_path = Column(String(512), nullable=False)
    crs = Column(String(50), nullable=True)
    feature_count = Column(Integer, default=0)
    status = Column(String(20), default="PENDING")  # PENDING, PROCESSING, COMPLETED, FAILED
    error_message = Column(Text, nullable=True)
    uploaded_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    features = relationship("Feature", back_populates="file", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "filename": self.original_filename,
            "feature_count": self.feature_count,
            "crs": self.crs,
            "status": self.status,
            "uploaded_at": self.uploaded_at.isoformat() if self.uploaded_at else None,
        }


class Feature(Base):
    """Represents a single feature extracted from a geospatial file."""

    __tablename__ = "features"

    id = Column(Integer, primary_key=True, autoincrement=True)
    file_id = Column(String(8), ForeignKey("uploaded_files.id"), nullable=False)
    feature_index = Column(Integer, nullable=False)
    geometry_type = Column(String(50), nullable=True)
    geometry_wkt = Column(Text, nullable=True)
    properties = Column(JSON, nullable=True)
    crs_projected = Column(String(50), nullable=True)
    measurement_type = Column(String(20), nullable=True)   # "area", "length", or None
    measurement_value = Column(Float, nullable=True)
    measurement_unit = Column(String(20), nullable=True)    # "sq_meters", "meters", or None

    file = relationship("UploadedFile", back_populates="features")

    def to_measurement_dict(self):
        return {
            "feature_index": self.feature_index,
            "geometry_type": self.geometry_type,
            "geometry_wkt": self.geometry_wkt,
            "properties": self.properties,
            "crs_projected": self.crs_projected,
            "measurement_type": self.measurement_type,
            "measurement_value": self.measurement_value,
            "measurement_unit": self.measurement_unit,
        }
