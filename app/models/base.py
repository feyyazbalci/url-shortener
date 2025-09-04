from sqlalchemy import Column, DateTime, func
from sqlalchemy.ext.declarative import declared_attr
from datetime import datetime
from app.core.database import Base

class TimestampMixin:

    @declared_attr
    def created_at(cls):
        return Column(
            DateTime(timezone=True),
            server_default=func.now(),
            nullable=False,
            doc="Timestamp when the record was created"
        )
    
    @declared_attr
    def updated_at(cls):
        return Column(
            DateTime(timezone=True),
            server_default=func.now(),
            onupdate=func.now(),
            nullable=False,
            doc="Timestamp when the record was last updated"
        )
    
class BaseModel(Base, TimestampMixin):
    """Base model for all database tables."""
    
    __abstract__ = True
    
    def to_dict(self) -> dict:
        return {
            column.name: getattr(self, column.name)
            for column in self.__table__.columns
        }
    
    def __repr__(self):
        """String representation."""
        class_name = self.__class__.__name__
        attrs = []
        
        # Primary key değerlerini al
        for col in self.__table__.primary_key.columns:
            value = getattr(self, col.name, None)
            if value is not None:
                attrs.append(f"{col.name}={value!r}")
        
        attrs_str = ", ".join(attrs) if attrs else "no_pk"
        return f"<{class_name}({attrs_str})>"
    
    def __str__(self):
        """User-friendly string representation."""
        return self.__repr__()