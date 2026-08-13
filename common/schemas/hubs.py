"""Pydantic v2 transport schemas for Hubs, Memberships, Links, Datastore Bindings and Audit Logs (hubs.md §3, §8)."""

from datetime import datetime
from typing import Literal, Optional, Any
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SecretStr,
    field_validator,
    model_validator,
)

HubType = Literal["ingestion", "agent", "workflow", "eval"]
HubRole = Literal["owner", "maintainer", "contributor", "viewer"]
LinkAccess = Literal["read", "use"]
StoreType = Literal["qdrant", "neo4j", "postgres", "opensearch"]

RESERVED_SLUGS = frozenset({"new", "admin", "settings"})


class InitialLinkCreate(BaseModel):
    target_hub_id: str
    access_level: LinkAccess = "use"


class HubBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class HubCreate(HubBase):
    name: str = Field(min_length=1, max_length=120)
    hub_type: HubType
    slug: str = Field(pattern=r"^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$", max_length=64)
    description: Optional[str] = Field(default=None, max_length=2000)
    accent: Optional[str] = Field(default=None, max_length=20)
    icon: Optional[str] = Field(default=None, max_length=40)
    settings_json: dict[str, Any] = Field(default_factory=dict)
    initial_links: Optional[list[InitialLinkCreate]] = Field(default_factory=list)

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, v: str) -> str:
        slug_lower = v.lower()
        if slug_lower in RESERVED_SLUGS:
            raise ValueError(f"Slug '{v}' is reserved and cannot be used for a hub.")
        return slug_lower


class HubUpdate(HubBase):
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    slug: Optional[str] = Field(default=None, pattern=r"^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$", max_length=64)
    description: Optional[str] = Field(default=None, max_length=2000)
    accent: Optional[str] = Field(default=None, max_length=20)
    icon: Optional[str] = Field(default=None, max_length=40)
    settings_json: Optional[dict[str, Any]] = None

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        slug_lower = v.lower()
        if slug_lower in RESERVED_SLUGS:
            raise ValueError(f"Slug '{v}' is reserved and cannot be used for a hub.")
        return slug_lower


class HubSummary(HubBase):
    id: str
    slug: str
    name: str
    hub_type: HubType
    accent: Optional[str] = None
    icon: Optional[str] = None
    is_archived: bool = False
    my_role: Optional[HubRole] = None
    member_count: int = 0
    resource_count: int = 0


class HubRead(HubSummary):
    description: Optional[str] = None
    settings_json: dict[str, Any] = Field(default_factory=dict)
    owner_id: str
    created_at: datetime
    updated_at: datetime


class HubMemberCreate(HubBase):
    user_id: Optional[str] = None
    email: Optional[str] = Field(default=None, pattern=r"^[^@]+@[^@]+\.[^@]+$")
    hub_role: HubRole

    @model_validator(mode="after")
    def validate_target(self) -> "HubMemberCreate":
        if (self.user_id is None and self.email is None) or (self.user_id is not None and self.email is not None):
            raise ValueError("Exactly one of 'user_id' or 'email' must be supplied.")
        return self


class HubMemberUpdate(HubBase):
    hub_role: HubRole


class HubMemberRead(HubBase):
    id: str
    hub_id: str
    user_id: str
    email: Optional[str] = None
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    hub_role: HubRole
    invited_by: Optional[str] = None
    created_at: datetime


class HubLinkCreate(HubBase):
    target_hub_id: str
    access_level: LinkAccess = "read"


class HubLinkRead(HubBase):
    id: str
    source_hub_id: str
    target_hub_id: str
    source_hub_name: Optional[str] = None
    source_hub_type: Optional[HubType] = None
    target_hub_name: Optional[str] = None
    target_hub_type: Optional[HubType] = None
    target_hub_slug: Optional[str] = None
    access_level: LinkAccess
    created_by: Optional[str] = None
    created_at: datetime


class DatastoreBindingCreate(HubBase):
    name: str = Field(max_length=120)
    store_type: StoreType
    connection_uri: str = Field(max_length=500)
    credentials: Optional[SecretStr] = None
    is_default: bool = False
    config_json: dict[str, Any] = Field(default_factory=dict)


class DatastoreBindingUpdate(HubBase):
    name: Optional[str] = Field(default=None, max_length=120)
    store_type: Optional[StoreType] = None
    connection_uri: Optional[str] = Field(default=None, max_length=500)
    credentials: Optional[SecretStr] = None
    is_default: Optional[bool] = None
    config_json: Optional[dict[str, Any]] = None


class DatastoreBindingRead(HubBase):
    # Security Invariant: NO credentials or credentials_encrypted field exists here!
    id: Optional[str] = None
    hub_id: Optional[str] = None
    name: str
    store_type: StoreType
    connection_uri: str
    has_credentials: bool = False
    is_default: bool = False
    health_status: str = "unknown"
    last_health_check: Optional[datetime] = None
    is_platform_default: bool = False
    config_json: dict[str, Any] = Field(default_factory=dict)


class AuditLogRead(HubBase):
    id: str
    hub_id: Optional[str] = None
    hub_name: Optional[str] = None
    actor_user_id: Optional[str] = None
    actor_email: Optional[str] = None
    action: str
    resource_type: str
    resource_id: Optional[str] = None
    summary: Optional[str] = None
    before_json: Optional[Any] = None
    after_json: Optional[Any] = None
    ip_address: Optional[str] = None
    created_at: datetime


class AuditLogFilter(HubBase):
    hub_id: Optional[str] = None
    actor_user_id: Optional[str] = None
    action: Optional[str] = None
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    since: Optional[datetime] = None
    until: Optional[datetime] = None
    limit: int = Field(default=50, ge=1, le=500)
    offset: int = Field(default=0, ge=0)
