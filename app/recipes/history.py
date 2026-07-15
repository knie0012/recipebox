from flask_login import current_user

from app import db
from app.models import RecipeHistory


def record_recipe_history(
    recipe_id,
    action,
    details=None,
):
    """
    Add an audit entry for a recipe-related action.

    This does not commit the transaction. The calling route
    commits the history record together with the main change.
    """

    history = RecipeHistory(
        recipe_id=recipe_id,
        user_id=(
            current_user.id
            if current_user.is_authenticated
            else None
        ),
        action=action,
        details=details,
    )

    db.session.add(history)

    return history
