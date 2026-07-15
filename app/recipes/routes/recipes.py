from flask import (
    flash,
    redirect,
    render_template,
    request,
    url_for,
)

from app import db
from app.models import Recipes
from app.recipes import recipes
from app.recipes.services import (
    parse_optional_nonnegative_integer, UNIT_LABELS
)

from flask_login import login_required

from flask_login import current_user
from app.recipes.history import record_recipe_history


@recipes.route("/recipebox/<int:id>")
def detail(id):
    recipe = Recipes.query.get_or_404(id)

    return render_template(
        "recipes/detail.html",
        recipe=recipe,
        unit_labels=UNIT_LABELS,
    )


@recipes.route(
    "/recipebox/new",
    methods=["GET", "POST"],
)
@login_required
def new_recipe():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get(
            "description",
            "",
        ).strip()

        if not title:
            flash("A recipe title is required.", "error")

            return render_template(
                "recipes/recipe_form.html",
                recipe=None,
            )

        try:
            prep_time = parse_optional_nonnegative_integer(
                request.form.get("prep_time"),
                "Prep time",
            )

            cook_time = parse_optional_nonnegative_integer(
                request.form.get("cook_time"),
                "Cook time",
            )

            servings = parse_optional_nonnegative_integer(
                request.form.get("servings"),
                "Servings",
            )

        except ValueError as error:
            flash(str(error), "error")

            return render_template(
                "recipes/recipe_form.html",
                recipe=None,
            )

        recipe = Recipes(
            title=title,
            description=description or None,
            prep_time=prep_time,
            cook_time=cook_time,
            servings=servings,
            created_by=current_user.id,
         )

        db.session.add(recipe)

        # Assign the recipe its database ID without committing.
        db.session.flush()

        record_recipe_history(
            recipe_id=recipe.id,
            action="recipe_created",
            details=f'Created recipe "{recipe.title}".',
        )

        # Commit both the recipe and its history entry together.
        db.session.commit()

        flash(
            f'"{recipe.title}" was created.',
            "success",
        )

        return redirect(
            url_for(
                "recipes.detail",
                id=recipe.id,
            )
        )

    return render_template(
        "recipes/recipe_form.html",
        recipe=None,
    )


@recipes.route(
    "/recipebox/<int:id>/edit",
    methods=["GET", "POST"],
)
@login_required
def edit_recipe(id):
    recipe = Recipes.query.get_or_404(id)

    if request.method == "POST":
        title = request.form.get(
            "title",
            "",
        ).strip()

        description = request.form.get(
            "description",
            "",
        ).strip()

        if not title:
            flash(
                "A recipe title is required.",
                "error",
            )

            return render_template(
                "recipes/recipe_form.html",
                recipe=recipe,
            )

        try:
            new_prep_time = (
                parse_optional_nonnegative_integer(
                    request.form.get("prep_time"),
                    "Prep time",
                )
            )

            new_cook_time = (
                parse_optional_nonnegative_integer(
                    request.form.get("cook_time"),
                    "Cook time",
                )
            )

            new_servings = (
                parse_optional_nonnegative_integer(
                    request.form.get("servings"),
                    "Servings",
                )
            )

        except ValueError as error:
            flash(
                str(error),
                "error",
            )

            return render_template(
                "recipes/recipe_form.html",
                recipe=recipe,
            )

        new_description = description or None

        changes = []

        if recipe.title != title:
            changes.append(
                f'Title changed from '
                f'"{recipe.title}" to "{title}"'
            )

        if recipe.description != new_description:
            changes.append(
                "Description updated"
            )

        if recipe.prep_time != new_prep_time:
            old_value = (
                recipe.prep_time
                if recipe.prep_time is not None
                else "not set"
            )

            new_value = (
                new_prep_time
                if new_prep_time is not None
                else "not set"
            )

            changes.append(
                f"Prep time changed from "
                f"{old_value} to {new_value}"
            )

        if recipe.cook_time != new_cook_time:
            old_value = (
                recipe.cook_time
                if recipe.cook_time is not None
                else "not set"
            )

            new_value = (
                new_cook_time
                if new_cook_time is not None
                else "not set"
            )

            changes.append(
                f"Cook time changed from "
                f"{old_value} to {new_value}"
            )

        if recipe.servings != new_servings:
            old_value = (
                recipe.servings
                if recipe.servings is not None
                else "not set"
            )

            new_value = (
                new_servings
                if new_servings is not None
                else "not set"
            )

            changes.append(
                f"Servings changed from "
                f"{old_value} to {new_value}"
            )

        recipe.title = title
        recipe.description = new_description
        recipe.prep_time = new_prep_time
        recipe.cook_time = new_cook_time
        recipe.servings = new_servings

        if changes:
            record_recipe_history(
                recipe_id=recipe.id,
                action="recipe_updated",
                details="; ".join(changes),
            )

            db.session.commit()

            flash(
                f'"{recipe.title}" was updated.',
                "success",
            )

        else:
            flash(
                "No recipe changes were detected.",
                "success",
            )

        return redirect(
            url_for(
                "recipes.detail",
                id=recipe.id,
            )
        )

    return render_template(
        "recipes/recipe_form.html",
        recipe=recipe,
    )


@recipes.route(
    "/recipebox/<int:id>/delete",
    methods=["POST"],
)
@login_required
def delete_recipe(id):
    recipe = Recipes.query.get_or_404(id)
    title = recipe.title

    db.session.delete(recipe)
    db.session.commit()

    flash(
        f'"{title}" was deleted.',
        "success",
    )

    return redirect(
        url_for("main.index")
    )
