"""Unit tests for HubResolver service (S6-02c)."""

import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from common.models.database import (
    AgentDefinition,
    Base,
    DatastoreBinding,
    Hub,
    HubLink,
    HubMember,
    User,
    WorkflowDefinition,
)
from common.services.hub_repository import create_link, create_hub
from common.services.hub_resolver import (
    HUB_LINK_INSUFFICIENT,
    HUB_LINK_REQUIRED,
    HUB_LINK_REVOKED,
    HubLinkError,
    assert_link,
    list_linked_hub_ids,
    resolve_linked,
    resolve_linked_many,
    validate_link_creation,
)


@pytest_asyncio.fixture
async def async_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session_factory = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    async with async_session_factory() as session:
        # Seed users
        u1 = User(id="user-owner-1", email="owner1@example.com", provider="local", provider_id="u1", platform_role="member")
        u2 = User(id="user-owner-2", email="owner2@example.com", provider="local", provider_id="u2", platform_role="member")
        admin = User(id="user-admin", email="admin@example.com", provider="local", provider_id="u3", platform_role="admin")
        session.add_all([u1, u2, admin])
        await session.commit()

        # Seed hubs
        # Ingestion Hub I1
        h_ingest = Hub(id="hub-i1", slug="kb-ingest", name="Ingest Hub", hub_type="ingestion", owner_id="user-owner-1")
        # Agent Hub A1
        h_agent = Hub(id="hub-a1", slug="agent-hub", name="Agent Hub", hub_type="agent", owner_id="user-owner-1")
        # Workflow Hub W1
        h_wf = Hub(id="hub-w1", slug="wf-hub", name="Workflow Hub", hub_type="workflow", owner_id="user-owner-2")
        session.add_all([h_ingest, h_agent, h_wf])
        await session.commit()

        # Seed memberships
        m1 = HubMember(hub_id="hub-i1", user_id="user-owner-1", hub_role="owner")
        m2 = HubMember(hub_id="hub-a1", user_id="user-owner-1", hub_role="owner")
        m3 = HubMember(hub_id="hub-w1", user_id="user-owner-2", hub_role="owner")
        session.add_all([m1, m2, m3])
        await session.commit()

        # Seed resources
        ds1 = DatastoreBinding(id="binding-1", hub_id="hub-i1", name="qdrant-main", store_type="qdrant", connection_uri="http://qdrant:6333")
        ag1 = AgentDefinition(id="agent-1", hub_id="hub-a1", name="Support Agent", role="assistant", system_prompt="Hello", model_id="gpt-4o")
        wf1 = WorkflowDefinition(id="wf-1", hub_id="hub-w1", name="RAG Pipeline", graph_json={})
        session.add_all([ds1, ag1, wf1])
        await session.commit()

        yield session

    await engine.dispose()


@pytest.mark.asyncio
async def test_intra_hub_resolution_fast_path(async_session: AsyncSession):
    """Resource in same hub resolves immediately without requiring hub link."""
    res = await resolve_linked(
        async_session,
        source_hub_id="hub-a1",
        target_resource_type="agent",
        target_resource_id="agent-1",
    )
    assert res.id == "agent-1"
    assert res.name == "Support Agent"


@pytest.mark.asyncio
async def test_cross_hub_valid_link_and_revocation(async_session: AsyncSession):
    """Cross-hub reference resolves with valid link, fails with HUB_LINK_REVOKED after link deletion."""
    # Create Agent Hub -> Ingestion Hub link with access_level="read"
    link = HubLink(id="link-a1-i1", source_hub_id="hub-a1", target_hub_id="hub-i1", access_level="read", created_by="user-owner-1")
    async_session.add(link)
    await async_session.commit()

    # Resolve collection in hub-i1 from hub-a1
    ds = await resolve_linked(
        async_session,
        source_hub_id="hub-a1",
        target_resource_type="collection",
        target_resource_id="binding-1",
        required_access="read",
    )
    assert ds.id == "binding-1"

    # Delete link (revoke)
    await async_session.delete(link)
    await async_session.commit()

    with pytest.raises(HubLinkError) as exc_info:
        await resolve_linked(
            async_session,
            source_hub_id="hub-a1",
            target_resource_type="collection",
            target_resource_id="binding-1",
            required_access="read",
        )
    assert exc_info.value.code == HUB_LINK_REVOKED


