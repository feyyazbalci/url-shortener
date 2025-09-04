from pydantic import BaseModel, ConfigDict
from typing import Optional, Any
from datetime import datetime

class BaseSchema(BaseModel):
    """Common base schema for all models."""
    
    model_config = ConfigDict(
        from_attributes=True,
        json_encoders={
            datetime: lambda v: v.isoformat() if v else None
        },
        str_strip_whitespace=True,
        validate_assignment=True,
        arbitrary_types_allowed=True,
    )

class TimestampSchema(BaseSchema):
    created_at: datetime
    updated_at: datetime

class PaginationParams(BaseSchema):

    limit: int = 10
    offset: int = 0

    def __init__(self, **data):
        super().__init__(**data)

        if self.limit > 100:
            self.limit = 100
        if self.limit < 1:
            self.limit = 1
        if self.offset < 0:
            self.offset = 0

class PaginationResponse(BaseSchema):
    total: int
    limit: int
    offset: int
    has_next: bool
    has_prev: bool

    def __init__(self, items: list, total: int, limit: int, offset: int, **data):
        has_next = offset + limit < total
        has_prev = offset > 0

        super().__init__(
            total=total,
            limit=limit,
            offset=offset,
            has_next=has_next,
            has_prev=has_prev,
            **data
        )

class SuccessResponse(BaseSchema):
    
    success: bool = True
    message: str
    data: Optional[Any] = None

class ErrorResponse(BaseSchema):
    success: bool = False
    error: str
    details: Optional[dict] = None
    code: Optional[str] = None

class HealthCheckResponse(BaseSchema):
    """Health check response."""
    
    status: str  # "healthy", "unhealthy"
    timestamp: datetime
    services: dict[str, bool]  # service_name -> is_healthy
    version: str