import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError

from common.models.database import Base, Hub, HubMember, HubLink, User
from common.models.hub_enums import (
    HUB_TYPES,
    HUB_ROLES,
    HUB_TYPE_INGESTION,
    HUB_TYPE_AGENT,
    HUB_TYPE_WORKFLOW,
    HUB_TYPE_EVAL,
    HUB_ROLE_OWNER,
    HUB_ROLE_MAINTAINER,
    HUB_ROLE_CONTRIBUTOR,
    HUB_ROLE_VIEWER,
    LINK_ACCESS_READ,
    LINK_ACCESS_USE,
    hub_role_rank,
    hub_role_satisfies,
    link_access_satisfies,
    is_link_direction_allowed,
)


@pytest.fixture
def db_session():
    """In-memory SQLite database session fixture."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def test_hub_role_rank_and_satisfies():
    """Test hub_role_rank and hub_role_satisfies for all combinations."""
    roles = [HUB_ROLE_OWNER, HUB_ROLE_MAINTAINER, HUB_ROLE_CONTRIBUTOR, HUB_ROLE_VIEWER]
    
    assert hub_role_rank(None) == 0
    assert hub_role_rank("invalid") == 0
    assert hub_role_rank(HUB_ROLE_OWNER) == 4
    assert hub_role_rank(HUB_ROLE_MAINTAINER) == 3
    assert hub_role_rank(HUB_ROLE_CONTRIBUTOR) == 2
    assert hub_role_rank(HUB_ROLE_VIEWER) == 1

    # Test all 16 role pairs
    for actual in roles:
        for required in roles:
            expected = hub_role_rank(actual) >= hub_role_rank(required)
            assert hub_role_satisfies(actual, required) == expected

    assert hub_role_satisfies(None, HUB_ROLE_VIEWER) is False


def test_link_access_satisfies():
    """Test link_access_satisfies logic."""
    assert link_access_satisfies(LINK_ACCESS_USE, LINK_ACCESS_READ) is True
    assert link_access_satisfies(LINK_ACCESS_READ, LINK_ACCESS_USE) is False
    assert link_access_satisfies(LINK_ACCESS_READ, LINK_ACCESS_READ) is True
    assert link_access_satisfies(None, LINK_ACCESS_READ) is False


def test_is_link_direction_allowed_matrix():
    """Test all 16 combinations of link directions (5 allowed, 11 rejected)."""
    allowed_count = 0
    for src in HUB_TYPES:
        for tgt in HUB_TYPES:
            allowed = is_link_direction_allowed(src, tgt)
            if allowed:
                allowed_count += 1
                assert (src, tgt) in {
                    (HUB_TYPE_AGENT, HUB_TYPE_INGESTION),
                    (HUB_TYPE_WORKFLOW, HUB_TYPE_AGENT),
                    (HUB_TYPE_WORKFLOW, HUB_TYPE_INGESTION),
                    (HUB_TYPE_EVAL, HUB_TYPE_WORKFLOW),
                    (HUB_TYPE_EVAL, HUB_TYPE_AGENT),
                }
            else:
                # Nothing links INTO eval hubs
                if tgt == HUB_TYPE_EVAL:
                    assert allowed is False

    assert allowed_count == 5


def test_hub_unique_constraint(db_session):
    """Test (hub_type, slug) uniqueness and distinct types with same slug."""
    # Create test user
    user = User(email="owner@example.com", provider="local", provider_id="p1", display_name="Owner User")
    db_session.add(user)
    db_session.commit()

    hub1 = Hub(slug="docs", name="Docs Hub", hub_type=HUB_TYPE_INGESTION, owner_id=user.id)
    db_session.add(hub1)
    db_session.commit()

    # Same slug under different hub_type should succeed
    hub2 = Hub(slug="docs", name="Docs Agent Hub", hub_type=HUB_TYPE_AGENT, owner_id=user.id)
    db_session.add(hub2)
    db_session.commit()
    assert hub2.id is not None

    # Same slug under same hub_type should fail
    hub_dup = Hub(slug="docs", name="Duplicate Ingestion Hub", hub_type=HUB_TYPE_INGESTION, owner_id=user.id)
    db_session.add(hub_dup)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_hub_member_unique_constraint(db_session):
    """Test duplicate (hub_id, user_id) raises IntegrityError."""
    user = User(email="user@example.com", provider="local", provider_id="p2", display_name="Test User")
    db_session.add(user)
    db_session.commit()

    hub = Hub(slug="default-hub", name="Default Hub", hub_type=HUB_TYPE_INGESTION, owner_id=user.id)
    db_session.add(hub)
    db_session.commit()

    member1 = HubMember(hub_id=hub.id, user_id=user.id, hub_role=HUB_ROLE_OWNER)
    db_session.add(member1)
    db_session.commit()

    member_dup = HubMember(hub_id=hub.id, user_id=user.id, hub_role=HUB_ROLE_VIEWER)
    db_session.add(member_dup)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_hub_cascade_delete(db_session):
    """Test deleting a Hub cascades to hub_members and hub_links."""
    user1 = User(email="user1@example.com", provider="local", provider_id="p3", display_name="User 1")
    user2 = User(email="user2@example.com", provider="local", provider_id="p4", display_name="User 2")
    db_session.add_all([user1, user2])
    db_session.commit()

    hub_ingestion = Hub(slug="ingest", name="Ingestion Hub", hub_type=HUB_TYPE_INGESTION, owner_id=user1.id)
    hub_agent = Hub(slug="agent", name="Agent Hub", hub_type=HUB_TYPE_AGENT, owner_id=user1.id)
    db_session.add_all([hub_ingestion, hub_agent])
    db_session.commit()

    member = HubMember(hub_id=hub_agent.id, user_id=user2.id, hub_role=HUB_ROLE_CONTRIBUTOR)
    link = HubLink(source_hub_id=hub_agent.id, target_hub_id=hub_ingestion.id, access_level=LINK_ACCESS_READ)
    db_session.add_all([member, link])
    db_session.commit()

    assert db_session.query(HubMember).count() == 1
    assert db_session.query(HubLink).count() == 1

    # Delete source hub
    db_session.delete(hub_agent)
    db_session.commit()

    assert db_session.query(HubMember).count() == 0
    assert db_session.query(HubLink).count() == 0


def test_model_validations(db_session):
    """Test model field validations (@validates hooks)."""
    user = User(email="val@example.com", provider="local", provider_id="p5", display_name="Val User")
    db_session.add(user)
    db_session.commit()

    # Invalid hub_type
    with pytest.raises(ValueError, match="Invalid hub_type"):
        Hub(slug="test", name="Test", hub_type="invalid_type", owner_id=user.id)

    hub = Hub(slug="test", name="Test", hub_type=HUB_TYPE_INGESTION, owner_id=user.id)
    db_session.add(hub)
    db_session.commit()

    # Immutable hub_type
    with pytest.raises(ValueError, match="hub_type is immutable"):
        hub.hub_type = HUB_TYPE_AGENT

    # Invalid hub_role
    with pytest.raises(ValueError, match="Invalid hub_role"):
        HubMember(hub_id=hub.id, user_id=user.id, hub_role="superadmin")

    # Invalid access_level
    with pytest.raises(ValueError, match="Invalid access_level"):
        HubLink(source_hub_id=hub.id, target_hub_id="other_hub_id", access_level="admin")

    # Self-link rejection
    with pytest.raises(ValueError, match="Self-linking is not allowed"):
        link = HubLink(source_hub_id=hub.id, access_level=LINK_ACCESS_READ)
        link.target_hub_id = hub.id
