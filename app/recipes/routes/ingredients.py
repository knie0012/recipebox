from flask import (
    abort,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import login_required

from app import db
from app.models import (
    Ingredients,
    RecipeIngredients,
    RecipeSection,
    Recipes,
)
from app.recipes import recipes
from app.recipes.history import (
    record_recipe_history,
)
from app.recipes.services import (
    UNIT_CHOICES,
    compact_section_ingredient_positions,
    get_next_section_ingredient_position,
    get_or_create_ingredient,
    get_or_create_recipe_section,
)


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
        parts.append(
            str(prefix).strip()
        )

    if quantity:
        parts.append(
            str(quantity).strip()
        )

    if unit:
        parts.append(
            str(unit)
            .replace("_", " ")
            .strip()
        )

    if ingredient_name:
        parts.append(
            str(ingredient_name).strip()
        )

    return " ".join(parts)


def get_section_label(
    section: RecipeSection | None,
) -> str:
    """
    Return a readable section name for history records.
    """

    if section is None:
        return "no section"

    return section.name


def get_section_choices(
    recipe_id: int,
) -> list[RecipeSection]:
    """
    Return a recipe's sections in display order.
    """

    return (
        RecipeSection.query
        .filter(
            RecipeSection.recipe_id == recipe_id
        )
        .order_by(
            RecipeSection.position,
            RecipeSection.id,
        )
        .all()
    )

def resolve_recipe_section_from_form(
    recipe_id: int,
):
    """
    Resolve an existing section, a newly entered section,
    or no section from the ingredient form.
    """

    section_selection = request.form.get(
        "section_id",
        "",
    ).strip()

    new_section_name = request.form.get(
        "new_section_name",
        "",
    ).strip()

    if section_selection == "new":
        if not new_section_name:
            raise ValueError(
                "Enter a name for the new recipe section."
            )

        return get_or_create_recipe_section(
            recipe_id=recipe_id,
            section_name=new_section_name,
        )

    if new_section_name:
        raise ValueError(
            "Select New Section before entering a new "
            "section name."
        )

    if not section_selection:
        return None, False

    try:
        section_id = int(section_selection)

    except ValueError as exc:
        raise ValueError(
            "Select a valid recipe section."
        ) from exc

    section = (
        RecipeSection.query
        .filter(
            RecipeSection.id == section_id,
            RecipeSection.recipe_id == recipe_id,
        )
        .first()
    )

    if section is None:
        raise ValueError(
            "The selected recipe section could not be found."
        )

    return section, False
    
    

@recipes.route(
    "/recipebox/<int:recipe_id>/ingredient/new",
    methods=["GET", "POST"],
)
@login_required
def new_ingredient(recipe_id):
    recipe = Recipes.query.get_or_404(
        recipe_id
    )

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
            request.form.get(
                "quantity",
                "",
            ).strip()
            or None
        )

        unit = (
            request.form.get(
                "unit",
                "",
            ).strip()
            or None
        )

        try:
            ingredient, ingredient_created = (
                get_or_create_ingredient(
                    ingredient_name,
                    category,
                )
            )

            recipe_section, section_created = (
                resolve_recipe_section_from_form(
                    recipe.id
                )
            )

        except ValueError as error:
            flash(
                str(error),
                "error",
            )

            return render_template(
                "recipes/ingredient_form.html",
                recipe=recipe,
                item=None,
                ingredients=(
                    Ingredients.query
                    .order_by(
                        Ingredients.name
                    )
                    .all()
                ),
                sections=get_section_choices(
                    recipe.id
                ),
                unit_choices=UNIT_CHOICES,
            )

        section_id = (
            recipe_section.id
            if recipe_section is not None
            else None
        )

        item = RecipeIngredients(
            recipe_id=recipe.id,
            ingredient_id=ingredient.id,
            quantity=quantity,
            section_id=section_id,
            unit=unit,
            position=(
                get_next_section_ingredient_position(
                    recipe.id,
                    section_id,
                )
            ),
        )

        db.session.add(item)

        details = format_ingredient_description(
            ingredient_name=ingredient.name,
            quantity=quantity,
            unit=unit,
            prefix="Added",
        )

        if recipe_section is not None:
            details += (
                f' to section "{recipe_section.name}"'
            )

        record_recipe_history(
            recipe_id=recipe.id,
            action="ingredient_added",
            details=details,
        )

        db.session.commit()

        if ingredient_created:
            message = (
                f"{ingredient.name} was created and added."
            )
        else:
            message = (
                f"{ingredient.name} was added."
            )

        if section_created:
            message += (
                f' Section "{recipe_section.name}" '
                f"was also created."
            )

        flash(
            message,
            "success",
        )

        return redirect(
            url_for(
                "recipes.detail",
                id=recipe.id,
                _anchor="ingredients",

            )
        )

    return render_template(
        "recipes/ingredient_form.html",
        recipe=recipe,
        item=None,
        ingredients=(
            Ingredients.query
            .order_by(
                Ingredients.name
            )
            .all()
        ),
        sections=get_section_choices(
            recipe.id
        ),
        unit_choices=UNIT_CHOICES,
    )


