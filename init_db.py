#!/usr/bin/env python3

"""
Initialize the RecipeBox database.

Examples:

    Create missing tables without deleting existing data:
        python init_db.py

    Completely wipe and rebuild all tables:
        python init_db.py --reset

    Create an initial user:
        python init_db.py --create-user

    Wipe, rebuild, and create an initial user:
        python init_db.py --reset --create-user
"""

import argparse
import getpass
import sys

from sqlalchemy import inspect
from sqlalchemy.exc import SQLAlchemyError

from app import create_app, db


# Import all models so SQLAlchemy knows about every table.
from app.models import Users  # noqa: F401
import app.models  # noqa: F401

app = create_app()

RESET_CONFIRMATION = "DELETE RECIPEBOX"


def print_tables() -> None:
    """Display the tables currently known to the database."""

    inspector = inspect(db.engine)
    tables = sorted(inspector.get_table_names())

    if not tables:
        print("No tables currently exist.")
        return

    print("Current database tables:")

    for table in tables:
        print(f"  - {table}")


def confirm_reset() -> bool:
    """Require an explicit confirmation before destroying data."""

    print()
    print("WARNING: This will permanently delete every RecipeBox table")
    print("and all recipes, users, ingredients, images, and other data.")
    print()
    print(f'Type "{RESET_CONFIRMATION}" to continue.')

    response = input("> ").strip()

    return response == RESET_CONFIRMATION


def reset_database() -> None:
    """Drop and recreate all SQLAlchemy-managed tables."""

    if not confirm_reset():
        print("Database reset cancelled.")
        sys.exit(1)

    print("Dropping existing tables...")
    db.drop_all()

    print("Creating new tables...")
    db.create_all()

    print("Database reset completed.")


def create_tables() -> None:
    """Create any missing tables without deleting existing data."""

    print("Creating missing tables...")
    db.create_all()
    print("Database tables are ready.")


def prompt_for_username() -> str:
    """Prompt until a valid, unused username is supplied."""

    while True:
        username = input("Username: ").strip()

        if not username:
            print("Username cannot be blank.")
            continue

        existing_user = Users.query.filter_by(
            username=username
        ).first()

        if existing_user is not None:
            print(f'Username "{username}" already exists.')
            continue

        return username


def prompt_for_password() -> str:
    """Prompt for and confirm a password without displaying it."""

    while True:
        password = getpass.getpass("Password: ")

        if len(password) < 8:
            print("Password must contain at least 8 characters.")
            continue

        confirmation = getpass.getpass("Confirm password: ")

        if password != confirmation:
            print("Passwords do not match.")
            continue

        return password


def create_initial_user() -> None:
    """Create the first RecipeBox user."""

    print()
    print("Create initial RecipeBox user")
    print("-----------------------------")

    username = prompt_for_username()
    password = prompt_for_password()

    user = Users(username=username)
    user.set_password(password)

    db.session.add(user)
    db.session.commit()

    print()
    print(f'User "{username}" created successfully.')
    print(f"User ID: {user.id}")

def add_user() -> None:
    """Interactively add a new RecipeBox user."""

    print()
    print("Add New User")
    print("------------")

    username = prompt_for_username()
    password = prompt_for_password()

    user = Users(username=username)
    user.set_password(password)

    db.session.add(user)
    db.session.commit()

    print()
    print(f'User "{username}" created successfully.')
    print(f"User ID: {user.id}")
    
    
def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Initialize the RecipeBox database."
    )

    parser.add_argument(
        "--reset",
        action="store_true",
        help="Drop all tables and rebuild the database schema.",
    )

    parser.add_argument(
        "--create-user",
        action="store_true",
        help="Prompt for and create an initial RecipeBox user.",
    )

    parser.add_argument(
        "--show-tables",
        action="store_true",
        help="Display the tables after initialization.",
    )
    
    parser.add_argument(
        "--add-user",
        action="store_true",
        help="Add a new user",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_arguments()

    try:
        with app.app_context():
            if args.reset:
                reset_database()
            else:
                create_tables()

            if args.create_user:
                create_initial_user()

            if args.add_user:
                add_user()

            if args.show_tables:
                print()
                print_tables()

    except SQLAlchemyError as exc:
        db.session.rollback()

        print()
        print("Database initialization failed:")
        print(exc)

        sys.exit(1)


if __name__ == "__main__":
    main()