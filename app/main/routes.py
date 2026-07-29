from flask import render_template, request
from sqlalchemy import func, or_
from sqlalchemy.orm import selectinload

from app.main import main
from app.models import (
    Ingredients,
    Recipes,
    RecipeIngredients,
    RecipeMadeEvent,
    RecipeNotes,
    RecipeRating,
    RecipeSection,
    RecipeSteps,
    RecipeTypes,
    Tags,
)


def make_search_snippet(text, term, radius=45):
    """
    Return a short piece of text surrounding the matched term.
    """
    if not text:
        return ""

    text = str(text)
    lower_text = text.lower()
    match_position = lower_text.find(term.lower())

    if match_position == -1:
        return text[: radius * 2]

    start = max(0, match_position - radius)
    end = min(
        len(text),
        match_position + len(term) + radius,
    )

    snippet = text[start:end].strip()

    if start > 0:
        snippet = f"…{snippet}"

    if end < len(text):
        snippet = f"{snippet}…"

    return snippet
    
    
def get_recipe_match_reasons(recipe, search):
    """
    Return a short list explaining why a recipe matched the search.
    """
    if not search:
        return []

    search_terms = [
        term.lower()
        for term in search.split()
        if term.strip()
    ]

    reasons = []

    def contains_term(value, term):
        return value is not None and term in str(value).lower()

    for term in search_terms:
        # Title
        if contains_term(recipe.title, term):
            reasons.append(
                f'Title contains "{term}"'
            )

        # Description
        if contains_term(recipe.description, term):
            reasons.append(
                f'Description contains "{term}"'
            )

        # Ingredients
        for recipe_ingredient in recipe.recipe_ingredients:
            ingredient = recipe_ingredient.ingredient

            if (
                ingredient
                and contains_term(ingredient.name, term)
            ):
                reasons.append(
                    f'Ingredient: {ingredient.name}'
                )

            if contains_term(
                recipe_ingredient.quantity,
                term,
            ):
                reasons.append(
                    "Ingredient quantity: "
                    f"{recipe_ingredient.quantity}"
                )

            if contains_term(
                recipe_ingredient.unit,
                term,
            ):
                reasons.append(
                    "Ingredient unit: "
                    f"{recipe_ingredient.unit}"
                )

        # Steps
        for step in recipe.recipe_steps:
            if contains_term(step.instruction, term):
                reasons.append(
                    "Step: "
                    f"{make_search_snippet(step.instruction, term)}"
                )

        # Notes
        for note in recipe.recipe_notes:
            if contains_term(note.note, term):
                reasons.append(
                    "Note: "
                    f"{make_search_snippet(note.note, term)}"
                )

        # Types
        for recipe_type in recipe.types:
            if contains_term(recipe_type.name, term):
                reasons.append(
                    f"Type: {recipe_type.name}"
                )

        # Tags
        for tag in recipe.tags:
            if contains_term(tag.name, term):
                reasons.append(
                    f"Tag: {tag.name}"
                )

        # Section names
        for section in recipe.sections:
            if contains_term(section.name, term):
                reasons.append(
                    f"Section: {section.name}"
                )

    # Remove duplicates while preserving order
    unique_reasons = list(dict.fromkeys(reasons))

    # Avoid filling the whole card with match explanations
    return unique_reasons[:4]

