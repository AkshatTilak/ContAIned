"""Unit tests for Hub Repository layer, hub schemas and scoped accessors (S6-01f)."""

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from common.models.database import Base, AgentDefinition, User, ModelRegistryModel
from common.schemas.hubs import (
    HubCreate,
    DatastoreBindingRead,
)
from common.services.hub_repository import (
    get_scoped,
    create_hub,
    list_hubs_for_user,
    delete_hub_if_empty,
    remove_member,
    upsert_member,
    create_link,
    HubNotEmptyError,
    LastOwnerError,
    DuplicateSlugError,
    InvalidLinkDirectionError,
)


@pytest_asyncio.fixture
async def async_session():
    """Fixture creating an in-memory SQLite async database."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session_factory = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    async with async_session_factory() as session:
        # Seed a test user
        user = User(id="user-1", email="user1@example.com", display_name="User One")
        admin_user = User(id="admin-1", email="admin1@example.com", display_name="Admin One")
        session.add_all([user, admin_user])
        await session.commit()
        yield session

    await engine.dispose()


@pytest.mark.asyncio
async def test_create_hub_and_membership(async_session: AsyncSession):
    """create_hub creates both Hub and owner HubMember in one transaction."""
    hub_data = HubCreate(
        name="Test Ingestion",
        hub_type="ingestion",
        slug="test-ingest",
        description="A test hub",
    )
    hub = await create_hub(async_session, data=hub_data, owner_id="user-1")
    await async_session.commit()

    assert hub.id is not None
    assert hub.slug == "test-ingest"
    assert hub.hub_type == "ingestion"

    # Verify membership created
    user_hubs = await list_hubs_for_user(async_session, user_id="user-1")
    assert len(user_hubs) == 1
    assert user_hubs[0][0].id == hub.id
    assert user_hubs[0][1] == "owner"


@pytest.mark.asyncio
async def test_create_hub_duplicate_slug(async_session: AsyncSession):
    """create_hub raises DuplicateSlugError if slug exists for hub_type."""
    data = HubCreate(name="Hub 1", hub_type="agent", slug="support-agent")
    await create_hub(async_session, data=data, owner_id="user-1")
    await async_session.commit()

    with pytest.raises(DuplicateSlugError):
        await create_hub(async_session, data=data, owner_id="user-1")


@pytest.mark.asyncio
async def test_get_scoped_isolation(async_session: AsyncSession):
    """get_scoped returns row for matching hub_id and None for foreign hub_id."""
    hub1 = await create_hub(
        async_session,
        data=HubCreate(name="Hub 1", hub_type="agent", slug="agent-hub-1"),
        owner_id="user-1",
    )
    hub2 = await create_hub(
        async_session,
        data=HubCreate(name="Hub 2", hub_type="agent", slug="agent-hub-2"),
        owner_id="user-1",
    )
    await async_session.commit()

    agent = AgentDefinition(
        id="agent-123",
        hub_id=hub1.id,
        name="Test Agent",
        role="router",
        system_prompt="Test prompt",
        model_id="gpt-4o",
        endpoint_slug="test-agent",
    )
    async_session.add(agent)
    await async_session.commit()

    # Query with matching hub_id -> returns row
    fetched = await get_scoped(async_session, AgentDefinition, hub_id=hub1.id, resource_id="agent-123")
    assert fetched is not None
    assert fetched.id == "agent-123"

    # Query with foreign hub_id -> returns None (preventing IDOR)
    foreign_fetched = await get_scoped(async_session, AgentDefinition, hub_id=hub2.id, resource_id="agent-123")
    assert foreign_fetched is None


@pytest.mark.asyncio
async def test_get_scoped_non_hub_scoped_model(async_session: AsyncSession):
    """get_scoped raises TypeError for non-hub-scoped models."""
    with pytest.raises(TypeError) as excinfo:
        await get_scoped(async_session, ModelRegistryModel, hub_id="some-hub", resource_id="res-1")
    assert "is not hub-scoped" in str(excinfo.value)


@pytest.mark.asyncio
async def test_list_hubs_for_platform_admin(async_session: AsyncSession):
    """Platform admin gets list of all hubs with 'owner' role when is_platform_admin=True."""
    await create_hub(
        async_session,
        data=HubCreate(name="User Hub", hub_type="ingestion", slug="user-hub"),
        owner_id="user-1",
    )
    await async_session.commit()

    # Admin user-2 has no explicit membership, but gets access when is_platform_admin=True
    admin_hubs = await list_hubs_for_user(async_session, user_id="admin-1", is_platform_admin=True)
    assert len(admin_hubs) >= 1
    assert admin_hubs[0][1] == "owner"


@pytest.mark.asyncio
async def test_delete_hub_if_empty(async_session: AsyncSession):
    """delete_hub_if_empty raises HubNotEmptyError when resources exist."""
    hub = await create_hub(
        async_session,
        data=HubCreate(name="Agent Hub", hub_type="agent", slug="agent-hub"),
        owner_id="user-1",
    )
    await async_session.commit()

    agent = AgentDefinition(
        id="agent-1",
        hub_id=hub.id,
        name="Bound Agent",
        role="router",
        system_prompt="Test prompt",
        model_id="gpt-4o",
        endpoint_slug="bound-agent",
    )
    async_session.add(agent)
    await async_session.commit()

    with pytest.raises(HubNotEmptyError):
        await delete_hub_if_empty(async_session, hub_id=hub.id)

    # Remove agent and verify deletion succeeds
    await async_session.delete(agent)
    await async_session.commit()

    await delete_hub_if_empty(async_session, hub_id=hub.id)
    await async_session.commit()


@pytest.mark.asyncio
async def test_last_owner_protection(async_session: AsyncSession):
    """Cannot remove or demote the last owner of a hub."""
    hub = await create_hub(
        async_session,
        data=HubCreate(name="Protected Hub", hub_type="eval", slug="eval-hub"),
        owner_id="user-1",
    )
    await async_session.commit()

    with pytest.raises(LastOwnerError):
        await remove_member(async_session, hub_id=hub.id, user_id="user-1")

    with pytest.raises(LastOwnerError):
        await upsert_member(async_session, hub_id=hub.id, user_id="user-1", hub_role="contributor")


@pytest.mark.asyncio
async def test_invalid_link_direction(async_session: AsyncSession):
    """create_link raises InvalidLinkDirectionError for disallowed link pairs."""
    ingest_hub = await create_hub(
        async_session,
        data=HubCreate(name="Ingest", hub_type="ingestion", slug="ingest"),
        owner_id="user-1",
    )
    eval_hub = await create_hub(
        async_session,
        data=HubCreate(name="Eval", hub_type="eval", slug="eval"),
        owner_id="user-1",
    )
    await async_session.commit()

    # Nothing may link into an eval hub
    with pytest.raises(InvalidLinkDirectionError):
        await create_link(async_session, source_hub_id=ingest_hub.id, target_hub_id=eval_hub.id)


def test_datastore_binding_read_security():
    """DatastoreBindingRead serialization contains no credentials/secret fields."""
    binding = DatastoreBindingRead(
        id="bind-1",
        hub_id="hub-1",
        name="Primary Qdrant",
        store_type="qdrant",
        connection_uri="http://qdrant:6333",
        has_credentials=True,
        is_default=True,
    )
    dump = binding.model_dump()
    for key in dump.keys():
        assert key not in ("credentials", "credentials_encrypted", "password", "secret", "token")


def test_reserved_slug_validation():
    """HubCreate rejects reserved slugs 'new', 'admin', 'settings'."""
    for reserved in ("new", "admin", "settings", "NEW"):
        with pytest.raises(ValueError):
            HubCreate(name="Reserved Hub", hub_type="agent", slug=reserved)
