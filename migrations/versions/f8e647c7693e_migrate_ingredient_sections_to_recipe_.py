"""migrate ingredient sections to recipe sections

Revision ID: f8e647c7693e
Revises: 1d59308add42
Create Date: 2026-07-24 13:47:58.913260

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f8e647c7693e'
down_revision = '1d59308add42'
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()

    recipes = connection.execute(
        sa.text(
            """
            SELECT DISTINCT recipe_id
            FROM recipe_ingredients
            WHERE section IS NOT NULL
              AND TRIM(section) <> ''
            ORDER BY recipe_id
            """
        )
    ).fetchall()

    for recipe_row in recipes:
        recipe_id = recipe_row.recipe_id

        section_rows = connection.execute(
            sa.text(
                """
                SELECT
                    TRIM(section) AS section_name,
                    MIN(position) AS first_position
                FROM recipe_ingredients
                WHERE recipe_id = :recipe_id
                  AND section IS NOT NULL
                  AND TRIM(section) <> ''
                GROUP BY TRIM(section)
                ORDER BY first_position, section_name
                """
            ),
            {
                "recipe_id": recipe_id,
            },
        ).fetchall()

        section_position = 1

        for section_row in section_rows:
            section_name = section_row.section_name

            existing_section_id = connection.execute(
                sa.text(
                    """
                    SELECT id
                    FROM recipe_sections
                    WHERE recipe_id = :recipe_id
                      AND name = :section_name
                    LIMIT 1
                    """
                ),
                {
                    "recipe_id": recipe_id,
                    "section_name": section_name,
                },
            ).scalar()

            if existing_section_id is None:
                result = connection.execute(
                    sa.text(
                        """
                        INSERT INTO recipe_sections (
                            recipe_id,
                            name,
                            position
                        )
                        VALUES (
                            :recipe_id,
                            :section_name,
                            :position
                        )
                        """
                    ),
                    {
                        "recipe_id": recipe_id,
                        "section_name": section_name,
                        "position": section_position,
                    },
                )

                section_id = result.lastrowid
            else:
                section_id = existing_section_id

                connection.execute(
                    sa.text(
                        """
                        UPDATE recipe_sections
                        SET position = :position
                        WHERE id = :section_id
                        """
                    ),
                    {
                        "position": section_position,
                        "section_id": section_id,
                    },
                )

            connection.execute(
                sa.text(
                    """
                    UPDATE recipe_ingredients
                    SET section_id = :section_id
                    WHERE recipe_id = :recipe_id
                      AND TRIM(section) = :section_name
                    """
                ),
                {
                    "section_id": section_id,
                    "recipe_id": recipe_id,
                    "section_name": section_name,
                },
            )

            section_position += 1

    ingredient_groups = connection.execute(
        sa.text(
            """
            SELECT DISTINCT
                recipe_id,
                section_id
            FROM recipe_ingredients
            ORDER BY recipe_id, section_id
            """
        )
    ).fetchall()

    for group_row in ingredient_groups:
        recipe_id = group_row.recipe_id
        section_id = group_row.section_id

        if section_id is None:
            ingredients = connection.execute(
                sa.text(
                    """
                    SELECT id
                    FROM recipe_ingredients
                    WHERE recipe_id = :recipe_id
                      AND section_id IS NULL
                    ORDER BY position, id
                    """
                ),
                {
                    "recipe_id": recipe_id,
                },
            ).fetchall()
        else:
            ingredients = connection.execute(
                sa.text(
                    """
                    SELECT id
                    FROM recipe_ingredients
                    WHERE recipe_id = :recipe_id
                      AND section_id = :section_id
                    ORDER BY position, id
                    """
                ),
                {
                    "recipe_id": recipe_id,
                    "section_id": section_id,
                },
            ).fetchall()

        for new_position, ingredient_row in enumerate(
            ingredients,
            start=1,
        ):
            connection.execute(
                sa.text(
                    """
                    UPDATE recipe_ingredients
                    SET position = :position
                    WHERE id = :ingredient_id
                    """
                ),
                {
                    "position": new_position,
                    "ingredient_id": ingredient_row.id,
                },
            )


def downgrade():
    connection = op.get_bind()

    connection.execute(
        sa.text(
            """
            UPDATE recipe_ingredients ri
            JOIN recipe_sections rs
              ON rs.id = ri.section_id
            SET ri.section = rs.name
            """
        )
    )

    connection.execute(
        sa.text(
            """
            UPDATE recipe_ingredients
            SET section_id = NULL
            """
        )
    )

    connection.execute(
        sa.text(
            """
            DELETE FROM recipe_sections
            """
        )
    )