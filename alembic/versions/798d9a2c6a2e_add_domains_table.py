"""add domains table

Revision ID: 798d9a2c6a2e
Revises: 001
Create Date: 2024-01-09 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '798d9a2c6a2e'
down_revision = '001'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        'domains',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('domain', sa.String(255), nullable=False),
        sa.Column('redirect_url', sa.String(2048), nullable=False),
        sa.Column('created_at', sa.String(30), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('domain')
    )

def downgrade():
    op.drop_table('domains')
