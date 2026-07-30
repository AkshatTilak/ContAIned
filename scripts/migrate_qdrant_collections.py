"""Migration script to rename legacy Qdrant physical collections to '{hub_slug}__{collection_name}' (S6-04f).

Usage:
    poetry run python scripts/migrate_qdrant_collections.py [--dry-run]
"""

import argparse
import asyncio
import logging

from sqlalchemy import select

from common.clients.postgres import get_async_db
from common.clients.qdrant import VectorClient
from projects.syntraflow.src.database.models import SyntraFlowCollection
from qdrant_client.http import models as qdrant_models

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("migrate_qdrant_collections")


async def migrate_qdrant(dry_run: bool = False) -> None:
    logger.info("Starting Qdrant physical collection migration (dry_run=%s)...", dry_run)
    vector_client = VectorClient()
    client = vector_client.get_client()

    existing_qdrant_collections = {c.name for c in client.get_collections().collections}
    logger.info("Existing Qdrant collections: %s", existing_qdrant_collections)

    async for db in get_async_db():
        stmt = select(SyntraFlowCollection)
        res = await db.execute(stmt)
        collections = res.scalars().all()

        for col in collections:
            legacy_name = col.name
            target_name = col.physical_name

            logger.info("Checking collection ID=%s: legacy_name='%s' -> target_name='%s'", col.id, legacy_name, target_name)

            if legacy_name in existing_qdrant_collections and legacy_name != target_name:
                if target_name not in existing_qdrant_collections:
                    logger.info("Copying Qdrant points from '%s' to '%s'...", legacy_name, target_name)
                    if not dry_run:
                        # Fetch legacy vector config
                        legacy_info = client.get_collection(legacy_name)
                        vector_params = legacy_info.config.params.vectors

                        # Create target collection
                        client.create_collection(collection_name=target_name, vectors_config=vector_params)

                        # Scroll and copy points
                        offset = None
                        copied_count = 0
                        while True:
                            records, offset = client.scroll(
                                collection_name=legacy_name,
                                limit=250,
                                offset=offset,
                                with_payload=True,
                                with_vectors=True,
                            )
                            if not records:
                                break

                            points = []
                            for r in records:
                                payload = dict(r.payload or {})
                                payload["hub_id"] = col.hub_id
                                payload["collection_id"] = col.id
                                points.append(
                                    qdrant_models.PointStruct(
                                        id=r.id,
                                        vector=r.vector,
                                        payload=payload,
                                    )
                                )

                            client.upsert(collection_name=target_name, points=points)
                            copied_count += len(points)

                        logger.info("Successfully copied %d points into '%s'. Verifying counts...", copied_count, target_name)
                        target_info = client.get_collection(target_name)
                        if target_info.points_count >= legacy_info.points_count:
                            logger.info("Count parity verified (%d vs %d). Deleting legacy collection '%s'...", target_info.points_count, legacy_info.points_count, legacy_name)
                            client.delete_collection(legacy_name)
                        else:
                            logger.error("Count mismatch! Legacy: %d, Target: %d. Aborting delete.", legacy_info.points_count, target_info.points_count)
                else:
                    logger.info("Target collection '%s' already exists.", target_name)
            else:
                logger.info("Skipping '%s' (no legacy Qdrant collection or already migrated).", legacy_name)

        break

    logger.info("Qdrant physical migration completed.")


def main():
    parser = argparse.ArgumentParser(description="Migrate legacy Qdrant collections to hub-scoped physical names.")
    parser.add_argument("--dry-run", action="store_true", help="Run without performing mutating writes")
    args = parser.parse_args()

    asyncio.run(migrate_qdrant(dry_run=args.dry_run))


if __name__ == "__main__":
    main()
