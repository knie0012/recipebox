#!/usr/bin/env python3

from app import create_app, db
from app.models import RecipeTypes


app = create_app()


DEFAULT_RECIPE_TYPES = [
    "Breakfast",
    "Brunch",
    "Lunch",
    "Dinner",
    "Appetizer",
    "Side Dish",
    "Soup",
    "Salad",
    "Dessert",
    "Snack",
    "Bread",
    "Beverage",
    "Sauce",
    "Marinade",
    "Seasoning Mix",
]


def seed_recipe_types() -> None:
    created_count = 0

    for position, name in enumerate(
        DEFAULT_RECIPE_TYPES,
        start=1,
    ):
        recipe_type = RecipeTypes.query.filter(
            db.func.lower(RecipeTypes.name)
            == name.lower()
        ).first()

        if recipe_type is None:
            recipe_type = RecipeTypes(
                name=name,
                position=position,
            )

            db.session.add(recipe_type)
            created_count += 1
        else:
            recipe_type.position = position

    db.session.commit()

    print(
        f"Recipe types ready. "
        f"Created {created_count} new type(s)."
    )


if __name__ == "__main__":
    with app.app_context():
        seed_recipe_types()
