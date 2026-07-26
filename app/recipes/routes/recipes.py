from flask import (
    flash,
    redirect,
    render_template,
    request,
    url_for,
)

from app import db
from app.models import Recipes, RecipeTypes, Tags
from app.recipes import recipes
from app.recipes.services import (
    parse_optional_nonnegative_integer, UNIT_LABELS
)
from flask_login import current_user, login_required

from app.recipes.history import record_recipe_history

def get_submitted_recipe_types():
    raw_type_ids = request.form.getlist("recipe_type_ids")

    try:
        selected_type_ids = {
            int(type_id)
            for type_id in raw_type_ids
        }
    except ValueError as error:
        raise ValueError(
            "One or more selected recipe types are invalid."
        ) from error

    if not selected_type_ids:
        return [], set()

    selected_types = RecipeTypes.query.filter(
        RecipeTypes.id.in_(selected_type_ids)
    ).all()

    found_type_ids = {
        recipe_type.id
        for recipe_type in selected_types
    }

    if found_type_ids != selected_type_ids:
        raise ValueError(
            "One or more selected recipe types no longer exist."
        )

    return selected_types, selected_type_ids

def get_submitted_tags():
    raw_tag_ids = request.form.getlist("tag_ids")

    try:
        selected_tag_ids = {
            int(tag_id)
            for tag_id in raw_tag_ids
        }

    except ValueError as error:
        raise ValueError(
            "One or more selected tags are invalid."
        ) from error

    if not selected_tag_ids:
        return [], set()

    selected_tags = Tags.query.filter(
        Tags.id.in_(selected_tag_ids)
    ).all()

    found_tag_ids = {
        tag.id
        for tag in selected_tags
    }

    if found_tag_ids != selected_tag_ids:
        raise ValueError(
            "One or more selected tags no longer exist."
        )

    return selected_tags, selected_tag_ids    
    
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
    recipe_types = RecipeTypes.query.order_by(
        RecipeTypes.position,
        RecipeTypes.name,
    ).all()
    
    tags = Tags.query.order_by(
        Tags.name,
    ).all()

    
    selected_type_ids = set()
    selected_tag_ids = set()
    
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get(
            "description",
            "",
        ).strip()
        
        raw_selected_type_ids = request.form.getlist(
            "recipe_type_ids"
        )

        selected_type_ids = {
            int(type_id)
            for type_id in raw_selected_type_ids
            if type_id.isdigit()
        }

        raw_selected_tag_ids = request.form.getlist(
            "tag_ids"
        )

        selected_tag_ids = {
            int(tag_id)
            for tag_id in raw_selected_tag_ids
            if tag_id.isdigit()
        }

        try:
            (
                selected_types,
                selected_type_ids,
            ) = get_submitted_recipe_types()

            (
                selected_tags,
                selected_tag_ids,
            ) = get_submitted_tags()

        except ValueError as error:
            flash(str(error), "error")

            return render_template(
                "recipes/recipe_form.html",
                recipe=None,
                recipe_types=recipe_types,
                tags=tags,
                selected_type_ids=selected_type_ids,
                selected_tag_ids=selected_tag_ids,
                
            )


        if not title:
            flash("A recipe title is required.", "error")

            return render_template(
                "recipes/recipe_form.html",
                recipe=None,
                recipe_types=recipe_types,
                tags=tags,
                selected_type_ids=selected_type_ids,
                selected_tag_ids=selected_tag_ids,
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
                recipe_types=recipe_types,
                tags=tags,
                selected_type_ids=selected_type_ids,
                selected_tag_ids=selected_tag_ids,
            )

        recipe = Recipes(
            title=title,
            description=description or None,
            prep_time=prep_time,
            cook_time=cook_time,
            servings=servings,
            created_by=current_user.id,
        )
         
        recipe.types = selected_types

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
        recipe_types=recipe_types,
        tags=tags,
        selected_type_ids=selected_type_ids,
        selected_tag_ids=selected_tag_ids,
    )


@recipes.route(
    "/recipebox/<int:id>/edit",
    methods=["GET", "POST"],
)
@login_required
def edit_recipe(id):
    recipe = Recipes.query.get_or_404(id)
    
    recipe_types = RecipeTypes.query.order_by(
        RecipeTypes.position,
        RecipeTypes.name,
    ).all()
    
    tags = Tags.query.order_by(
            Tags.name,
        ).all() 

    selected_type_ids = {
        recipe_type.id
        for recipe_type in recipe.types
    }
    
    selected_tag_ids = {
        tag.id
        for tag in recipe.tags
    }
    
    if request.method == "POST":
        title = request.form.get(
            "title",
            "",
        ).strip()

        description = request.form.get(
            "description",
            "",
        ).strip()

        raw_selected_type_ids = request.form.getlist(
            "recipe_type_ids"
        )

        selected_type_ids = {
            int(type_id)
            for type_id in raw_selected_type_ids
            if type_id.isdigit()
        }
        
        raw_selected_tag_ids = request.form.getlist(
            "tag_ids"
        )

        selected_tag_ids = {
            int(tag_id)
            for tag_id in raw_selected_tag_ids
            if tag_id.isdigit()
        }

        try:
            (
                selected_types,
                selected_type_ids,
            ) = get_submitted_recipe_types()
            
            (
                selected_tags,
                selected_tag_ids,
            ) = get_submitted_tags()

        except ValueError as error:
            flash(str(error), "error")

            return render_template(
                "recipes/recipe_form.html",
                recipe=recipe,
                recipe_types=recipe_types,
                tags=tags,
                selected_type_ids=selected_type_ids,
                selected_tag_ids=selected_tag_ids,
            )


        if not title:
            flash(
                "A recipe title is required.",
                "error",
            )

            return render_template(
                "recipes/recipe_form.html",
                recipe=recipe,
                recipe_types=recipe_types,
                tags=tags,
                selected_type_ids=selected_type_ids,
                selected_tag_ids=selected_tag_ids,
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
                recipe_types=recipe_types,
                tags=tags,
                selected_type_ids=selected_type_ids,
                selected_tag_ids=selected_tag_ids,
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
            
        old_type_names = {
            recipe_type.name
            for recipe_type in recipe.types
        }

        new_type_names = {
            recipe_type.name
            for recipe_type in selected_types
        }

        added_type_names = sorted(
            new_type_names - old_type_names
        )

        removed_type_names = sorted(
            old_type_names - new_type_names
        )

        if added_type_names:
            changes.append(
                "Added recipe types: "
                + ", ".join(added_type_names)
            )

        if removed_type_names:
            changes.append(
                "Removed recipe types: "
                + ", ".join(removed_type_names)
            )
         
        old_tag_names = {
            tag.name
            for tag in recipe.tags
        }

        new_tag_names = {
            tag.name
            for tag in selected_tags
        }

        added_tag_names = sorted(
            new_tag_names - old_tag_names
        )

        removed_tag_names = sorted(
            old_tag_names - new_tag_names
        )

        if added_tag_names:
            changes.append(
                "Added tags: "
                + ", ".join(added_tag_names)
            )

        if removed_tag_names:
            changes.append(
                "Removed tags: "
                + ", ".join(removed_tag_names)
            )
        

        recipe.title = title
        recipe.description = new_description
        recipe.prep_time = new_prep_time
        recipe.cook_time = new_cook_time
        recipe.servings = new_servings
        recipe.types = selected_types
        recipe.tags = selected_tags

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
        recipe_types=recipe_types,
        tags=tags,
        selected_type_ids=selected_type_ids,
        selected_tag_ids=selected_tag_ids,
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
