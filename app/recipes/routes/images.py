from pathlib import Path
from uuid import uuid4

from flask import (
    current_app,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from werkzeug.utils import secure_filename

from app import db
from app.models import RecipeImages, Recipes
from app.recipes import recipes

from flask_login import login_required, current_user
from app.recipes.history import record_recipe_history

ALLOWED_IMAGE_EXTENSIONS = {
    "jpg",
    "jpeg",
    "png",
    "webp",
}

def format_caption_change(
    old_caption,
    new_caption,
):
    """
    Create a readable photo-caption history description.
    """

    if not old_caption and new_caption:
        return f'Added photo caption "{new_caption}".'

    if old_caption and not new_caption:
        return f'Removed photo caption "{old_caption}".'

    return (
        f'Changed photo caption from '
        f'"{old_caption}" to "{new_caption}".'
    )
    
    

def get_image_extension(filename):
    """
    Return a validated lowercase file extension.
    """

    if "." not in filename:
        return None

    extension = filename.rsplit(".", 1)[1].lower()

    if extension not in ALLOWED_IMAGE_EXTENSIONS:
        return None

    return extension


@recipes.route(
    "/recipebox/<int:recipe_id>/image/new",
    methods=["POST"],
)
@login_required
def add_image(recipe_id):
    recipe = Recipes.query.get_or_404(recipe_id)
    uploaded_file = request.files.get("image")

    if uploaded_file is None or not uploaded_file.filename:
        flash("Select an image to upload.", "error")

        return redirect(
            url_for(
                "recipes.detail",
                id=recipe.id,
            )
        )

    extension = get_image_extension(
        uploaded_file.filename
    )

    if extension is None:
        flash(
            "Images must be JPG, JPEG, PNG, or WebP.",
            "error",
        )

        return redirect(
            url_for(
                "recipes.detail",
                id=recipe.id,
            )
        )

    original_name = secure_filename(
        uploaded_file.filename
    )

    stored_filename = (
        f"recipe_{recipe.id}_{uuid4().hex}.{extension}"
    )

    upload_directory = Path(
        current_app.static_folder
    ) / "uploads" / "recipes"

    upload_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    file_path = upload_directory / stored_filename

    uploaded_file.save(file_path)

    caption = (
        request.form.get("caption", "").strip()
        or None
    )

    image = RecipeImages(
        recipe_id=recipe.id,
        filename=stored_filename,
        caption=caption,
        uploaded_by=current_user.id,
    )

    try:
        db.session.add(image)

        record_recipe_history(
            recipe_id=recipe.id,
            action="photo_uploaded",
            details=(
                f'Uploaded photo with caption "{caption}".'
                if caption
                else "Uploaded a recipe photo."
            ),
        )

        db.session.commit()

    except Exception:
        db.session.rollback()

        if file_path.exists():
            file_path.unlink()

        current_app.logger.exception(
            "Unable to save recipe image record."
        )

        flash(
            "The image could not be saved.",
            "error",
        )

        return redirect(
            url_for(
                "recipes.detail",
                id=recipe.id,
            )
        )

    flash(
        f"Photo added to {recipe.title}.",
        "success",
    )

    return redirect(
        url_for(
            "recipes.detail",
            id=recipe.id,
        )
    )


@recipes.route(
    "/recipebox/image/<int:id>/delete",
    methods=["POST"],
)
@login_required
def delete_image(id):
    image = RecipeImages.query.get_or_404(id)

    recipe_id = image.recipe_id
    caption = image.caption
    filename = image.filename

    file_path = (
        Path(current_app.static_folder)
        / "uploads"
        / "recipes"
        / filename
    )

    db.session.delete(image)

    record_recipe_history(
        recipe_id=recipe_id,
        action="photo_deleted",
        details=(
            f'Deleted photo with caption "{caption}".'
            if caption
            else "Deleted a recipe photo."
        ),
    )

    db.session.commit()

    try:
        file_path.unlink(missing_ok=True)

    except OSError:
        current_app.logger.exception(
            "Unable to remove recipe image file: %s",
            file_path,
        )

    flash(
        "The recipe photo was deleted.",
        "success",
    )

    return redirect(
        url_for(
            "recipes.detail",
            id=recipe_id,
        )
    )

@recipes.route(
    "/recipebox/image/<int:id>/edit",
    methods=["GET", "POST"],
)
@login_required
def edit_image(id):
    image = RecipeImages.query.get_or_404(id)

    if request.method == "POST":
        old_caption = image.caption

        new_caption = (
            request.form.get("caption", "").strip()
            or None
        )

        if old_caption == new_caption:
            flash(
                "No caption changes were detected.",
                "success",
            )

            return redirect(
                url_for(
                    "recipes.detail",
                    id=image.recipe_id,
                )
            )

        image.caption = new_caption

        record_recipe_history(
            recipe_id=image.recipe_id,
            action="photo_caption_updated",
            details=format_caption_change(
                old_caption,
                new_caption,
            ),
        )

        db.session.commit()

        flash(
            "The photo caption was updated.",
            "success",
        )

        return redirect(
            url_for(
                "recipes.detail",
                id=image.recipe_id,
            )
        )

    return render_template(
        "recipes/image_form.html",
        image=image,
        recipe=image.recipe,
    )