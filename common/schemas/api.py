"""Shared API request/response schemas.

Standardizes health check, error, and pagination payloads across backends.
"""

from typing import Any, Generic, Optional, TypeVar
from pydantic import BaseModel, Field

T = TypeVar("T")


class HealthResponse(BaseModel):
    """Standard health check response schema."""

    status: str = Field(default="healthy", description="Status of the application (healthy, degraded, down)")
    version: str = Field(default="0.1.0", description="Application version number")
    details: dict[str, Any] = Field(default_factory=dict, description="Additional health and resource details")


class ErrorResponse(BaseModel):
    """Standard error response payload."""

    error_code: str = Field(..., description="Unique error code identifier")
    message: str = Field(..., description="Human-readable error description")
    details: Optional[dict[str, Any]] = Field(default=None, description="Detailed error information or context")


class PaginatedResponse(BaseModel, Generic[T]):
    """Standard wrapper for paginated collections."""

    items: list[T] = Field(..., description="List of items in the current page")
    total: int = Field(..., description="Total number of items in the collection")
    page: int = Field(..., description="Current page number (1-indexed)")
    size: int = Field(..., description="Number of items per page")
    pages: int = Field(..., description="Total number of pages")


from datetime import datetime


class IdentitySummary(BaseModel):
    """Summary representation of a user identity."""

    id: str
    provider: str
    provider_id: str
    email: str
    created_at: datetime
    last_used_at: Optional[datetime] = None


class HubMembershipSummary(BaseModel):
    """Summary representation of a hub membership for a user."""

    id: str
    hub_id: str
    hub_name: Optional[str] = None
    hub_slug: Optional[str] = None
    hub_type: Optional[str] = None
    hub_role: str
    created_at: datetime


class UserSummary(BaseModel):
    """Basic summary representation of a user."""

    id: str
    email: str
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    platform_role: str
    status: str
    created_at: datetime
    last_login: Optional[datetime] = None


class UserDetail(UserSummary):
    """Detailed user record including identities and hub memberships."""

    password_updated_at: Optional[datetime] = None
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    failed_login_count: int = 0
    locked_until: Optional[datetime] = None
    identities: list[IdentitySummary] = Field(default_factory=list)
    hub_memberships: list[HubMembershipSummary] = Field(default_factory=list)


class InviteGrant(BaseModel):
    """Pre-assigned hub grant included in an invitation."""

    hub_id: str
    hub_role: str


class InviteCreate(BaseModel):
    """Payload for creating a new user invitation."""

    email: str
    platform_role: str = "member"
    hub_grants: list[InviteGrant] = Field(default_factory=list)


class InviteSummary(BaseModel):
    """Summary representation of a user invite."""

    id: str
    email: str
    platform_role: str
    hub_grants_json: list[dict[str, Any]] = Field(default_factory=list)
    invited_by: Optional[str] = None
    status: str
    expires_at: datetime
    accepted_at: Optional[datetime] = None
    accepted_user_id: Optional[str] = None
    resend_count: int = 0
    last_sent_at: Optional[datetime] = None
    created_at: datetime
    invite_url: Optional[str] = None


class DatastoreBindingResponse(BaseModel):
    """Response schema for datastore binding metadata. Excludes plaintext & encrypted credentials."""

    id: str
    hub_id: str
    name: str
    store_type: str
    connection_uri: str
    is_default: bool = False
    is_synthetic: bool = False
    health_status: str = "healthy"
    last_health_check: Optional[datetime] = None
    config: dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class CollectionResponse(BaseModel):
    """Response schema for an Ingestion Hub collection."""

    id: str
    hub_id: str
    name: str
    physical_name: str
    embedding_model: str
    vector_dimension: int
    description: Optional[str] = None
    retrieval_config: dict[str, Any] = Field(default_factory=dict)
    pipeline_config: dict[str, Any] = Field(default_factory=dict)
    datastore_binding_id: Optional[str] = None
    points_count: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class IngestionJobResponse(BaseModel):
    """Response schema for an ingestion job in a hub."""

    job_id: str
    hub_id: str
    collection_id: Optional[str] = None
    document_id: Optional[str] = None
    status: str
    progress: float = 0.0
    error_msg: Optional[str] = None
    pipeline_config: dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class DocumentResponse(BaseModel):
    """Response schema for an ingested document in a hub collection."""

    id: str
    hub_id: str
    collection_id: str
    filename: str
    file_hash: str
    file_type: str = "unknown"
    created_at: Optional[datetime] = None


class SearchHit(BaseModel):
    """Schema for an individual retrieval hit."""

    id: str
    hub_id: str
    collection_id: str
    collection_name: Optional[str] = None
    document_id: Optional[str] = None
    score: float
    text: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class SearchResponse(BaseModel):
    """Response schema for multi-collection/hybrid search."""

    status: str = "success"
    query: str
    count: int
    results: list[SearchHit] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


