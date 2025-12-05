"""Initial migration

Revision ID: 001
Create Date: 2024-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        'urls',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('original_url', sa.String(length=2048), nullable=False),
        sa.Column('url_hash', sa.String(length=64), nullable=False),  # Для SHA-256
        sa.Column('short_code', sa.String(length=6), nullable=False),
        sa.Column('created_at', sa.String(length=30), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('short_code'),
        sa.UniqueConstraint('url_hash')  # Уникальный индекс по хешу
    )
    op.create_index('ix_urls_original_url', 'urls', ['original_url'])
    op.create_index('ix_urls_short_code', 'urls', ['short_code'])
    op.create_index('ix_urls_url_hash', 'urls', ['url_hash'])

def downgrade():
    op.drop_index('ix_urls_url_hash', 'urls')
    op.drop_index('ix_urls_short_code', 'urls')
    op.drop_index('ix_urls_original_url', 'urls')
    op.drop_table('urls')
