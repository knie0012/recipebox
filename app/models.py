from typing import Optional
import datetime
import decimal

from sqlalchemy import DECIMAL, Date, ForeignKeyConstraint, Index, Integer, String, TIMESTAMP, Text, text
from sqlalchemy.dialects.mysql import TINYINT
from app import db
from sqlalchemy.orm import Mapped, mapped_column, relationship

from flask_login import UserMixin
from werkzeug.security import (
    check_password_hash,
    generate_password_hash,
)


class Ingredients(db.Model):
    __tablename__ = 'ingredients'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[Optional[str]] = mapped_column(String(100))
    category: Mapped[Optional[str]] = mapped_column(String(50))

    recipe_ingredients: Mapped[list['RecipeIngredients']] = relationship('RecipeIngredients', back_populates='ingredient')
    shopping_items_ingredient: Mapped[list['ShoppingItems']] = relationship('ShoppingItems', foreign_keys='[ShoppingItems.ingredient_id]', back_populates='ingredient')

class RecipeHistory(db.Model):
    __tablename__ = "recipe_history"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    recipe_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        db.ForeignKey(
            "recipes.id",
            ondelete="CASCADE",
        ),
        nullable=True,
        index=True,
    )

    user_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        db.ForeignKey(
            "users.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    action: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    details: Mapped[Optional[str]] = mapped_column(
        Text,
    )

    created: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )

    recipe: Mapped[Optional["Recipes"]] = relationship(
        "Recipes",
        back_populates="recipe_history",
    )

    user: Mapped[Optional["Users"]] = relationship(
        "Users",
        foreign_keys=[user_id],
    )

recipe_type_assignments = db.Table(
    "recipe_type_assignments",
    db.Column(
        "recipe_id",
        db.Integer,
        db.ForeignKey(
            "recipes.id",
            ondelete="CASCADE",
        ),
        primary_key=True,
    ),
    db.Column(
        "recipe_type_id",
        db.Integer,
        db.ForeignKey(
            "recipe_types.id",
            ondelete="CASCADE",
        ),
        primary_key=True,
    ),
)


recipe_tag_assignments = db.Table(
    "recipe_tag_assignments",
    db.Column(
        "recipe_id",
        db.Integer,
        db.ForeignKey(
            "recipes.id",
            ondelete="CASCADE",
        ),
        primary_key=True,
    ),
    db.Column(
        "tag_id",
        db.Integer,
        db.ForeignKey(
            "tags.id",
            ondelete="CASCADE",
        ),
        primary_key=True,
    ),
)

class RecipeTypes(db.Model):
    __tablename__ = "recipe_types"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    name: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        unique=True,
    )

    position: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
    )

    created: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )

    recipes: Mapped[list["Recipes"]] = relationship(
        "Recipes",
        secondary=recipe_type_assignments,
        back_populates="types",
    )

class Tags(db.Model):
    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    name: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        unique=True,
    )

    created: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )

    recipes: Mapped[list["Recipes"]] = relationship(
        "Recipes",
        secondary=recipe_tag_assignments,
        back_populates="tags",
    )
    
    
class Recipes(db.Model):
    __tablename__ = "recipes"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    title: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    description: Mapped[Optional[str]] = mapped_column(Text)

    prep_time: Mapped[Optional[int]] = mapped_column(Integer)

    cook_time: Mapped[Optional[int]] = mapped_column(Integer)

    servings: Mapped[Optional[int]] = mapped_column(Integer)

    created_by: Mapped[Optional[int]] = mapped_column(
    Integer,
    db.ForeignKey(
        "users.id",
        ondelete="SET NULL",
    ),
    nullable=True,
)

    creator: Mapped[Optional["Users"]] = relationship(
    "Users",
    foreign_keys=[created_by],
)

    created: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )

    updated: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        onupdate=datetime.datetime.utcnow,
    )

    types: Mapped[list["RecipeTypes"]] = relationship(
        "RecipeTypes",
        secondary=recipe_type_assignments,
        back_populates="recipes",
        order_by="RecipeTypes.position",
    )

    tags: Mapped[list["Tags"]] = relationship(
        "Tags",
        secondary=recipe_tag_assignments,
        back_populates="recipes",
        order_by="Tags.name",
    )

    meal_plan: Mapped[list["MealPlan"]] = relationship(
        "MealPlan",
        back_populates="recipe",
    )

    recipe_images: Mapped[list["RecipeImages"]] = relationship(
        "RecipeImages",
        back_populates="recipe",
        cascade="all, delete-orphan",
        order_by=lambda: (
            RecipeImages.created.asc(),
            RecipeImages.id.asc(),
        ),
    )

    recipe_history: Mapped[list["RecipeHistory"]] = relationship(
    "RecipeHistory",
    back_populates="recipe",
    cascade="all, delete-orphan",
    order_by=lambda: RecipeHistory.created.desc(),
)

    recipe_ingredients: Mapped[list["RecipeIngredients"]] = relationship(
        "RecipeIngredients",
        back_populates="recipe",
        cascade="all, delete-orphan",
        order_by="RecipeIngredients.position",
    )

    recipe_steps: Mapped[list["RecipeSteps"]] = relationship(
        "RecipeSteps",
        back_populates="recipe",
        cascade="all, delete-orphan",
        order_by="RecipeSteps.position",
    )

    recipe_notes: Mapped[list["RecipeNotes"]] = relationship(
        "RecipeNotes",
        back_populates="recipe",
        cascade="all, delete-orphan",
    )
    
    sections: Mapped[list["RecipeSection"]] = relationship(
        "RecipeSection",
        back_populates="recipe",
        cascade="all, delete-orphan",
        order_by="RecipeSection.position",
    )
    
    
