from flask import (
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import login_required
from sqlalchemy import func

from app import db
from app.models import (
    RecipeTypes,
    Tags,
)
from app.recipes import recipes


def normalize_name(value: str) -> str:
    """
    Remove surrounding whitespace and collapse repeated
    internal whitespace.
    """

    return " ".join(value.strip().split())


def recipe_type_name_exists(
    name: str,
    exclude_id: int | None = None,
) -> bool:
    query = RecipeTypes.query.filter(
        func.lower(RecipeTypes.name)
        == name.lower()
    )

    if exclude_id is not None:
        query = query.filter(
            RecipeTypes.id != exclude_id
        )

    return query.first() is not None


def tag_name_exists(
    name: str,
    exclude_id: int | None = None,
) -> bool:
    query = Tags.query.filter(
        func.lower(Tags.name)
        == name.lower()
    )

    if exclude_id is not None:
        query = query.filter(
            Tags.id != exclude_id
        )

    return query.first() is not None


def normalize_recipe_type_positions() -> None:
    """
    Ensure Recipe Type positions remain sequential.
    """

    recipe_types = RecipeTypes.query.order_by(
        RecipeTypes.position,
        RecipeTypes.name,
        RecipeTypes.id,
    ).all()

    for position, recipe_type in enumerate(
        recipe_types,
        start=1,
    ):
        recipe_type.position = position


@recipes.route(
    "/recipebox/classifications",
    methods=["GET"],
)
@login_required
def manage_classifications():
    recipe_types = RecipeTypes.query.order_by(
        RecipeTypes.position,
        RecipeTypes.name,
    ).all()

    tags = Tags.query.order_by(
        Tags.name,
    ).all()

    return render_template(
        "recipes/manage_classifications.html",
        recipe_types=recipe_types,
        tags=tags,
    )


@recipes.route(
    "/recipebox/recipe-types/add",
    methods=["POST"],
)
@login_required
def add_recipe_type():
    name = normalize_name(
        request.form.get("name", "")
    )

    if not name:
        flash(
            "Enter a Recipe Type name.",
            "error",
        )

        return redirect(
            url_for(
                "recipes.manage_classifications"
            )
        )

    if len(name) > 50:
        flash(
            "Recipe Type names cannot exceed "
            "50 characters.",
            "error",
        )

        return redirect(
            url_for(
                "recipes.manage_classifications"
            )
        )

    if recipe_type_name_exists(name):
        flash(
            f'The Recipe Type "{name}" already exists.',
            "error",
        )

        return redirect(
            url_for(
                "recipes.manage_classifications"
            )
        )

    highest_position = (
        db.session.query(
            func.max(RecipeTypes.position)
        ).scalar()
        or 0
    )

    recipe_type = RecipeTypes(
        name=name,
        position=highest_position + 1,
    )

    db.session.add(recipe_type)
    db.session.commit()

    flash(
        f'Recipe Type "{name}" was added.',
        "success",
    )

    return redirect(
        url_for(
            "recipes.manage_classifications"
        )
    )


@recipes.route(
    "/recipebox/recipe-types/<int:id>/rename",
    methods=["POST"],
)
@login_required
def rename_recipe_type(id):
    recipe_type = RecipeTypes.query.get_or_404(id)

    name = normalize_name(
        request.form.get("name", "")
    )

    if not name:
        flash(
            "Enter a Recipe Type name.",
            "error",
        )

        return redirect(
            url_for(
                "recipes.manage_classifications"
            )
        )

    if len(name) > 50:
        flash(
            "Recipe Type names cannot exceed "
            "50 characters.",
            "error",
        )

        return redirect(
            url_for(
                "recipes.manage_classifications"
            )
        )

    if recipe_type_name_exists(
        name,
        exclude_id=recipe_type.id,
    ):
        flash(
            f'The Recipe Type "{name}" already exists.',
            "error",
        )

        return redirect(
            url_for(
                "recipes.manage_classifications"
            )
        )

    old_name = recipe_type.name
    recipe_type.name = name

    db.session.commit()

    flash(
        f'Recipe Type "{old_name}" was renamed '
        f'to "{name}".',
        "success",
    )

    return redirect(
        url_for(
            "recipes.manage_classifications"
        )
    )


@recipes.route(
    "/recipebox/recipe-types/<int:id>/move-up",
    methods=["POST"],
)
@login_required
def move_recipe_type_up(id):
    normalize_recipe_type_positions()
    db.session.flush()

    recipe_type = RecipeTypes.query.get_or_404(id)

    previous_type = RecipeTypes.query.filter(
        RecipeTypes.position
        < recipe_type.position
    ).order_by(
        RecipeTypes.position.desc()
    ).first()

    if previous_type is not None:
        (
            recipe_type.position,
            previous_type.position,
        ) = (
            previous_type.position,
            recipe_type.position,
        )

        db.session.commit()

    else:
        db.session.rollback()

    return redirect(
        url_for(
            "recipes.manage_classifications"
        )
    )


@recipes.route(
    "/recipebox/recipe-types/<int:id>/move-down",
    methods=["POST"],
)
@login_required
def move_recipe_type_down(id):
    normalize_recipe_type_positions()
    db.session.flush()

    recipe_type = RecipeTypes.query.get_or_404(id)

    next_type = RecipeTypes.query.filter(
        RecipeTypes.position
        > recipe_type.position
    ).order_by(
        RecipeTypes.position.asc()
    ).first()

    if next_type is not None:
        (
            recipe_type.position,
            next_type.position,
        ) = (
            next_type.position,
            recipe_type.position,
        )

        db.session.commit()

    else:
        db.session.rollback()

    return redirect(
        url_for(
            "recipes.manage_classifications"
        )
    )


@recipes.route(
    "/recipebox/recipe-types/<int:id>/delete",
    methods=["POST"],
)
@login_required
def delete_recipe_type(id):
    recipe_type = RecipeTypes.query.get_or_404(id)

    name = recipe_type.name
    recipe_count = len(recipe_type.recipes)

    db.session.delete(recipe_type)
    db.session.flush()

    normalize_recipe_type_positions()
    db.session.commit()

    flash(
        f'Recipe Type "{name}" was deleted. '
        f"It was removed from "
        f"{recipe_count} recipe(s).",
        "success",
    )

    return redirect(
        url_for(
            "recipes.manage_classifications"
        )
    )


@recipes.route(
    "/recipebox/tags/add",
    methods=["POST"],
)
@login_required
def add_tag():
    name = normalize_name(
        request.form.get("name", "")
    )

    if not name:
        flash(
            "Enter a Tag name.",
            "error",
        )

        return redirect(
            url_for(
                "recipes.manage_classifications"
            )
        )

    if len(name) > 50:
        flash(
            "Tag names cannot exceed 50 characters.",
            "error",
        )

        return redirect(
            url_for(
                "recipes.manage_classifications"
            )
        )

    if tag_name_exists(name):
        flash(
            f'The Tag "{name}" already exists.',
            "error",
        )

        return redirect(
            url_for(
                "recipes.manage_classifications"
            )
        )

    tag = Tags(name=name)

    db.session.add(tag)
    db.session.commit()

    flash(
        f'Tag "{name}" was added.',
        "success",
    )

    return redirect(
        url_for(
            "recipes.manage_classifications"
        )
    )


@recipes.route(
    "/recipebox/tags/<int:id>/rename",
    methods=["POST"],
)
@login_required
def rename_tag(id):
    tag = Tags.query.get_or_404(id)

    name = normalize_name(
        request.form.get("name", "")
    )

    if not name:
        flash(
            "Enter a Tag name.",
            "error",
        )

        return redirect(
            url_for(
                "recipes.manage_classifications"
            )
        )

    if len(name) > 50:
        flash(
            "Tag names cannot exceed 50 characters.",
            "error",
        )

        return redirect(
            url_for(
                "recipes.manage_classifications"
            )
        )

    if tag_name_exists(
        name,
        exclude_id=tag.id,
    ):
        flash(
            f'The Tag "{name}" already exists.',
            "error",
        )

        return redirect(
            url_for(
                "recipes.manage_classifications"
            )
        )

    old_name = tag.name
    tag.name = name

    db.session.commit()

    flash(
        f'Tag "{old_name}" was renamed '
        f'to "{name}".',
        "success",
    )

    return redirect(
        url_for(
            "recipes.manage_classifications"
        )
    )


@recipes.route(
    "/recipebox/tags/<int:id>/delete",
    methods=["POST"],
)
@login_required
def delete_tag(id):
    tag = Tags.query.get_or_404(id)

    name = tag.name
    recipe_count = len(tag.recipes)

    db.session.delete(tag)
    db.session.commit()

    flash(
        f'Tag "{name}" was deleted. '
        f"It was removed from "
        f"{recipe_count} recipe(s).",
        "success",
    )

    return redirect(
        url_for(
            "recipes.manage_classifications"
        )
    )
