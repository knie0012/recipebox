from flask import (
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import (
    current_user,
    login_required,
)

from app import db
from app.imports import imports
from app.imports.services import (
    RecipeImportError,
    delete_import_draft,
    download_imported_image,
    extract_recipe_from_url,
    load_import_draft,
    prepare_import_for_review,
    save_import_draft,
)
from app.models import (
    RecipeImages,
    RecipeIngredients,
    RecipeSteps,
    Recipes,
    RecipeTypes,
    Tags,
)
from app.recipes.history import (
    record_recipe_history,
)
from app.recipes.services import (
    UNIT_CHOICES,
    get_next_section_ingredient_position,
    get_or_create_ingredient,
    get_or_create_recipe_section,
    parse_optional_nonnegative_integer,
)

import re

def get_indexed_form_values(
    prefix: str,
    field_name: str,
    count: int,
) -> list[str]:
    """
    Read indexed fields such as ingredient_0_name.
    """

    return [
        request.form.get(
            f"{prefix}_{index}_{field_name}",
            "",
        ).strip()
        for index in range(count)
    ]


def parse_servings_number(
    value: str,
) -> int | None:
    """
    Extract the first whole number from imported yield text.
    """

    match = re.search(
        r"\d+",
        value or "",
    )

    if not match:
        return None

    return int(match.group())

def get_submitted_recipe_types() -> list[RecipeTypes]:
    """
    Validate submitted recipe type IDs and return the records.
    """

    raw_type_ids = request.form.getlist(
        "recipe_type_ids"
    )

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
        return []

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

    return selected_types

def get_submitted_tags() -> list[Tags]:
    """
    Validate submitted tag IDs and return the records.
    """

    raw_tag_ids = request.form.getlist(
        "tag_ids"
    )

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
        return []

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

    return selected_tags    
    
@imports.route(
    "/recipebox/import",
    methods=["GET", "POST"],
)
@login_required
def import_url():
    if request.method == "POST":
        source_url = request.form.get(
            "source_url",
            "",
        ).strip()

        if not source_url:
            flash(
                "Enter a recipe URL.",
                "error",
            )

            return render_template(
                "imports/url_form.html",
                source_url=source_url,
            )

        try:
            extracted_recipe = (
                extract_recipe_from_url(
                    source_url
                )
            )

            imported_recipe = (
                prepare_import_for_review(
                    extracted_recipe
                )
            )

            import_token = save_import_draft(
                imported_recipe,
                current_user.id,
            )

        except RecipeImportError as error:
            flash(
                str(error),
                "error",
            )

            return render_template(
                "imports/url_form.html",
                source_url=source_url,
            )

        return redirect(
            url_for(
                "imports.review_import",
                import_token=import_token,
            )
        )

    return render_template(
        "imports/url_form.html",
        source_url="",
    )


@imports.route(
    "/recipebox/import/<string:import_token>/review",
    methods=["GET"],
)
@login_required
def review_import(import_token):
    try:
        imported_recipe = load_import_draft(
            import_token,
            current_user.id,
        )

    except RecipeImportError as error:
        flash(str(error), "error")

        return redirect(
            url_for("imports.import_url")
        )

    servings = parse_servings_number(
        imported_recipe.get(
            "servings_text",
            "",
        )
    )
    
    recipe_types = RecipeTypes.query.order_by(
        RecipeTypes.position,
        RecipeTypes.name,
    ).all()
    
    tags = Tags.query.order_by(
        Tags.name
    ).all()

    return render_template(
        "imports/review.html",
        imported_recipe=imported_recipe,
        import_token=import_token,
        unit_choices=UNIT_CHOICES,
        servings=servings,
        recipe_types=recipe_types,
        tags=tags,
    )


@imports.route(
    "/recipebox/import/<string:import_token>/save",
    methods=["POST"],
)
@login_required
def save_import(import_token):
    try:
        imported_recipe = load_import_draft(
            import_token,
            current_user.id,
        )

    except RecipeImportError as error:
        flash(
            str(error),
            "error",
        )

        return redirect(
            url_for("imports.import_url")
        )

    title = request.form.get(
        "title",
        "",
    ).strip()

    description = (
        request.form.get(
            "description",
            "",
        ).strip()
        or None
    )

    try:
        selected_types = (
            get_submitted_recipe_types()
        )
        
        selected_tags = (
            get_submitted_tags()
        )

    except ValueError as error:
        flash(
            str(error),
            "error",
        )

        return redirect(
            url_for(
                "imports.review_import",
                import_token=import_token,
            )
        )

    if not title:
        flash(
            "A recipe title is required.",
            "error",
        )

        return redirect(
            url_for(
                "imports.review_import",
                import_token=import_token,
            )
        )

    try:
        prep_time = (
            parse_optional_nonnegative_integer(
                request.form.get("prep_time"),
                "Prep time",
            )
        )

        cook_time = (
            parse_optional_nonnegative_integer(
                request.form.get("cook_time"),
                "Cook time",
            )
        )

        servings = (
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

        return redirect(
            url_for(
                "imports.review_import",
                import_token=import_token,
            )
        )

    try:
        ingredient_count = int(
            request.form.get(
                "ingredient_count",
                "0",
            )
        )

        step_count = int(
            request.form.get(
                "step_count",
                "0",
            )
        )

    except ValueError:
        flash(
            "The imported recipe form was invalid.",
            "error",
        )

        return redirect(
            url_for(
                "imports.review_import",
                import_token=import_token,
            )
        )

    if (
        ingredient_count < 1
        or ingredient_count > 500
        or step_count < 1
        or step_count > 500
    ):
        flash(
            "The imported recipe has an invalid number "
            "of ingredients or steps.",
            "error",
        )

        return redirect(
            url_for(
                "imports.review_import",
                import_token=import_token,
            )
        )

    ingredient_rows = []

    for index in range(ingredient_count):
        ingredient_name = request.form.get(
            f"ingredient_{index}_name",
            "",
        ).strip()

        quantity = (
            request.form.get(
                f"ingredient_{index}_quantity",
                "",
            ).strip()
            or None
        )
        
        section = (
            request.form.get(
                f"ingredient_{index}_section",
                "",
            ).strip()
            or None
        )

        unit = (
            request.form.get(
                f"ingredient_{index}_unit",
                "",
            ).strip()
            or None
        )

        include = (
            request.form.get(
                f"ingredient_{index}_include"
            )
            == "yes"
        )

        if not include:
            continue

        if not ingredient_name:
            flash(
                f"Ingredient {index + 1} needs a name.",
                "error",
            )

            return redirect(
                url_for(
                    "imports.review_import",
                    import_token=import_token,
                )
            )

        ingredient_rows.append(
            {
                "name": ingredient_name,
                "quantity": quantity,
                "unit": unit,
                "section": section,

            }
        )

    step_rows = []

    for index in range(step_count):
        instruction = request.form.get(
            f"step_{index}_instruction",
            "",
        ).strip()

        include = (
            request.form.get(
                f"step_{index}_include"
            )
            == "yes"
        )

        if not include:
            continue

        if not instruction:
            flash(
                f"Step {index + 1} cannot be empty.",
                "error",
            )

            return redirect(
                url_for(
                    "imports.review_import",
                    import_token=import_token,
                )
            )

        try:
            timer_minutes = (
                parse_optional_nonnegative_integer(
                    request.form.get(
                        f"step_{index}_timer_minutes"
                    ),
                    f"Step {index + 1} timer",
                )
            )

        except ValueError as error:
            flash(
                str(error),
                "error",
            )

            return redirect(
                url_for(
                    "imports.review_import",
                    import_token=import_token,
                )
            )

        step_rows.append(
            {
                "instruction": instruction,
                "timer_minutes": timer_minutes,
            }
        )

    if not ingredient_rows:
        flash(
            "Keep at least one ingredient.",
            "error",
        )

        return redirect(
            url_for(
                "imports.review_import",
                import_token=import_token,
            )
        )

    if not step_rows:
        flash(
            "Keep at least one recipe step.",
            "error",
        )

        return redirect(
            url_for(
                "imports.review_import",
                import_token=import_token,
            )
        )

    imported_file_path = None

    try:
        recipe = Recipes(
            title=title,
            description=description,
            prep_time=prep_time,
            cook_time=cook_time,
            servings=servings,
            created_by=current_user.id,
        )
        
        recipe.types = selected_types
        recipe.tags = selected_tags
        
        db.session.add(recipe)
        db.session.flush()

        for ingredient_data in ingredient_rows:
            ingredient, _ = get_or_create_ingredient(
                ingredient_data["name"]
            )

            recipe_section, _ = (
                get_or_create_recipe_section(
                    recipe_id=recipe.id,
                    section_name=ingredient_data[
                        "section"
                    ],
                )
            )

            section_id = (
                recipe_section.id
                if recipe_section is not None
                else None
            )

            position = (
                get_next_section_ingredient_position(
                    recipe_id=recipe.id,
                    section_id=section_id,
                )
            )

            db.session.add(
                RecipeIngredients(
                    recipe_id=recipe.id,
                    ingredient_id=ingredient.id,
                    quantity=ingredient_data[
                        "quantity"
                    ],
                    unit=ingredient_data["unit"],
                    section_id=section_id,
                    position=position,
                )
            )

        for position, step_data in enumerate(
            step_rows,
            start=1,
        ):
            db.session.add(
                RecipeSteps(
                    recipe_id=recipe.id,
                    position=position,
                    instruction=step_data[
                        "instruction"
                    ],
                    timer_minutes=step_data[
                        "timer_minutes"
                    ],
                )
            )

        import_image = (
            request.form.get("import_image")
            == "yes"
        )

        image_url = imported_recipe.get(
            "image_url",
            "",
        )

        if import_image and image_url:
            stored_filename, imported_file_path = (
                download_imported_image(
                    image_url,
                    recipe.id,
                )
            )

            db.session.add(
                RecipeImages(
                    recipe_id=recipe.id,
                    filename=stored_filename,
                    caption=title,
                    uploaded_by=current_user.id,
                )
            )

        source_url = imported_recipe.get(
            "source_url",
            "",
        )
        
        type_names = ", ".join(
            recipe_type.name
            for recipe_type in selected_types
        )

        type_details = (
            f" Recipe types: {type_names}."
            if type_names
            else ""
        )
        
        tag_names = ", ".join(
            tag.name
            for tag in selected_tags
        )

        tag_details = (
            f" Tags: {tag_names}."
            if tag_names
            else ""
        )

        record_recipe_history(
            recipe_id=recipe.id,
            action="recipe_imported",
            details=(
                f'Imported "{recipe.title}" from '
                f"{source_url} with "
                f"{len(ingredient_rows)} ingredients "
                f"and {len(step_rows)} steps."
                f"{type_details}"
                f"{tag_details}"
            ),
        )

        db.session.commit()

    except Exception:
        db.session.rollback()

        if (
            imported_file_path is not None
            and imported_file_path.exists()
        ):
            imported_file_path.unlink(
                missing_ok=True
            )

        raise

    delete_import_draft(import_token)

    flash(
        f'"{recipe.title}" was imported.',
        "success",
    )

    return redirect(
        url_for(
            "recipes.detail",
            id=recipe.id,
        )
    )