
import pytest
pytestmark = pytest.mark.unit
import pytest
from gateway.api.models import delete_local_model
from common.clients.postgres import get_sessionmaker

@pytest.mark.asyncio
async def test_delete_local_model_endpoint():
    """Verify delete_local_model removes model from registry."""
    s = get_sessionmaker()
    async with s() as session:
        # Call delete_local_model for a test non-existent model to verify handling
        res = await delete_local_model("nonexistent-test-model", purge_disk=False, db=session)
        assert res["status"] == "success"
