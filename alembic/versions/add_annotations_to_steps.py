"""add annotations to guide steps

Revision ID: add_annotations
Revises: 
Create Date: 2026-01-20

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = 'add_annotations'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Добавляем поле annotations в guide_steps
    op.add_column('guide_steps', 
        sa.Column('annotations', postgresql.JSON(astext_type=sa.Text()), nullable=True)
    )


def downgrade():
    op.drop_column('guide_steps', 'annotations')