@pytest.mark.asyncio
async def test_insufficient_link_access_level(async_session: AsyncSession):
    """Link with access_level 'read' raises HUB_LINK_INSUFFICIENT when 'use' is required."""
    link = HubLink(id="link-w1-a1", source_hub_id="hub-w1", target_hub_id="hub-a1", access_level="read", created_by="user-owner-2")
    async_session.add(link)
    await async_session.commit()

    with pytest.raises(HubLinkError) as exc_info:
        await resolve_linked(
            async_session,
            source_hub_id="hub-w1",
            target_resource_type="agent",
            target_resource_id="agent-1",
            required_access="use",
        )
    assert exc_info.value.code == HUB_LINK_INSUFFICIENT


@pytest.mark.asyncio
async def test_disallowed_link_direction(async_session: AsyncSession):
    """Attempting cross-hub resolution in disallowed direction (e.g. Ingestion -> Agent) fails."""
    # Insert link in invalid direction
    link = HubLink(id="link-invalid", source_hub_id="hub-i1", target_hub_id="hub-a1", access_level="read", created_by="user-owner-1")
    async_session.add(link)
    await async_session.commit()

    with pytest.raises(HubLinkError) as exc_info:
        await resolve_linked(
            async_session,
            source_hub_id="hub-i1",
            target_resource_type="agent",
            target_resource_id="agent-1",
            required_access="read",
        )
    assert exc_info.value.code == HUB_LINK_REQUIRED


@pytest.mark.asyncio
async def test_non_transitivity_rule(async_session: AsyncSession):
    """W1 -> A1 and A1 -> I1 links present does NOT grant W1 access to I1 (non-transitive)."""
    l1 = HubLink(id="l-w1-a1", source_hub_id="hub-w1", target_hub_id="hub-a1", access_level="use", created_by="user-owner-2")
    l2 = HubLink(id="l-a1-i1", source_hub_id="hub-a1", target_hub_id="hub-i1", access_level="read", created_by="user-owner-1")
    async_session.add_all([l1, l2])
    await async_session.commit()

    # W1 attempting to resolve collection in I1 fails because no W1 -> I1 link exists
    with pytest.raises(HubLinkError) as exc_info:
        await resolve_linked(
            async_session,
            source_hub_id="hub-w1",
            target_resource_type="collection",
            target_resource_id="binding-1",
            required_access="read",
        )
    assert exc_info.value.code == HUB_LINK_REVOKED or exc_info.value.code == HUB_LINK_REQUIRED


@pytest.mark.asyncio
async def test_validate_link_creation(async_session: AsyncSession):
    """Test validate_link_creation self-link rejection and dual-hub role enforcement."""
    # Self-link rejection (422)
    with pytest.raises(HTTPException) as exc1:
        await validate_link_creation(
            async_session,
            source_hub_id="hub-a1",
            target_hub_id="hub-a1",
            access_level="read",
            actor_user_id="user-owner-1",
            is_platform_admin=False,
        )
    assert exc1.value.status_code == 422

    # User-owner-2 is owner on hub-w1, but has NO membership on hub-i1 -> 403
    with pytest.raises(HTTPException) as exc2:
        await validate_link_creation(
            async_session,
            source_hub_id="hub-w1",
            target_hub_id="hub-i1",
            access_level="read",
            actor_user_id="user-owner-2",
            is_platform_admin=False,
        )
    assert exc2.value.status_code == 403

    # Platform admin bypass passes without target membership
    await validate_link_creation(
        async_session,
        source_hub_id="hub-w1",
        target_hub_id="hub-i1",
        access_level="read",
        actor_user_id="user-admin",
        is_platform_admin=True,
    )
