from flask import render_template
from sqlalchemy.orm import selectinload

from app.main import main
from app.models import Recipes


@main.route("/recipebox")
def index():
    recipes = (
        Recipes.query
        .options(
            selectinload(Recipes.recipe_images),
            selectinload(Recipes.types),
            selectinload(Recipes.tags),
        )
        .order_by(Recipes.title)
        .all()
    )

    return render_template(
        "index.html",
        recipes=recipes,
    )