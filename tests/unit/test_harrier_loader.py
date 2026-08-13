
import pytest
pytestmark = pytest.mark.unit
import pytest
import asyncio
from inference.core.vram_manager import VRAMManager
from inference.models.harrier import load_harrier

@pytest.mark.asyncio
async def test_harrier_loader_registration():
    """Verify that Harrier 0.6B model loader loads successfully."""
    vram = VRAMManager.get_instance(budget_mb=8000)
    vram.register_loader("harrier-0.6b", load_harrier, 1000)
    
    # Load model via ensure_loaded
    wrapper = await vram.ensure_loaded("harrier-0.6b")
    assert wrapper is not None
    
    # Generate embedding
    res = await wrapper.embed_texts(["hello world"])
    assert len(res) == 1
    assert len(res[0]) == 768
