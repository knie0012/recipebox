from flask import (
    flash,
    redirect,
    render_template,
    request,
    url_for,
)

from app import db
from app.models import RecipeSteps, Recipes
from app.recipes import recipes
from app.recipes.services import (
    compact_positions,
    get_next_position,
    move_ordered_item,
    parse_optional_nonnegative_integer,
)

from flask_login import login_required
from app.recipes.history import record_recipe_history


@recipes.route(
    "/recipebox/<int:recipe_id>/step/new",
    methods=["GET", "POST"],
)
@login_required
def new_step(recipe_id):
    recipe = Recipes.query.get_or_404(recipe_id)

    if request.method == "POST":
        instruction = request.form.get(
            "instruction",
            "",
        ).strip()

        if not instruction:
            flash(
                "The instruction cannot be empty.",
                "error",
            )

            return render_template(
                "recipes/step_form.html",
                recipe=recipe,
                step=None,
            )

        try:
            timer_minutes = (
                parse_optional_nonnegative_integer(
                    request.form.get("timer_minutes"),
                    "Timer",
                )
            )
        except ValueError as error:
            flash(str(error), "error")

            return render_template(
                "recipes/step_form.html",
                recipe=recipe,
                step=None,
            )

        step = RecipeSteps(
            recipe_id=recipe.id,
            position=get_next_position(
                RecipeSteps,
                recipe.id,
            ),
            instruction=instruction,
            timer_minutes=timer_minutes,
        )

        db.session.add(step)

        instruction_summary = step.instruction.strip()

        if len(instruction_summary) > 120:
            instruction_summary = (
                instruction_summary[:117] + "..."
            )

        record_recipe_history(
            recipe_id=recipe.id,
            action="step_added",
            details=(
                f"Added step {step.position}: "
                f"{instruction_summary}"
            ),
        )

        db.session.commit()

        flash(
            "The recipe step was added.",
            "success",
        )

        return redirect(
            url_for(
                "recipes.detail",
                id=recipe.id,
            )
        )

    return render_template(
        "recipes/step_form.html",
        recipe=recipe,
        step=None,
    )


@recipes.route(
    "/recipebox/step/<int:id>/edit",
    methods=["GET", "POST"],
)
@login_required
def edit_step(id):
    step = RecipeSteps.query.get_or_404(id)

    if request.method == "POST":
        instruction = request.form.get(
            "instruction",
            "",
        ).strip()

        if not instruction:
            flash(
                "The instruction cannot be empty.",
                "error",
            )

            return render_template(
                "recipes/step_form.html",
                recipe=step.recipe,
                step=step,
            )

        try:
            timer_minutes = (
                parse_optional_nonnegative_integer(
                    request.form.get("timer_minutes"),
                    "Timer",
                )
            )
        except ValueError as error:
            flash(str(error), "error")

            return render_template(
                "recipes/step_form.html",
                recipe=step.recipe,
                step=step,
            )

        old_instruction = step.instruction
        old_timer_minutes = step.timer_minutes

        changes = []

        if old_instruction != instruction:
            changes.append("Instruction updated")

        if old_timer_minutes != timer_minutes:
            old_timer = (
                old_timer_minutes
                if old_timer_minutes is not None
                else "not set"
            )

            new_timer = (
                timer_minutes
                if timer_minutes is not None
                else "not set"
            )

            changes.append(
                f"Timer changed from {old_timer} to {new_timer}"
            )

        step.instruction = instruction
        step.timer_minutes = timer_minutes

        if changes:
            record_recipe_history(
                recipe_id=step.recipe_id,
                action="step_updated",
                details=(
                    f"Updated step {step.position}: "
                    + "; ".join(changes)
                ),
            )

            db.session.commit()

            flash(
                "The recipe step was updated.",
                "success",
            )

        else:
            flash(
                "No step changes were detected.",
                "success",
            )

        flash("The recipe step was updated.", "success")

        return redirect(
            url_for(
                "recipes.detail",
                id=step.recipe_id,
            )
        )

    return render_template(
        "recipes/step_form.html",
        recipe=step.recipe,
        step=step,
    )


@recipes.route(
    "/recipebox/step/<int:id>/delete",
    methods=["POST"],
)
@login_required
def delete_step(id):
    step = RecipeSteps.query.get_or_404(id)

    recipe_id = step.recipe_id
    position = step.position
    instruction = step.instruction.strip()

    if len(instruction) > 120:
        instruction = instruction[:117] + "..."

    db.session.delete(step)
    db.session.flush()

    compact_positions(
        RecipeSteps,
        recipe_id,
    )

    record_recipe_history(
        recipe_id=recipe_id,
        action="step_deleted",
        details=(
            f"Deleted step {position}: "
            f"{instruction}"
        ),
    )

    db.session.commit()

    flash(
        "The recipe step was deleted.",
        "success",
    )

    return redirect(
        url_for(
            "recipes.detail",
            id=recipe_id,
        )
    )


@recipes.route(
    "/recipebox/step/<int:id>/move/<string:direction>",
    methods=["POST"],
)
@login_required
def move_step(id, direction):
    step = RecipeSteps.query.get_or_404(id)

    try:
        moved = move_ordered_item(
            RecipeSteps,
            step,
            direction,
        )
    except ValueError:
        flash("Invalid move direction.", "error")

        return redirect(
            url_for(
                "recipes.detail",
                id=step.recipe_id,
            )
        )

    if moved:
        db.session.commit()

    return redirect(
        url_for(
            "recipes.detail",
            id=step.recipe_id,
        )
    )