@main.route("/recipebox")
def index():
    search = request.args.get("q", "").strip()
    sort = request.args.get("sort", "title")
    direction = request.args.get("dir", "asc").lower()

    if direction not in {"asc", "desc"}:
        direction = "asc"

    is_desc = direction == "desc"

    query = (
        Recipes.query
        .options(
            selectinload(Recipes.recipe_images),
            selectinload(Recipes.types),
            selectinload(Recipes.tags),
            selectinload(Recipes.ratings),
            selectinload(Recipes.made_events),
        )
    )

    # Search all useful recipe content
    if search:
        search_terms = search.split()

        for term in search_terms:
            search_pattern = f"%{term}%"

            query = query.filter(
                or_(
                    # Basic recipe information
                    Recipes.title.ilike(search_pattern),
                    Recipes.description.ilike(search_pattern),

                    # Ingredient names
                    Recipes.recipe_ingredients.any(
                        RecipeIngredients.ingredient.has(
                            Ingredients.name.ilike(search_pattern)
                        )
                    ),

                    # Ingredient quantity or unit
                    Recipes.recipe_ingredients.any(
                        RecipeIngredients.quantity.ilike(
                            search_pattern
                        )
                    ),
                    Recipes.recipe_ingredients.any(
                        RecipeIngredients.unit.ilike(
                            search_pattern
                        )
                    ),

                    # Recipe instructions
                    Recipes.recipe_steps.any(
                        RecipeSteps.instruction.ilike(
                            search_pattern
                        )
                    ),

                    # Notes
                    Recipes.recipe_notes.any(
                        RecipeNotes.note.ilike(
                            search_pattern
                        )
                    ),

                    # Recipe types
                    Recipes.types.any(
                        RecipeTypes.name.ilike(
                            search_pattern
                        )
                    ),

                    # Tags
                    Recipes.tags.any(
                        Tags.name.ilike(
                            search_pattern
                        )
                    ),

                    # Section names
                    Recipes.sections.any(
                        RecipeSection.name.ilike(
                            search_pattern
                        )
                    ),
                )
            )

    # Alphabetical
    if sort == "title":
        title_order = (
            Recipes.title.desc()
            if is_desc
            else Recipes.title.asc()
        )

        query = query.order_by(title_order)

    # Recently added
    elif sort == "recent":
        created_order = (
            Recipes.created.desc()
            if is_desc
            else Recipes.created.asc()
        )

        query = query.order_by(
            created_order,
            Recipes.title.asc(),
        )

    # Last made
    elif sort == "last_made":
        last_made = (
            RecipeMadeEvent.query
            .with_entities(
                RecipeMadeEvent.recipe_id,
                func.max(
                    RecipeMadeEvent.made_at
                ).label("last_made_at"),
            )
            .group_by(
                RecipeMadeEvent.recipe_id
            )
            .subquery()
        )

        last_made_order = (
            last_made.c.last_made_at.desc()
            if is_desc
            else last_made.c.last_made_at.asc()
        )

        query = (
            query
            .outerjoin(
                last_made,
                Recipes.id == last_made.c.recipe_id,
            )
            .order_by(
                last_made_order,
                Recipes.title.asc(),
            )
        )

    # Most made
    elif sort == "most_made":
        made_count = (
            RecipeMadeEvent.query
            .with_entities(
                RecipeMadeEvent.recipe_id,
                func.count(
                    RecipeMadeEvent.id
                ).label("made_count"),
            )
            .group_by(
                RecipeMadeEvent.recipe_id
            )
            .subquery()
        )

        made_count_order = (
            made_count.c.made_count.desc()
            if is_desc
            else made_count.c.made_count.asc()
        )

        query = (
            query
            .outerjoin(
                made_count,
                Recipes.id == made_count.c.recipe_id,
            )
            .order_by(
                made_count_order,
                Recipes.title.asc(),
            )
        )

    # Highest average rating
    elif sort == "rating":
        rating_summary = (
            RecipeRating.query
            .with_entities(
                RecipeRating.recipe_id,
                func.avg(
                    RecipeRating.rating
                ).label("average_rating"),
            )
            .group_by(
                RecipeRating.recipe_id
            )
            .subquery()
        )

        rating_order = (
            rating_summary.c.average_rating.desc()
            if is_desc
            else rating_summary.c.average_rating.asc()
        )

        query = (
            query
            .outerjoin(
                rating_summary,
                Recipes.id == rating_summary.c.recipe_id,
            )
            .order_by(
                rating_order,
                Recipes.title.asc(),
            )
        )

    # Protect against invalid sort values
    else:
        sort = "title"
        direction = "asc"

        query = query.order_by(
            Recipes.title.asc()
        )

    recipes = query.all()
    
    match_reasons = {}

    if search:
        match_reasons = {
            recipe.id: get_recipe_match_reasons(
                recipe,
                search,
            )
            for recipe in recipes
        }

    return render_template(
        "index.html",
        recipes=recipes,
        search=search,
        sort=sort,
        direction=direction,
        match_reasons=match_reasons,
    )