@recipes.route(
    "/recipebox/ingredient/<int:id>/edit",
    methods=["GET", "POST"],
)
@login_required
def edit_ingredient(id):
    item = RecipeIngredients.query.get_or_404(
        id
    )

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
            request.form.get(
                "quantity",
                "",
            ).strip()
            or None
        )

        unit = (
            request.form.get(
                "unit",
                "",
            ).strip()
            or None
        )

        try:
            ingredient, ingredient_created = (
                get_or_create_ingredient(
                    ingredient_name,
                    category,
                )
            )

            new_section, section_created = (
                resolve_recipe_section_from_form(
                    recipe.id
                )
            )

        except ValueError as error:
            flash(
                str(error),
                "error",
            )

            return render_template(
                "recipes/ingredient_form.html",
                recipe=recipe,
                item=item,
                ingredients=(
                    Ingredients.query
                    .order_by(
                        Ingredients.name
                    )
                    .all()
                ),
                sections=get_section_choices(
                    recipe.id
                ),
                unit_choices=UNIT_CHOICES,
            )

        old_ingredient_name = (
            item.ingredient.name
        )

        old_quantity = item.quantity
        old_unit = item.unit
        old_section = item.recipe_section
        old_section_id = item.section_id

        new_section_id = (
            new_section.id
            if new_section is not None
            else None
        )

        old_description = (
            format_ingredient_description(
                ingredient_name=old_ingredient_name,
                quantity=old_quantity,
                unit=old_unit,
            )
        )

        new_description = (
            format_ingredient_description(
                ingredient_name=ingredient.name,
                quantity=quantity,
                unit=unit,
            )
        )

        section_changed = (
            old_section_id != new_section_id
        )

        ingredient_changed = (
            item.ingredient_id != ingredient.id
            or item.quantity != quantity
            or item.unit != unit
            or section_changed
        )

        item.ingredient_id = ingredient.id
        item.quantity = quantity
        item.unit = unit

        if section_changed:
            item.section_id = new_section_id

            item.position = (
                get_next_section_ingredient_position(
                    recipe.id,
                    new_section_id,
                )
            )

            db.session.flush()

            compact_section_ingredient_positions(
                recipe.id,
                old_section_id,
            )

            compact_section_ingredient_positions(
                recipe.id,
                new_section_id,
            )

        if ingredient_changed:
            details = (
                f"Changed {old_description} "
                f"to {new_description}"
            )

            if section_changed:
                details += (
                    ". Section changed from "
                    f"{get_section_label(old_section)} "
                    f"to {get_section_label(new_section)}"
                )

            record_recipe_history(
                recipe_id=item.recipe_id,
                action="ingredient_updated",
                details=details,
            )

        db.session.commit()

        if not ingredient_changed:
            flash(
                "No ingredient changes were detected.",
                "success",
            )

        elif ingredient_created:
            flash(
                f"{ingredient.name} was created and selected.",
                "success",
            )

        elif section_created:
            flash(
                f'The ingredient was updated and section '
                f'"{new_section.name}" was created.',
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
                _anchor="ingredients",

            )
        )

    return render_template(
        "recipes/ingredient_form.html",
        recipe=recipe,
        item=item,
        ingredients=(
            Ingredients.query
            .order_by(
                Ingredients.name
            )
            .all()
        ),
        sections=get_section_choices(
            recipe.id
        ),
        unit_choices=UNIT_CHOICES,
    )


@recipes.route(
    "/recipebox/ingredient/<int:id>/delete",
    methods=["POST"],
)
@login_required
def delete_ingredient(id):
    item = RecipeIngredients.query.get_or_404(
        id
    )

    recipe_id = item.recipe_id
    section_id = item.section_id
    ingredient_name = item.ingredient.name

    ingredient_description = (
        format_ingredient_description(
            ingredient_name=ingredient_name,
            quantity=item.quantity,
            unit=item.unit,
        )
    )

    db.session.delete(item)
    db.session.flush()

    compact_section_ingredient_positions(
        recipe_id,
        section_id,
    )

    record_recipe_history(
        recipe_id=recipe_id,
        action="ingredient_deleted",
        details=(
            f"Removed {ingredient_description}"
        ),
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
            _anchor="ingredients",

        )
    )


@recipes.route(
    "/recipebox/ingredient/<int:id>/move/<string:direction>",
    methods=["POST"],
)
@login_required
def move_ingredient(id, direction):
    item = RecipeIngredients.query.get_or_404(
        id
    )

    query = RecipeIngredients.query.filter(
        RecipeIngredients.recipe_id
        == item.recipe_id
    )

    if item.section_id is None:
        query = query.filter(
            RecipeIngredients.section_id.is_(None)
        )
    else:
        query = query.filter(
            RecipeIngredients.section_id
            == item.section_id
        )

    if direction == "up":
        other_item = (
            query
            .filter(
                RecipeIngredients.position
                < item.position
            )
            .order_by(
                RecipeIngredients.position.desc()
            )
            .first()
        )

    elif direction == "down":
        other_item = (
            query
            .filter(
                RecipeIngredients.position
                > item.position
            )
            .order_by(
                RecipeIngredients.position.asc()
            )
            .first()
        )

    else:
        abort(400)

    if other_item is not None:
        item.position, other_item.position = (
            other_item.position,
            item.position,
        )

        db.session.commit()

    return redirect(
        url_for(
            "recipes.detail",
            id=item.recipe_id,
            _anchor="ingredients",

        )
    )