from flask import flash, redirect, render_template, request, url_for, abort

from app import db
from app.models import (
    Ingredients,
    RecipeIngredients,
    Recipes,
)
from app.recipes import recipes
from app.recipes.services import (
    compact_positions,
    find_ingredient_by_name,
    get_next_position,
    move_ordered_item,
    normalize_name,
    UNIT_CHOICES,
    get_next_ingredient_position,
    get_or_create_ingredient

)

from flask_login import login_required

from app.recipes.history import record_recipe_history

def format_ingredient_description(
    ingredient_name,
    quantity=None,
    unit=None,
    prefix=None,
):
    """
    Create a readable ingredient description for history records.
    """

    parts = []

    if prefix:
        parts.append(str(prefix).strip())

    if quantity:
        parts.append(str(quantity).strip())

    if unit:
        parts.append(str(unit).replace("_", " ").strip())

    if ingredient_name:
        parts.append(str(ingredient_name).strip())

    return " ".join(parts)

def resolve_ingredient_from_form():
    """
    Resolve either a selected existing ingredient or a new ingredient.

    Returns:
        Ingredients instance

    Raises:
        ValueError for invalid form input.
    """

    ingredient_selection = request.form.get(
        "ingredient_id",
        "",
    ).strip()

    new_name = normalize_name(
        request.form.get("name")
    )

    if ingredient_selection != "new" and new_name:
        raise ValueError(
            "Select an existing ingredient or enter a new "
            "ingredient, not both."
        )

    if ingredient_selection == "new":
        if not new_name:
            raise ValueError(
                "Enter a name for the new ingredient."
            )

        ingredient = find_ingredient_by_name(new_name)

        if ingredient is None:
            ingredient = Ingredients(
                name=new_name,
                category=(
                    request.form.get("category", "").strip()
                    or None
                ),
            )

            db.session.add(ingredient)
            db.session.flush()

        return ingredient

    if not ingredient_selection:
        raise ValueError("Select an ingredient.")

    try:
        ingredient_id = int(ingredient_selection)
    except ValueError as exc:
        raise ValueError(
            "Select a valid ingredient."
        ) from exc

    ingredient = db.session.get(
        Ingredients,
        ingredient_id,
    )

    if ingredient is None:
        raise ValueError(
            "The selected ingredient could not be found."
        )

    return ingredient


@recipes.route(
    "/recipebox/<int:recipe_id>/ingredient/new",
    methods=["GET", "POST"],
)
@login_required
def new_ingredient(recipe_id):
    recipe = Recipes.query.get_or_404(recipe_id)

    if request.method == "POST":
        ingredient_name = request.form.get(
            "ingredient_name",
            "",
        )

        category = request.form.get(
            "category",
            "",
        )

        quantity = (
            request.form.get("quantity", "").strip()
            or None
        )

        unit = (
            request.form.get("unit", "").strip()
            or None
        )

        try:
            ingredient, ingredient_created = (
                get_or_create_ingredient(
                    ingredient_name,
                    category,
                )
            )
        except ValueError as error:
            flash(str(error), "error")

            return render_template(
                "recipes/ingredient_form.html",
                recipe=recipe,
                item=None,
                ingredients=Ingredients.query.order_by(
                    Ingredients.name
                ).all(),
                unit_choices=UNIT_CHOICES,
            )

        existing = RecipeIngredients.query.filter_by(
            recipe_id=recipe.id,
            ingredient_id=ingredient.id,
        ).first()

        if existing is not None:
            flash(
                f"{ingredient.name} is already in this recipe.",
                "error",
            )

            return render_template(
                "recipes/ingredient_form.html",
                recipe=recipe,
                item=None,
                ingredients=Ingredients.query.order_by(
                    Ingredients.name
                ).all(),
                unit_choices=UNIT_CHOICES,
            )

        item = RecipeIngredients(
            recipe_id=recipe.id,
            ingredient_id=ingredient.id,
            quantity=quantity,
            unit=unit,
            position=get_next_ingredient_position(
                recipe.id
            ),
        )

        db.session.add(item)

        record_recipe_history(
            recipe_id=recipe.id,
            action="ingredient_added",
            details=format_ingredient_description(
                ingredient_name=ingredient.name,
                quantity=quantity,
                unit=unit,
                prefix="Added",
            ),
        )

        db.session.commit()

        if ingredient_created:
            flash(
                f"{ingredient.name} was created and added.",
                "success",
            )
        else:
            flash(
                f"{ingredient.name} was added.",
                "success",
            )

        return redirect(
            url_for(
                "recipes.detail",
                id=recipe.id,
            )
        )

    return render_template(
        "recipes/ingredient_form.html",
        recipe=recipe,
        item=None,
        ingredients=Ingredients.query.order_by(
            Ingredients.name
        ).all(),
        unit_choices=UNIT_CHOICES,
    )
    

