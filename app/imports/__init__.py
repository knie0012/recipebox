from flask import Blueprint


imports = Blueprint(
    "imports",
    __name__,
)


from app.imports import routes