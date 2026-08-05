import pytest
from projects.syntraflow.src.datastores.validator import validate_datastore_binding
from common.clients.postgres import get_sessionmaker

@pytest.mark.asyncio
async def test_sentinel_datastore_binding_validation():
    """Verify that sentinel datastore binding IDs (like platform-default:qdrant) fall back cleanly without raising DatastoreValidationError."""
    s = get_sessionmaker()
    async with s() as session:
        # Sentinel ID should return None (representing platform default fallback)
        res = await validate_datastore_binding(session, hub_id="dummy-hub-id", datastore_binding_id="platform-default:qdrant", store_type="qdrant")
        assert res is None
        res_neo4j = await validate_datastore_binding(session, hub_id="dummy-hub-id", datastore_binding_id="platform-default:neo4j", store_type="neo4j")
        assert res_neo4j is None
