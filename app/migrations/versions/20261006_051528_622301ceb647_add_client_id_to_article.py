"""add_client_id_to_article

Revision ID: 622301ceb647
Revises: 865c863df6b0
Create Date: 2026-10-06 05:15:28.301117+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = '622301ceb647'
down_revision: Union[str, None] = '865c863df6b0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('article', sa.Column('client_id', sa.Uuid(), nullable=True))
    op.create_index(op.f('ix_article_client_id'), 'article', ['client_id'], unique=False)
    op.create_foreign_key('fk_article_client_profile_client_id', 'article', 'client_profile', ['client_id'], ['id'])


def downgrade() -> None:
    op.drop_constraint('fk_article_client_profile_client_id', 'article', type_='foreignkey')
    op.drop_index(op.f('ix_article_client_id'), table_name='article')
    op.drop_column('article', 'client_id')
