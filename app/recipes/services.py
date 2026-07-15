from typing import Optional, Type

from sqlalchemy import func

from app import db
from app.models import Ingredients, RecipeIngredients

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
]


UNIT_LABELS = dict(UNIT_CHOICES)


def normalize_ingredient_name(name):
    """
    Remove leading, trailing, and repeated whitespace.
    """

    return " ".join(str(name or "").split()).strip()


def find_ingredient_by_name(name):
    """
    Find an existing ingredient using a case-insensitive comparison.
    """

    normalized_name = normalize_ingredient_name(name)

    if not normalized_name:
        return None

    return Ingredients.query.filter(
        db.func.lower(Ingredients.name)
        == normalized_name.lower()
    ).first()


def get_or_create_ingredient(name, category=None):
    """
    Reuse an existing ingredient or create a new ingredient.
    """

    normalized_name = normalize_ingredient_name(name)

    if not normalized_name:
        raise ValueError("Enter an ingredient name.")

    ingredient = find_ingredient_by_name(normalized_name)

    if ingredient is not None:
        return ingredient, False

    ingredient = Ingredients(
        name=normalized_name,
        category=normalize_ingredient_name(category) or None,
    )

    db.session.add(ingredient)
    db.session.flush()

    return ingredient, True


def get_next_ingredient_position(recipe_id):
    """
    Return the next available ingredient position for a recipe.
    """

    highest_position = (
        db.session.query(
            db.func.max(RecipeIngredients.position)
        )
        .filter(
            RecipeIngredients.recipe_id == recipe_id
        )
        .scalar()
    )

    return (highest_position or 0) + 1
    
    
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


def normalize_name(value: Optional[str]) -> str:
    """
    Trim leading/trailing whitespace and collapse repeated spaces.
    """

    return " ".join(str(value or "").split()).strip()


def find_ingredient_by_name(name: str) -> Optional[Ingredients]:
    """
    Find an ingredient using a case-insensitive name comparison.
    """

    return Ingredients.query.filter(
        func.lower(Ingredients.name) == name.lower()
    ).first()


def get_next_position(model: Type, recipe_id: int) -> int:
    """
    Return the next display position for an ordered recipe child record.
    """

    highest_position = (
        db.session.query(func.max(model.position))
        .filter(model.recipe_id == recipe_id)
        .scalar()
    )

    return (highest_position or 0) + 1


def compact_positions(model: Type, recipe_id: int) -> None:
    """
    Renumber records sequentially after a deletion.
    """

    items = (
        model.query
        .filter_by(recipe_id=recipe_id)
        .order_by(model.position, model.id)
        .all()
    )

    for position, item in enumerate(items, start=1):
        item.position = position


def move_ordered_item(model: Type, item, direction: str) -> bool:
    """
    Swap an ordered item with the item directly above or below it.

    Returns True when a move occurred.
    """

    query = model.query.filter_by(recipe_id=item.recipe_id)

    if direction == "up":
        neighbor = (
            query
            .filter(model.position < item.position)
            .order_by(model.position.desc(), model.id.desc())
            .first()
        )

    elif direction == "down":
        neighbor = (
            query
            .filter(model.position > item.position)
            .order_by(model.position.asc(), model.id.asc())
            .first()
        )

    else:
        raise ValueError("Invalid move direction.")

    if neighbor is None:
        return False

    item.position, neighbor.position = (
        neighbor.position,
        item.position,
    )

    return True
