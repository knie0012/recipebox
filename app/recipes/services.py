from typing import Optional, Type

from sqlalchemy import func

from app import db
from app.models import (
    Ingredients,
    RecipeIngredients,
    RecipeSection,
)


UNIT_CHOICES = [
    ("each", "each"),
    ("pinch", "pinch"),
    ("dash", "dash"),
    ("teaspoon", "teaspoon"),
    ("tablespoon", "tablespoon"),
    ("cup", "cup"),
    ("pint", "pint"),
    ("quart", "quart"),
    ("gallon", "gallon"),
    ("fluid_ounce", "fluid ounce"),
    ("milliliter", "milliliter"),
    ("liter", "liter"),
    ("ounce", "ounce"),
    ("pound", "pound"),
    ("gram", "gram"),
    ("kilogram", "kilogram"),
    ("clove", "clove"),
    ("can", "can"),
    ("package", "package"),
    ("slice", "slice"),
    ("piece", "piece"),
    ("bunch", "bunch"),
    ("small", "small"),
    ("medium", "medium"),
    ("large", "large"),
]


UNIT_LABELS = dict(UNIT_CHOICES)


def normalize_name(
    value: Optional[str],
) -> str:
    """
    Trim leading/trailing whitespace and collapse repeated spaces.
    """

    return " ".join(
        str(value or "").split()
    ).strip()


def normalize_ingredient_name(
    name: Optional[str],
) -> str:
    """
    Normalize an ingredient name.
    """

    return normalize_name(name)


def find_ingredient_by_name(
    name: str,
) -> Optional[Ingredients]:
    """
    Find an ingredient using a case-insensitive name comparison.
    """

    normalized_name = normalize_ingredient_name(
        name
    )

    if not normalized_name:
        return None

    return (
        Ingredients.query
        .filter(
            func.lower(Ingredients.name)
            == normalized_name.lower()
        )
        .first()
    )


def get_or_create_ingredient(
    name: str,
    category: Optional[str] = None,
) -> tuple[Ingredients, bool]:
    """
    Reuse an existing ingredient or create a new ingredient.

    Returns:
        A tuple containing the ingredient and whether it was created.
    """

    normalized_name = normalize_ingredient_name(
        name
    )

    if not normalized_name:
        raise ValueError(
            "Enter an ingredient name."
        )

    ingredient = find_ingredient_by_name(
        normalized_name
    )

    if ingredient is not None:
        return ingredient, False

    ingredient = Ingredients(
        name=normalized_name,
        category=normalize_name(category) or None,
    )

    db.session.add(ingredient)
    db.session.flush()

    return ingredient, True


def normalize_section_name(
    value: Optional[str],
) -> Optional[str]:
    """
    Normalize a recipe ingredient section name.

    A blank value represents unsectioned ingredients.
    """

    normalized_name = normalize_name(value)

    return normalized_name or None


def get_or_create_recipe_section(
    recipe_id: int,
    section_name: Optional[str],
) -> tuple[Optional[RecipeSection], bool]:
    """
    Reuse an existing recipe section or create a new one.

    Section names are matched case-insensitively within the recipe.

    A blank section name returns None, representing unsectioned
    ingredients.

    Returns:
        A tuple containing the section and whether it was created.
    """

    normalized_name = normalize_section_name(
        section_name
    )

    if normalized_name is None:
        return None, False

    existing_section = (
        RecipeSection.query
        .filter(
            RecipeSection.recipe_id == recipe_id,
            func.lower(RecipeSection.name)
            == normalized_name.lower(),
        )
        .first()
    )

    if existing_section is not None:
        return existing_section, False

    highest_position = (
        db.session.query(
            func.max(RecipeSection.position)
        )
        .filter(
            RecipeSection.recipe_id == recipe_id
        )
        .scalar()
        or 0
    )

    section = RecipeSection(
        recipe_id=recipe_id,
        name=normalized_name,
        position=highest_position + 1,
    )

    db.session.add(section)
    db.session.flush()

    return section, True