@recipes.route(
    "/recipebox/ingredient/<int:id>/edit",
    methods=["GET", "POST"],
)
@login_required
def edit_ingredient(id):
    item = RecipeIngredients.query.get_or_404(id)
    recipe = item.recipe

    if request.method == "POST":
        ingredient_name = request.form.get(
            "ingredient_name",
            "",
        )

        category = request.form.get(
            "category",
            "",
        )

        quantity = (
            request.form.get("quantity", "").strip()
            or None
        )

        unit = (
            request.form.get("unit", "").strip()
            or None
        )

        try:
            ingredient, ingredient_created = (
                get_or_create_ingredient(
                    ingredient_name,
                    category,
                )
            )
        except ValueError as error:
            flash(str(error), "error")

            return render_template(
                "recipes/ingredient_form.html",
                recipe=recipe,
                item=item,
                ingredients=Ingredients.query.order_by(
                    Ingredients.name
                ).all(),
                unit_choices=UNIT_CHOICES,
            )

        existing = RecipeIngredients.query.filter(
            RecipeIngredients.recipe_id
            == item.recipe_id,
            RecipeIngredients.ingredient_id
            == ingredient.id,
            RecipeIngredients.id != item.id,
        ).first()

        if existing is not None:
            flash(
                f"{ingredient.name} is already in this recipe.",
                "error",
            )

            return render_template(
                "recipes/ingredient_form.html",
                recipe=recipe,
                item=item,
                ingredients=Ingredients.query.order_by(
                    Ingredients.name
                ).all(),
                unit_choices=UNIT_CHOICES,
            )
            
        old_ingredient_name = item.ingredient.name
        old_quantity = item.quantity
        old_unit = item.unit

        old_description = format_ingredient_description(
            ingredient_name=old_ingredient_name,
            quantity=old_quantity,
            unit=old_unit,
        )

        new_description = format_ingredient_description(
            ingredient_name=ingredient.name,
            quantity=quantity,
            unit=unit,
        )

        ingredient_changed = (
            item.ingredient_id != ingredient.id
            or item.quantity != quantity
            or item.unit != unit
)


        item.ingredient_id = ingredient.id
        item.quantity = quantity
        item.unit = unit
        
        if ingredient_changed:
            record_recipe_history(
                recipe_id=item.recipe_id,
                action="ingredient_updated",
                details=(
                    f"Changed {old_description} "
                    f"to {new_description}"
                ),
            )

        db.session.commit()

        if ingredient_created:
            flash(
                f"{ingredient.name} was created and selected.",
                "success",
            )
        else:
            flash(
                "The ingredient was updated.",
                "success",
            )

        return redirect(
            url_for(
                "recipes.detail",
                id=recipe.id,
            )
        )

    return render_template(
        "recipes/ingredient_form.html",
        recipe=recipe,
        item=item,
        ingredients=Ingredients.query.order_by(
            Ingredients.name
        ).all(),
        unit_choices=UNIT_CHOICES,
    )


@recipes.route(
    "/recipebox/ingredient/<int:id>/delete",
    methods=["POST"],
)
@login_required
def delete_ingredient(id):
    item = RecipeIngredients.query.get_or_404(id)

    recipe_id = item.recipe_id
    ingredient_name = item.ingredient.name

    ingredient_description = (
        format_ingredient_description(
            ingredient_name=ingredient_name,
            quantity=item.quantity,
            unit=item.unit,
        )
    )

    db.session.delete(item)

    record_recipe_history(
        recipe_id=recipe_id,
        action="ingredient_deleted",
        details=f"Removed {ingredient_description}",
    )

    db.session.commit()

    flash(
        f"{ingredient_name} was removed from the recipe.",
        "success",
    )

    return redirect(
        url_for(
            "recipes.detail",
            id=recipe_id,
        )
    )

@recipes.route(
    "/recipebox/ingredient/<int:id>/move/<string:direction>",
    methods=["POST"],
)
@login_required
def move_ingredient(id, direction):
    item = RecipeIngredients.query.get_or_404(id)

    if direction == "up":
        other_item = (
            RecipeIngredients.query
            .filter(
                RecipeIngredients.recipe_id == item.recipe_id,
                RecipeIngredients.position < item.position,
            )
            .order_by(RecipeIngredients.position.desc())
            .first()
        )

    elif direction == "down":
        other_item = (
            RecipeIngredients.query
            .filter(
                RecipeIngredients.recipe_id == item.recipe_id,
                RecipeIngredients.position > item.position,
            )
            .order_by(RecipeIngredients.position.asc())
            .first()
        )

    else:
        abort(400)

    if other_item is not None:
        item_position = item.position
        other_position = other_item.position

        item.position = other_position
        other_item.position = item_position

        db.session.commit()

    return redirect(
        url_for(
            "recipes.detail",
            id=item.recipe_id,
        )
    )
