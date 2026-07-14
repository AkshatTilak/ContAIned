"""HuggingFace model downloader with structured JSON progress logging.

Coordinates model weight checks and downloading before VRAM loading.
"""

import os
import sys
import json
import logging
from typing import Optional
import tqdm
import tqdm.auto

from common.config.settings import settings

logger = logging.getLogger("inference.core.downloader")


class JSONProgressTqdm(tqdm.tqdm):
    """Subclass of tqdm that outputs structured JSON progress instead of stderr text."""

    def __init__(self, *args, **kwargs):
        # Disable stderr writing to avoid terminal progress bar spamming
        kwargs["disable"] = True
        super().__init__(*args, **kwargs)
        self._last_pct = 0.0
        self._desc = kwargs.get("desc", "Downloading")

    def update(self, n=1):
        super().update(n)
        if self.total:
            pct = round((self.n / self.total) * 100, 1)
            # Emit logs every 10% increment or at completion to reduce output verbosity
            if pct - self._last_pct >= 10.0 or pct >= 100.0 or self.n == self.total:
                self._last_pct = pct
                log_payload = {
                    "status": "downloading",
                    "description": self._desc,
                    "progress_pct": pct,
                    "downloaded_bytes": self.n,
                    "total_bytes": self.total,
                }
                # Print to stdout and flush so that logs are captured immediately
                sys.stdout.write(json.dumps(log_payload) + "\n")
                sys.stdout.flush()


def download_model_from_hub(model_id: str, quantization: Optional[str] = None) -> str:
    """Ensure a HuggingFace model is downloaded and cached.

    Honors HF_HUB_OFFLINE, HF_TOKEN, HF_HOME, and custom MODEL_CACHE_DIR.
    Outputs progress logs as JSON lines.

    Args:
        model_id: HuggingFace repository ID (e.g. 'THUDM/GLM-OCR') or local path.
        quantization: Optional quantization level specifier.

    Returns:
        Path to the downloaded model repository directory.
    """
    # 1. Check if model_id is already a valid local directory
    if os.path.isdir(model_id):
        logger.info("Model ID '%s' is already a valid local path. Skipping download.", model_id)
        return model_id

    # 2. Check offline mode
    is_offline = os.environ.get("HF_HUB_OFFLINE") == "1"
    
    # 3. Setup cache directory priority: env var > settings > default cache
    cache_dir = os.environ.get("MODEL_CACHE_DIR")
    if not cache_dir:
        cache_dir = settings.HF_HOME
    cache_dir = os.path.expanduser(cache_dir)

    logger.info("Checking model weights for '%s' in cache directory: %s", model_id, cache_dir)

    # 4. If offline, verify weights are already cached, otherwise fail
    if is_offline:
        # Check standard cache directory structure for HF repository
        # HF caches in <cache_dir>/models--%s
        repo_folder = "models--" + model_id.replace("/", "--")
        repo_cache_path = os.path.join(cache_dir, repo_folder)
        if os.path.exists(repo_cache_path):
            logger.info("Offline mode: Found cached model folder at %s", repo_cache_path)
            return repo_cache_path
        else:
            raise RuntimeError(
                f"Offline mode (HF_HUB_OFFLINE=1) is active but model '{model_id}' "
                f"is not cached locally in {cache_dir}."
            )

    # 5. Build download arguments
    token = os.environ.get("HF_TOKEN")
    
    # Fast transfer setting
    if os.environ.get("HF_HUB_ENABLE_HF_TRANSFER") == "1":
        logger.info("HF transfer acceleration (HF_HUB_ENABLE_HF_TRANSFER) enabled.")

    # 6. Apply progress bar patch and execute download
    orig_tqdm = tqdm.tqdm
    orig_auto_tqdm = tqdm.auto.tqdm

    try:
        tqdm.tqdm = JSONProgressTqdm
        tqdm.auto.tqdm = JSONProgressTqdm

        from huggingface_hub import snapshot_download

        logger.info("Starting HuggingFace download for model '%s'...", model_id)
        
        # Execute download with snapshot_download
        local_path = snapshot_download(
            repo_id=model_id,
            cache_dir=cache_dir,
            token=token,
            ignore_patterns=["*.msgpack", "*.h5", "*.ot"],  # ignore unused framework binaries
        )
        
        logger.info("Model '%s' successfully cached at: %s", model_id, local_path)
        return local_path

    except Exception as e:
        logger.error("Failed to download model '%s': %s", model_id, e)
        raise e

    finally:
        # Restore original progress bars
        tqdm.tqdm = orig_tqdm
        tqdm.auto.tqdm = orig_auto_tqdm
