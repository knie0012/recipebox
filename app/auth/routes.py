from urllib.parse import urljoin, urlparse

from flask import (
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import (
    current_user,
    login_user,
    logout_user,
)

from app.models import Users
from app.auth import auth


def is_safe_redirect_url(target):
    """
    Only allow redirects back to this application.
    """

    if not target:
        return False

    host_url = urlparse(request.host_url)
    redirect_url = urlparse(
        urljoin(request.host_url, target)
    )

    return (
        redirect_url.scheme in {"http", "https"}
        and redirect_url.netloc == host_url.netloc
    )


@auth.route(
    "/recipebox/login",
    methods=["GET", "POST"],
)
def login():
    if current_user.is_authenticated:
        return redirect(
            url_for("main.index")
        )

    if request.method == "POST":
        username = request.form.get(
            "username",
            "",
        ).strip()

        password = request.form.get(
            "password",
            "",
        )

        remember = (
            request.form.get("remember")
            == "yes"
        )

        user = Users.query.filter(
            Users.username == username
        ).first()

        if user is None or not user.check_password(
            password
        ):
            flash(
                "Invalid username or password.",
                "error",
            )

            return render_template(
                "auth/login.html",
                username=username,
            )

        login_user(
            user,
            remember=remember,
        )

        flash(
            f"Welcome, {user.username}.",
            "success",
        )

        next_url = request.args.get("next")

        if is_safe_redirect_url(next_url):
            return redirect(next_url)

        return redirect(
            url_for("main.index")
        )

    return render_template(
        "auth/login.html"
    )


@auth.route(
    "/recipebox/logout",
    methods=["POST"],
)
def logout():
    if current_user.is_authenticated:
        logout_user()
        flash(
            "You have been logged out.",
            "success",
        )

    return redirect(
        url_for("main.index")
    )
