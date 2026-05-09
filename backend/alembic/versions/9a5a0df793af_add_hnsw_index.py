"""add_hnsw_index

Revision ID: 9a5a0df793af
Revises: 32c538358a05
Create Date: 2026-05-07 11:59:55.814513

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9a5a0df793af'
down_revision: Union[str, Sequence[str], None] = '32c538358a05'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("""
        CREATE INDEX idx_messages_embedding ON chat_messages 
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64);
    """)


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP INDEX IF EXISTS idx_messages_embedding;")
