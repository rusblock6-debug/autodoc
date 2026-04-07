"""make screenshot_path nullable

Revision ID: make_screenshot_path_nullable
Revises: add_annotations_to_steps
Create Date: 2026-04-07 09:50:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'make_screenshot_path_nullable'
down_revision = 'add_annotations_to_steps'
branch_labels = None
depends_on = None


def upgrade():
    # Делаем screenshot_path nullable
    op.alter_column('guide_steps', 'screenshot_path',
                    existing_type=sa.String(1000),
                    nullable=True)


def downgrade():
    # Возвращаем обратно
    op.alter_column('guide_steps', 'screenshot_path',
                    existing_type=sa.String(1000),
                    nullable=False)