class ShoppingLists(db.Model):
    __tablename__ = 'shopping_lists'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    created_by: Mapped[Optional[int]] = mapped_column(Integer)
    created: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP, server_default=text('CURRENT_TIMESTAMP'))

    shopping_items_shopping_list: Mapped[list['ShoppingItems']] = relationship('ShoppingItems', foreign_keys='[ShoppingItems.shopping_list_id]', back_populates='shopping_list')


class Users(UserMixin, db.Model):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    username: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        unique=True,
    )

    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    created: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )

    def set_password(self, password):
        self.password_hash = generate_password_hash(
            password
        )

    def check_password(self, password):
        return check_password_hash(
            self.password_hash,
            password,
        )


class MealPlan(db.Model):
    __tablename__ = 'meal_plan'
    __table_args__ = (
        ForeignKeyConstraint(['recipe_id'], ['recipes.id'], ondelete='CASCADE', name='fk_meal_plan_recipe'),
        Index('fk_meal_plan_recipe', 'recipe_id')
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    recipe_id: Mapped[Optional[int]] = mapped_column(Integer)
    meal_date: Mapped[Optional[datetime.date]] = mapped_column(Date)
    meal_type: Mapped[Optional[str]] = mapped_column(String(50))
    notes: Mapped[Optional[str]] = mapped_column(Text)
    created_by: Mapped[Optional[int]] = mapped_column(Integer)
    created: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP, server_default=text('CURRENT_TIMESTAMP'))

    recipe: Mapped[Optional['Recipes']] = relationship('Recipes', back_populates='meal_plan')


