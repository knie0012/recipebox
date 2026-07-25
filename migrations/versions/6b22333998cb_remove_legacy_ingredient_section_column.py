"""remove legacy ingredient section column

Revision ID: 6b22333998cb
Revises: f8e647c7693e
Create Date: 2026-07-24 15:27:46.766953

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '6b22333998cb'
down_revision = 'f8e647c7693e'
branch_labels = None
depends_on = None

def upgrade():
    op.drop_column(
        "recipe_ingredients",
        "section",
    )


def downgrade():
    op.add_column(
        "recipe_ingredients",
        sa.Column(
            "section",
            sa.String(length=100),
            nullable=True,
        ),
    )