def get_next_ingredient_position(
    recipe_id: int,
) -> int:
    """
    Return the next global ingredient position for a recipe.

    Retained temporarily for compatibility with older code.
    New section-aware code should use
    get_next_section_ingredient_position().
    """

    highest_position = (
        db.session.query(
            func.max(RecipeIngredients.position)
        )
        .filter(
            RecipeIngredients.recipe_id == recipe_id
        )
        .scalar()
    )

    return (highest_position or 0) + 1


def get_next_section_ingredient_position(
    recipe_id: int,
    section_id: Optional[int],
) -> int:
    """
    Return the next ingredient position within one section.

    A NULL section_id represents unsectioned ingredients.
    """

    query = (
        db.session.query(
            func.max(RecipeIngredients.position)
        )
        .filter(
            RecipeIngredients.recipe_id == recipe_id
        )
    )

    if section_id is None:
        query = query.filter(
            RecipeIngredients.section_id.is_(None)
        )
    else:
        query = query.filter(
            RecipeIngredients.section_id
            == section_id
        )

    highest_position = query.scalar() or 0

    return highest_position + 1


def compact_section_ingredient_positions(
    recipe_id: int,
    section_id: Optional[int],
) -> None:
    """
    Renumber ingredients sequentially within one section.
    """

    query = RecipeIngredients.query.filter(
        RecipeIngredients.recipe_id
        == recipe_id
    )

    if section_id is None:
        query = query.filter(
            RecipeIngredients.section_id.is_(None)
        )
    else:
        query = query.filter(
            RecipeIngredients.section_id
            == section_id
        )

    ingredients = (
        query
        .order_by(
            RecipeIngredients.position,
            RecipeIngredients.id,
        )
        .all()
    )

    for position, ingredient in enumerate(
        ingredients,
        start=1,
    ):
        ingredient.position = position


def parse_optional_nonnegative_integer(
    value: Optional[str],
    field_name: str,
) -> Optional[int]:
    """
    Convert an optional form value to a nonnegative integer.

    Empty values become None.
    """

    value = str(value or "").strip()

    if not value:
        return None

    try:
        number = int(value)

    except ValueError as exc:
        raise ValueError(
            f"{field_name} must be a whole number."
        ) from exc

    if number < 0:
        raise ValueError(
            f"{field_name} cannot be negative."
        )

    return number


def get_next_position(
    model: Type,
    recipe_id: int,
) -> int:
    """
    Return the next display position for an ordered recipe child.

    This remains appropriate for recipe steps and other globally
    ordered child records.
    """

    highest_position = (
        db.session.query(
            func.max(model.position)
        )
        .filter(
            model.recipe_id == recipe_id
        )
        .scalar()
    )

    return (highest_position or 0) + 1


def compact_positions(
    model: Type,
    recipe_id: int,
) -> None:
    """
    Renumber globally ordered recipe child records sequentially.

    Use compact_section_ingredient_positions() for ingredients.
    """

    items = (
        model.query
        .filter_by(
            recipe_id=recipe_id
        )
        .order_by(
            model.position,
            model.id,
        )
        .all()
    )

    for position, item in enumerate(
        items,
        start=1,
    ):
        item.position = position


def move_ordered_item(
    model: Type,
    item,
    direction: str,
) -> bool:
    """
    Swap a globally ordered item with the item above or below it.

    This remains appropriate for recipe steps. Ingredient movement
    must additionally be constrained by section_id.
    """

    query = model.query.filter_by(
        recipe_id=item.recipe_id
    )

    if direction == "up":
        neighbor = (
            query
            .filter(
                model.position < item.position
            )
            .order_by(
                model.position.desc(),
                model.id.desc(),
            )
            .first()
        )

    elif direction == "down":
        neighbor = (
            query
            .filter(
                model.position > item.position
            )
            .order_by(
                model.position.asc(),
                model.id.asc(),
            )
            .first()
        )

    else:
        raise ValueError(
            "Invalid move direction."
        )

    if neighbor is None:
        return False

    item.position, neighbor.position = (
        neighbor.position,
        item.position,
    )

    return True