class RecipeImages(db.Model):
    __tablename__ = 'recipe_images'
    __table_args__ = (
        ForeignKeyConstraint(['recipe_id'], ['recipes.id'], ondelete='CASCADE', name='fk_recipe_images_recipe'),
        Index('fk_recipe_images_recipe', 'recipe_id')
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    recipe_id: Mapped[int] = mapped_column(Integer, nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    caption: Mapped[Optional[str]] = mapped_column(String(255))
    uploaded_by: Mapped[Optional[int]] = mapped_column(
        Integer,
        db.ForeignKey(
            "users.id",
            ondelete="SET NULL",
        ),
        nullable=True,
    )

    uploader: Mapped[Optional["Users"]] = relationship(
        "Users",
        foreign_keys=[uploaded_by],
    )

    created: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP, server_default=text('CURRENT_TIMESTAMP'))

    recipe: Mapped['Recipes'] = relationship('Recipes', back_populates='recipe_images')


class RecipeIngredients(db.Model):
    __tablename__ = "recipe_ingredients"
    __table_args__ = (
        ForeignKeyConstraint(
            ["ingredient_id"],
            ["ingredients.id"],
            ondelete="CASCADE",
            name="fk_recipe_ingredients_ingredient",
        ),
        ForeignKeyConstraint(
            ["recipe_id"],
            ["recipes.id"],
            ondelete="CASCADE",
            name="fk_recipe_ingredients_recipe",
        ),
        Index(
            "fk_recipe_ingredients_ingredient",
            "ingredient_id",
        ),
        Index(
            "fk_recipe_ingredients_recipe",
            "recipe_id",
        ),
        Index(
            "ix_recipe_ingredients_position",
            "recipe_id",
            "section_id",
            "position",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    recipe_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    ingredient_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    quantity: Mapped[Optional[str]] = mapped_column(
        String(50)
    )

    unit: Mapped[Optional[str]] = mapped_column(
        String(30)
    )
    
    position: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    ingredient: Mapped["Ingredients"] = relationship(
        "Ingredients",
        back_populates="recipe_ingredients",
    )

    recipe: Mapped["Recipes"] = relationship(
        "Recipes",
        back_populates="recipe_ingredients",
    )
    
    section_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        db.ForeignKey(
            "recipe_sections.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    recipe_section: Mapped[Optional["RecipeSection"]] = relationship(
        "RecipeSection",
        back_populates="ingredients",
    )
    

class RecipeSection(db.Model):
    __tablename__ = "recipe_sections"

    __table_args__ = (
        db.UniqueConstraint(
            "recipe_id",
            "name",
            name="uq_recipe_section_name",
        ),
        Index(
            "ix_recipe_sections_recipe_position",
            "recipe_id",
            "position",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    recipe_id: Mapped[int] = mapped_column(
        Integer,
        db.ForeignKey(
            "recipes.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    position: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
    )

    recipe: Mapped["Recipes"] = relationship(
        "Recipes",
        back_populates="sections",
    )

    ingredients: Mapped[list["RecipeIngredients"]] = relationship(
        "RecipeIngredients",
        back_populates="recipe_section",
        order_by="RecipeIngredients.position",
        passive_deletes=True,
    )
    

class RecipeSteps(db.Model):
    __tablename__ = "recipe_steps"
    __table_args__ = (
        ForeignKeyConstraint(
            ["recipe_id"],
            ["recipes.id"],
            ondelete="CASCADE",
            name="fk_recipe_steps_recipe",
        ),
        Index(
            "ix_recipe_steps_recipe_position",
            "recipe_id",
            "position",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    recipe_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    position: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    instruction: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    timer_minutes: Mapped[Optional[int]] = mapped_column(
        Integer,
    )

    created: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )

    updated: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        onupdate=datetime.datetime.utcnow,
    )

    recipe: Mapped["Recipes"] = relationship(
        "Recipes",
        back_populates="recipe_steps",
    )

class RecipeNotes(db.Model):
    __tablename__ = 'recipe_notes'
    __table_args__ = (
        ForeignKeyConstraint(['recipe_id'], ['recipes.id'], ondelete='CASCADE', name='fk_recipe_notes_recipe'),
        Index('fk_recipe_notes_recipe', 'recipe_id')
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    recipe_id: Mapped[Optional[int]] = mapped_column(Integer)
    user_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        db.ForeignKey(
            "users.id",
            ondelete="SET NULL",
        ),
        nullable=True,
    )

    user: Mapped[Optional["Users"]] = relationship(
        "Users",
        foreign_keys=[user_id],
        )
    note: Mapped[Optional[str]] = mapped_column(Text)
    created: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP, server_default=text('CURRENT_TIMESTAMP'))

    recipe: Mapped[Optional['Recipes']] = relationship('Recipes', back_populates='recipe_notes')


class ShoppingItems(db.Model):
    __tablename__ = 'shopping_items'
    __table_args__ = (
        ForeignKeyConstraint(['ingredient_id'], ['ingredients.id'], ondelete='SET NULL', name='fk_shopping_items_ingredient'),
      #  ForeignKeyConstraint(['ingredient_id'], ['ingredients.id'], ondelete='SET NULL', name='shopping_items_ibfk_2'),
        ForeignKeyConstraint(['shopping_list_id'], ['shopping_lists.id'], ondelete='CASCADE', name='fk_shopping_items_list'),
      #  ForeignKeyConstraint(['shopping_list_id'], ['shopping_lists.id'], ondelete='CASCADE', name='shopping_items_ibfk_1'),
        Index('fk_shopping_items_ingredient', 'ingredient_id'),
        Index('fk_shopping_items_list', 'shopping_list_id')
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    shopping_list_id: Mapped[int] = mapped_column(Integer, nullable=False)
    ingredient_id: Mapped[Optional[int]] = mapped_column(Integer)
    quantity: Mapped[Optional[decimal.Decimal]] = mapped_column(DECIMAL(10, 2))
    unit: Mapped[Optional[str]] = mapped_column(String(50))
    checked: Mapped[Optional[int]] = mapped_column(TINYINT(1), server_default=text("'0'"))

    ingredient: Mapped[Optional['Ingredients']] = relationship('Ingredients', foreign_keys=[ingredient_id], back_populates='shopping_items_ingredient')
    #ingredient_: Mapped[Optional['Ingredients']] = relationship('Ingredients', foreign_keys=[ingredient_id], back_populates='shopping_items_ingredient_')
    shopping_list: Mapped['ShoppingLists'] = relationship('ShoppingLists', foreign_keys=[shopping_list_id], back_populates='shopping_items_shopping_list')
    #shopping_list_: Mapped['ShoppingLists'] = relationship('ShoppingLists', foreign_keys=[shopping_list_id], back_populates='shopping_items_shopping_list_')
