from flask import Blueprint


recipes = Blueprint(
    "recipes",
    __name__,
    template_folder="../templates/recipes",
)


# Import route modules only after the blueprint has been created.
import app.recipes.routes.ingredients
import app.recipes.routes.images
import app.recipes.routes.recipes
import app.recipes.routes.steps
