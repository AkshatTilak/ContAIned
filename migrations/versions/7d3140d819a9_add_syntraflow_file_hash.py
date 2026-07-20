"""add_syntraflow_file_hash

Revision ID: 7d3140d819a9
Revises: d1ea753fbd9d
Create Date: 2026-07-20 19:03:21.808389

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
"""add_syntraflow_file_hash

Revision ID: 7d3140d819a9
Revises: d1ea753fbd9d
Create Date: 2026-07-20 19:03:21.808389

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7d3140d819a9'
down_revision: Union[str, Sequence[str], None] = 'd1ea753fbd9d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("DROP TABLE IF EXISTS syntraflow_video_segments CASCADE")
    op.execute("DROP TABLE IF EXISTS syntraflow_chunks CASCADE")
    op.execute("DROP TABLE IF EXISTS syntraflow_jobs CASCADE")
    op.execute("DROP TABLE IF EXISTS syntraflow_documents CASCADE")

    op.execute("""
        CREATE TABLE syntraflow_documents (
            id UUID PRIMARY KEY,
            filename VARCHAR(255) NOT NULL,
            file_hash VARCHAR(64),
            content TEXT,
            layout_json TEXT,
            created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (now() at time zone 'utc')
        )
    """)
    op.execute("CREATE INDEX ix_syntraflow_documents_file_hash ON syntraflow_documents (file_hash)")

    op.execute("""
        CREATE TABLE syntraflow_jobs (
            id UUID PRIMARY KEY,
            document_id UUID REFERENCES syntraflow_documents(id) ON DELETE SET NULL,
            status VARCHAR(32) NOT NULL DEFAULT 'queued',
            progress FLOAT DEFAULT 0.0,
            error_msg VARCHAR(512),
            created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (now() at time zone 'utc'),
            updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (now() at time zone 'utc')
        )
    """)

    op.execute("""
        CREATE TABLE syntraflow_chunks (
            id UUID PRIMARY KEY,
            document_id UUID REFERENCES syntraflow_documents(id) ON DELETE CASCADE,
            chunk_index FLOAT NOT NULL,
            text TEXT NOT NULL,
            metadata_json TEXT,
            created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (now() at time zone 'utc')
        )
    """)

    op.execute("""
        CREATE TABLE syntraflow_video_segments (
            id UUID PRIMARY KEY,
            document_id UUID REFERENCES syntraflow_documents(id) ON DELETE CASCADE,
            video_name VARCHAR(255) NOT NULL,
            start_time FLOAT NOT NULL,
            end_time FLOAT NOT NULL,
            transcript TEXT NOT NULL,
            visual_summary TEXT,
            emotion_tags VARCHAR(128),
            audio_events VARCHAR(255),
            created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (now() at time zone 'utc')
        )
    """)
    op.execute("CREATE INDEX ix_syntraflow_video_segments_document_id ON syntraflow_video_segments (document_id)")


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP TABLE IF EXISTS syntraflow_video_segments CASCADE")
    op.execute("DROP TABLE IF EXISTS syntraflow_chunks CASCADE")
    op.execute("DROP TABLE IF EXISTS syntraflow_jobs CASCADE")
    op.execute("DROP TABLE IF EXISTS syntraflow_documents CASCADE")

