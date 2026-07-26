#!/usr/bin/env python3

from app import create_app, db
from app.models import Tags


app = create_app()


DEFAULT_TAGS = [
"Sweet",
"Savory",
"Spicy",
"Mild",
"Tangy",
"Zesty",
"Smoky",
"Rich",
"Creamy",
"Cheesy",
"Buttery",
"Garlicky",
"Herby",
"Crispy",
"Crunchy",
"Juicy",
"Tender",
"Fluffy",
"Moist",
"Refreshing",
"Comfort Food",
"Hearty",
"Light",
"Fresh",
"Classic",
"Homemade",
"Family Favorite",
"Crowd Pleaser",
"Restaurant Quality",
"Best Ever",
"Popular",
"Favorite",
"Delicious",
"Flavor Packed",
"Irresistible",
"Decadent",
"Satisfying",
"Mouthwatering",
"Golden Brown",
"Perfectly Seasoned",
"Bold Flavor",
"Caramelized",
"Velvety",
"Silky",
"Sticky",
"Flaky",
"Warm",
"Cozy",
"Aromatic",
"Peppery",
"Sweet and Savory",
"Umami",
"Fiery",
"Luscious",
"Finger Licking",
"Addictive",
"Crave Worthy",
"Kitchen Favorite",
"Must Try",
"Baked",
"Roasted",
"Grilled",
"Pan Fried",
"Slow Cooked",
"One Pot",
"Skillet",
"Casserole",
"Rustic",
"Elegant",
"Simple",
"Quick",
"Easy",
"Homestyle",
"Wholesome",
"Indulgent",
"Festive",
"Colorful",
"Seasonal",
"Signature",
"Authentic",
"Traditional",
"Handcrafted",
"Perfect for Sharing"
]


def seed_tags() -> None:
    created_count = 0

    for name in DEFAULT_TAGS:
        tag = Tags.query.filter(
            db.func.lower(Tags.name)
            == name.lower()
        ).first()

        if tag is None:
            tag = Tags(
                name=name,
            )

            db.session.add(tag)
            created_count += 1

    db.session.commit()

    print(
        f"Tags ready. "
        f"Created {created_count} new tag(s)."
    )


if __name__ == "__main__":
    with app.app_context():
        seed_tags()
