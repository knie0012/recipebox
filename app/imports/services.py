import ipaddress
import json
import re
import socket
from typing import Any
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from playwright.sync_api import (
    Error as PlaywrightError,
    TimeoutError as PlaywrightTimeoutError,
    sync_playwright,
)
from recipe_scrapers import scrape_html

import datetime
import decimal
from pathlib import Path
from uuid import uuid4

from flask import current_app


class RecipeImportError(Exception):
    """Raised when a recipe cannot be safely imported."""


MAX_HTML_BYTES = 5 * 1024 * 1024

REQUEST_TIMEOUT = (
    5,
    15,
)

MAX_REDIRECTS = 5

PLAYWRIGHT_TIMEOUT_MS = 25_000

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) "
    "AppleWebKit/537.36 "
    "(KHTML, like Gecko) "
    "Chrome/149.0 Safari/537.36 "
    "RecipeBox/1.0"
)


# -------------------------------------------------------------------
# URL and network validation
# -------------------------------------------------------------------

def validate_public_url(url: str) -> None:
    """
    Confirm that a URL uses HTTP/HTTPS and resolves only to
    publicly routable IP addresses.
    """

    parsed = urlparse(url)

    if parsed.scheme not in {"http", "https"}:
        raise RecipeImportError(
            "Only HTTP and HTTPS recipe URLs are supported."
        )

    if not parsed.hostname:
        raise RecipeImportError(
            "Enter a complete recipe URL."
        )

    try:
        address_info = socket.getaddrinfo(
            parsed.hostname,
            parsed.port or (
                443 if parsed.scheme == "https" else 80
            ),
            type=socket.SOCK_STREAM,
        )

    except socket.gaierror as error:
        raise RecipeImportError(
            "The recipe website could not be found."
        ) from error

    if not address_info:
        raise RecipeImportError(
            "The recipe website did not resolve to an address."
        )

    for address in address_info:
        ip_text = address[4][0]

        try:
            ip_address = ipaddress.ip_address(ip_text)

        except ValueError as error:
            raise RecipeImportError(
                "The recipe website resolved to an invalid address."
            ) from error

        if (
            ip_address.is_private
            or ip_address.is_loopback
            or ip_address.is_link_local
            or ip_address.is_multicast
            or ip_address.is_reserved
            or ip_address.is_unspecified
        ):
            raise RecipeImportError(
                "That URL points to a private or unsupported address."
            )


def is_public_request_url(url: str) -> bool:
    """
    Return False when a browser request points to an unsafe URL.
    Non-network URLs such as data: and blob: are allowed.
    """

    parsed = urlparse(url)

    if parsed.scheme in {"data", "blob", "about"}:
        return True

    if parsed.scheme not in {"http", "https"}:
        return False

    try:
        validate_public_url(url)
    except RecipeImportError:
        return False

    return True


# -------------------------------------------------------------------
# HTTP fetching
# -------------------------------------------------------------------

def read_limited_html_response(
    response: requests.Response,
) -> str:
    """
    Read an HTML response while enforcing the configured size limit.
    """

    content_type = response.headers.get(
        "Content-Type",
        "",
    ).lower()

    if (
        "text/html" not in content_type
        and "application/xhtml+xml" not in content_type
    ):
        raise RecipeImportError(
            "The URL did not return an HTML webpage."
        )

    content_length = response.headers.get(
        "Content-Length"
    )

    if content_length:
        try:
            if int(content_length) > MAX_HTML_BYTES:
                raise RecipeImportError(
                    "The recipe webpage is too large to import."
                )
        except ValueError:
            pass

    chunks: list[bytes] = []
    downloaded_bytes = 0

    for chunk in response.iter_content(
        chunk_size=64 * 1024
    ):
        if not chunk:
            continue

        downloaded_bytes += len(chunk)

        if downloaded_bytes > MAX_HTML_BYTES:
            raise RecipeImportError(
                "The recipe webpage is too large to import."
            )

        chunks.append(chunk)

    encoding = (
        response.encoding
        or response.apparent_encoding
        or "utf-8"
    )

    return b"".join(chunks).decode(
        encoding,
        errors="replace",
    )


def fetch_recipe_html(
    url: str,
) -> tuple[str, str]:
    """
    Fetch webpage HTML through requests.

    Redirects are handled manually so every redirect destination
    can be validated before it is requested.
    """

    current_url = url

    headers = {
        "User-Agent": USER_AGENT,
        "Accept": (
            "text/html,"
            "application/xhtml+xml,"
            "application/xml;q=0.9,"
            "*/*;q=0.8"
        ),
        "Accept-Language": "en-US,en;q=0.8",
    }

    with requests.Session() as session:
        for _ in range(MAX_REDIRECTS + 1):
            validate_public_url(current_url)

            try:
                response = session.get(
                    current_url,
                    headers=headers,
                    timeout=REQUEST_TIMEOUT,
                    stream=True,
                    allow_redirects=False,
                )

            except requests.RequestException as error:
                raise RecipeImportError(
                    "The recipe website could not be reached."
                ) from error

            try:
                if response.is_redirect or response.is_permanent_redirect:
                    location = response.headers.get("Location")

                    if not location:
                        raise RecipeImportError(
                            "The recipe website returned an invalid redirect."
                        )

                    current_url = urljoin(
                        current_url,
                        location,
                    )

                    continue

                if response.status_code == 403:
                    raise RecipeImportError(
                        "The recipe website blocked the normal importer."
                    )

                if response.status_code == 429:
                    raise RecipeImportError(
                        "The recipe website temporarily rate-limited "
                        "the normal importer."
                    )

                response.raise_for_status()

                html = read_limited_html_response(
                    response
                )

                return html, current_url

            except requests.HTTPError as error:
                raise RecipeImportError(
                    f"The recipe website returned HTTP "
                    f"{response.status_code}."
                ) from error

            finally:
                response.close()

    raise RecipeImportError(
        "The recipe website redirected too many times."
    )


# -------------------------------------------------------------------
# Playwright rendering
# -------------------------------------------------------------------

def fetch_recipe_html_with_playwright(
    url: str,
) -> tuple[str, str]:
    """
    Render a recipe page with Chromium and return the resulting HTML.
    """

    validate_public_url(url)

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                headless=True,
            )

            context = browser.new_context(
                user_agent=USER_AGENT,
                locale="en-US",
                viewport={
                    "width": 1280,
                    "height": 900,
                },
                java_script_enabled=True,
            )

            page = context.new_page()

            def validate_browser_request(route) -> None:
                request_url = route.request.url

                if is_public_request_url(request_url):
                    route.continue_()
                else:
                    route.abort()

            page.route(
                "**/*",
                validate_browser_request,
            )

            response = page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=PLAYWRIGHT_TIMEOUT_MS,
            )

            if response is not None:
                status = response.status

                if status >= 400:
                    raise RecipeImportError(
                        f"The rendered recipe webpage returned "
                        f"HTTP {status}."
                    )

            # Some sites insert JSON-LD shortly after the initial DOM
            # is ready. A short bounded wait gives that script time
            # to execute without waiting indefinitely.
            try:
                page.wait_for_load_state(
                    "load",
                    timeout=8_000,
                )
            except PlaywrightTimeoutError:
                pass

            page.wait_for_timeout(2_000)

            final_url = page.url
            validate_public_url(final_url)

            html = page.content()

            browser.close()

    except RecipeImportError:
        raise

    except PlaywrightTimeoutError as error:
        raise RecipeImportError(
            "The recipe webpage took too long to render."
        ) from error

    except PlaywrightError as error:
        raise RecipeImportError(
            "The browser importer could not load that webpage."
        ) from error

    if len(html.encode("utf-8")) > MAX_HTML_BYTES:
        raise RecipeImportError(
            "The rendered recipe webpage is too large to import."
        )

    return html, final_url


# -------------------------------------------------------------------
# General value normalization
# -------------------------------------------------------------------

def clean_text(value: Any) -> str:
    """
    Normalize a value into readable single-spaced text.
    """

    if value is None:
        return ""

    if isinstance(value, list):
        value = " ".join(
            str(item)
            for item in value
            if item is not None
        )

    text = BeautifulSoup(
        str(value),
        "html.parser",
    ).get_text(" ", strip=True)

    return " ".join(text.split())


def parse_iso_duration_minutes(
    value: Any,
) -> int | None:
    """
    Convert common ISO-8601 recipe durations such as PT1H30M
    into total minutes.
    """

    if value is None:
        return None

    if isinstance(value, (int, float)):
        return int(value)

    text = str(value).strip().upper()

    if not text:
        return None

    if text.isdigit():
        return int(text)

    match = re.fullmatch(
        r"P"
        r"(?:(?P<days>\d+)D)?"
        r"(?:T"
        r"(?:(?P<hours>\d+)H)?"
        r"(?:(?P<minutes>\d+)M)?"
        r"(?:(?P<seconds>\d+)S)?"
        r")?",
        text,
    )

    if not match:
        return None

    days = int(match.group("days") or 0)
    hours = int(match.group("hours") or 0)
    minutes = int(match.group("minutes") or 0)
    seconds = int(match.group("seconds") or 0)

    total_minutes = (
        days * 24 * 60
        + hours * 60
        + minutes
    )

    if seconds >= 30:
        total_minutes += 1

    return total_minutes


def normalize_yield(value: Any) -> str:
    """
    Normalize schema.org recipeYield into display text.
    """

    if value is None:
        return ""

    if isinstance(value, list):
        return clean_text(
            next(
                (
                    item
                    for item in value
                    if clean_text(item)
                ),
                "",
            )
        )

    return clean_text(value)


def normalize_image_url(
    value: Any,
) -> str:
    """
    Extract one usable image URL from common JSON-LD shapes.
    """

    if not value:
        return ""

    if isinstance(value, str):
        return value.strip()

    if isinstance(value, list):
        for item in value:
            image_url = normalize_image_url(item)

            if image_url:
                return image_url

        return ""

    if isinstance(value, dict):
        for key in (
            "url",
            "contentUrl",
            "thumbnailUrl",
        ):
            image_url = normalize_image_url(
                value.get(key)
            )

            if image_url:
                return image_url

    return ""


# -------------------------------------------------------------------
# JSON-LD discovery
# -------------------------------------------------------------------

def object_is_recipe(value: Any) -> bool:
    """
    Return True when a JSON-LD object identifies itself as Recipe.
    """

    if not isinstance(value, dict):
        return False

    object_type = value.get("@type")

    if isinstance(object_type, str):
        return object_type.lower() == "recipe"

    if isinstance(object_type, list):
        return any(
            str(item).lower() == "recipe"
            for item in object_type
        )

    return False


def recursively_find_recipe(
    value: Any,
) -> dict[str, Any] | None:
    """
    Search nested JSON-LD structures for a Recipe object.
    """

    if isinstance(value, dict):
        if object_is_recipe(value):
            return value

        graph = value.get("@graph")

        if graph is not None:
            recipe = recursively_find_recipe(graph)

            if recipe is not None:
                return recipe

        for nested_value in value.values():
            if isinstance(
                nested_value,
                (dict, list),
            ):
                recipe = recursively_find_recipe(
                    nested_value
                )

                if recipe is not None:
                    return recipe

    elif isinstance(value, list):
        for item in value:
            recipe = recursively_find_recipe(item)

            if recipe is not None:
                return recipe

    return None


def load_json_ld_script(
    script_text: str,
) -> Any | None:
    """
    Parse a JSON-LD script while handling a few common wrappers.
    """

    text = script_text.strip()

    if not text:
        return None

    text = re.sub(
        r"^\s*<!--",
        "",
        text,
    )

    text = re.sub(
        r"-->\s*$",
        "",
        text,
    )

    text = text.strip().rstrip(";")

    try:
        return json.loads(text)

    except json.JSONDecodeError:
        return None


# -------------------------------------------------------------------
# JSON-LD instruction extraction
# -------------------------------------------------------------------

def extract_instruction_texts(
    value: Any,
) -> list[str]:
    """
    Recursively flatten schema.org HowToStep and HowToSection data.
    """

    steps: list[str] = []

    if value is None:
        return steps

    if isinstance(value, str):
        text = clean_text(value)

        if text:
            steps.append(text)

        return steps

    if isinstance(value, list):
        for item in value:
            steps.extend(
                extract_instruction_texts(item)
            )

        return steps

    if not isinstance(value, dict):
        return steps

    object_type = value.get("@type")

    if isinstance(object_type, list):
        object_types = {
            str(item).lower()
            for item in object_type
        }
    elif object_type:
        object_types = {
            str(object_type).lower()
        }
    else:
        object_types = set()

    if (
        "howtosection" in object_types
        or "itemlist" in object_types
    ):
        nested_items = (
            value.get("itemListElement")
            or value.get("steps")
        )

        steps.extend(
            extract_instruction_texts(
                nested_items
            )
        )

        return steps

    instruction_text = (
        value.get("text")
        or value.get("description")
        or value.get("name")
    )

    if instruction_text:
        text = clean_text(instruction_text)

        if text:
            steps.append(text)

    nested_items = value.get("itemListElement")

    if nested_items:
        steps.extend(
            extract_instruction_texts(
                nested_items
            )
        )

    return steps

def extract_ingredient_sections(
    ingredients_raw: list[Any],
) -> list[dict[str, str]]:
    """
    Preserve simple ingredient section headings when a recipe
    provides them inline.
    """

    ingredients = []
    current_section = ""

    for item in ingredients_raw:
        text = clean_text(item)

        if not text:
            continue

        # Common recipe format:
        # "For the crust:"
        # "Filling:"
        # "Sauce:"
        if (
            len(text) < 80
            and text.endswith(":")
        ):
            current_section = text.rstrip(":")
            continue

        ingredients.append(
            {
                "original_text": text,
                "section": current_section,
            }
        )

    return ingredients
    
    
def extract_json_ld_recipe(
    html: str,
    source_url: str,
) -> dict[str, Any] | None:
    """
    Extract a recipe directly from JSON-LD embedded in HTML.
    """

    soup = BeautifulSoup(
        html,
        "html.parser",
    )

    recipe_object = None

    for script in soup.find_all(
        "script",
        attrs={"type": re.compile(
            r"application/ld\+json",
            re.I,
        )},
    ):
        script_text = script.string or script.get_text()

        parsed_json = load_json_ld_script(
            script_text
        )

        if parsed_json is None:
            continue

        recipe_object = recursively_find_recipe(
            parsed_json
        )
        if recipe_object is not None:
            print(
                json.dumps(
                    recipe_object.get(
                        "recipeIngredient"
                    ),
                    indent=2,
                )
            )

        if recipe_object is not None:
            break

    if recipe_object is None:
        return None

    title = clean_text(
        recipe_object.get("name")
        or recipe_object.get("headline")
    )

    ingredients_raw = (
        recipe_object.get("recipeIngredient")
        or recipe_object.get("ingredients")
        or []
    )

    if isinstance(ingredients_raw, str):
        ingredients_raw = [
            line
            for line in ingredients_raw.splitlines()
            if line.strip()
        ]

    ingredients = extract_ingredient_sections(
        ingredients_raw
)

    instructions = extract_instruction_texts(
        recipe_object.get(
            "recipeInstructions"
        )
    )

    if not title or not ingredients or not instructions:
        return None

    return {
        "source_url": source_url,
        "extraction_method": "json_ld",
        "title": title,
        "description": clean_text(
            recipe_object.get("description")
        ),
        "prep_time": parse_iso_duration_minutes(
            recipe_object.get("prepTime")
        ),
        "cook_time": parse_iso_duration_minutes(
            recipe_object.get("cookTime")
        ),
        "total_time": parse_iso_duration_minutes(
            recipe_object.get("totalTime")
        ),
        "servings_text": normalize_yield(
            recipe_object.get("recipeYield")
        ),
        "image_url": normalize_image_url(
            recipe_object.get("image")
        ),
        "ingredients": ingredients,
        "steps": [
            {
                "instruction": instruction,
            }
            for instruction in instructions
        ],
    }


# -------------------------------------------------------------------
# recipe-scrapers extraction
# -------------------------------------------------------------------

def safe_scraper_value(
    function,
    default=None,
):
    """
    Call an optional recipe-scrapers method without allowing one
    absent field to abort the entire import.
    """

    try:
        value = function()
    except Exception:
        return default

    if value in ("", [], {}):
        return default

    return value


def normalize_scraper_instructions(
    scraper,
) -> list[str]:
    """
    Extract an ordered instruction list from recipe-scrapers.
    """

    instruction_list = safe_scraper_value(
        scraper.instructions_list,
        default=None,
    )

    if instruction_list:
        return [
            clean_text(item)
            for item in instruction_list
            if clean_text(item)
        ]

    instructions_text = safe_scraper_value(
        scraper.instructions,
        default="",
    )

    if not instructions_text:
        return []

    return [
        clean_text(line)
        for line in str(
            instructions_text
        ).splitlines()
        if clean_text(line)
    ]


def extract_with_recipe_scrapers(
    html: str,
    source_url: str,
) -> dict[str, Any] | None:
    """
    Extract recipe data through recipe-scrapers.
    """

    try:
        scraper = scrape_html(
            html,
            source_url,
        )
    except Exception:
        return None

    title = clean_text(
        safe_scraper_value(
            scraper.title,
            default="",
        )
    )

    ingredients_raw = safe_scraper_value(
        scraper.ingredients,
        default=[],
    )

    ingredients = [
        clean_text(item)
        for item in ingredients_raw
        if clean_text(item)
    ]

    instructions = normalize_scraper_instructions(
        scraper
    )

    if not title or not ingredients or not instructions:
        return None

    return {
        "source_url": source_url,
        "extraction_method": "recipe_scrapers",
        "title": title,
        "description": clean_text(
            safe_scraper_value(
                scraper.description,
                default="",
            )
        ),
        "prep_time": safe_scraper_value(
            scraper.prep_time,
        ),
        "cook_time": safe_scraper_value(
            scraper.cook_time,
        ),
        "total_time": safe_scraper_value(
            scraper.total_time,
        ),
        "servings_text": clean_text(
            safe_scraper_value(
                scraper.yields,
                default="",
            )
        ),
        "image_url": safe_scraper_value(
            scraper.image,
            default="",
        ),
        "ingredients": [
            {
                "original_text": ingredient,
            }
            for ingredient in ingredients
        ],
        "steps": [
            {
                "instruction": instruction,
            }
            for instruction in instructions
        ],
    }


# -------------------------------------------------------------------
# Import orchestration
# -------------------------------------------------------------------

def extract_from_html(
    html: str,
    source_url: str,
) -> dict[str, Any] | None:
    """
    Try all supported parsers against one HTML document.
    """

    recipe = extract_json_ld_recipe(
        html,
        source_url,
    )

    if recipe is not None:
        return recipe

    return extract_with_recipe_scrapers(
        html,
        source_url,
    )


def extract_recipe_from_url(
    url: str,
) -> dict[str, Any]:
    """
    Import a recipe using lightweight HTTP first, followed by
    rendered-browser extraction when necessary.
    """

    requests_error = None

    try:
        html, final_url = fetch_recipe_html(url)

        recipe = extract_from_html(
            html,
            final_url,
        )

        if recipe is not None:
            recipe["fetch_method"] = "requests"
            return recipe

    except RecipeImportError as error:
        requests_error = str(error)

    try:
        rendered_html, final_url = (
            fetch_recipe_html_with_playwright(url)
        )

        recipe = extract_from_html(
            rendered_html,
            final_url,
        )

        if recipe is not None:
            recipe["fetch_method"] = "playwright"
            return recipe

    except RecipeImportError as error:
        if requests_error:
            raise RecipeImportError(
                f"Normal import failed: {requests_error} "
                f"Browser import failed: {error}"
            ) from error

        raise

    raise RecipeImportError(
        "The webpage loaded, but no complete structured recipe "
        "could be detected. It may not expose its ingredients and "
        "instructions in a supported format."
    )
    
IMPORT_CACHE_MAX_AGE_HOURS = 24


def get_import_cache_directory() -> Path:
    """
    Return the private server-side directory used for temporary
    imported-recipe data.
    """

    cache_directory = (
        Path(current_app.instance_path)
        / "import_cache"
    )

    cache_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    return cache_directory


def cleanup_expired_imports() -> None:
    """
    Remove temporary import files older than the configured age.
    """

    cache_directory = get_import_cache_directory()

    cutoff = (
        datetime.datetime.now(
            datetime.timezone.utc
        )
        - datetime.timedelta(
            hours=IMPORT_CACHE_MAX_AGE_HOURS
        )
    )

    for cache_file in cache_directory.glob("*.json"):
        try:
            modified = datetime.datetime.fromtimestamp(
                cache_file.stat().st_mtime,
                tz=datetime.timezone.utc,
            )

            if modified < cutoff:
                cache_file.unlink(
                    missing_ok=True
                )

        except OSError:
            current_app.logger.exception(
                "Unable to inspect temporary import: %s",
                cache_file,
            )


def save_import_draft(
    imported_recipe: dict,
    user_id: int,
) -> str:
    """
    Save extracted recipe data and return a random import token.
    """

    cleanup_expired_imports()

    import_token = uuid4().hex

    payload = {
        "user_id": user_id,
        "created": datetime.datetime.now(
            datetime.timezone.utc
        ).isoformat(),
        "recipe": imported_recipe,
    }

    cache_file = (
        get_import_cache_directory()
        / f"{import_token}.json"
    )

    temporary_file = cache_file.with_suffix(
        ".json.tmp"
    )

    temporary_file.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    temporary_file.replace(cache_file)

    return import_token


def load_import_draft(
    import_token: str,
    user_id: int,
) -> dict:
    """
    Load temporary import data belonging to the logged-in user.
    """

    if not re.fullmatch(
        r"[a-f0-9]{32}",
        import_token or "",
    ):
        raise RecipeImportError(
            "The import reference is invalid."
        )

    cache_file = (
        get_import_cache_directory()
        / f"{import_token}.json"
    )

    if not cache_file.exists():
        raise RecipeImportError(
            "This import has expired or no longer exists."
        )

    try:
        payload = json.loads(
            cache_file.read_text(
                encoding="utf-8"
            )
        )

    except (
        OSError,
        json.JSONDecodeError,
    ) as error:
        raise RecipeImportError(
            "The temporary import could not be read."
        ) from error

    if payload.get("user_id") != user_id:
        raise RecipeImportError(
            "This import belongs to another user."
        )

    recipe = payload.get("recipe")

    if not isinstance(recipe, dict):
        raise RecipeImportError(
            "The temporary import is invalid."
        )

    return recipe


def delete_import_draft(
    import_token: str,
) -> None:
    """
    Delete temporary import data after a successful save.
    """

    if not re.fullmatch(
        r"[a-f0-9]{32}",
        import_token or "",
    ):
        return

    cache_file = (
        get_import_cache_directory()
        / f"{import_token}.json"
    )

    cache_file.unlink(
        missing_ok=True
    )
    
UNIT_ALIASES = {
    "tsp": "teaspoon",
    "tsp.": "teaspoon",
    "teaspoons": "teaspoon",
    "teaspoon": "teaspoon",

    "tbsp": "tablespoon",
    "tbsp.": "tablespoon",
    "tablespoons": "tablespoon",
    "tablespoon": "tablespoon",

    "c": "cup",
    "c.": "cup",
    "cups": "cup",
    "cup": "cup",

    "pt": "pint",
    "pints": "pint",
    "pint": "pint",

    "qt": "quart",
    "quarts": "quart",
    "quart": "quart",

    "gal": "gallon",
    "gallons": "gallon",
    "gallon": "gallon",

    "fl oz": "fluid_ounce",
    "fluid ounces": "fluid_ounce",
    "fluid ounce": "fluid_ounce",

    "ml": "milliliter",
    "milliliters": "milliliter",
    "milliliter": "milliliter",

    "l": "liter",
    "liters": "liter",
    "liter": "liter",

    "oz": "ounce",
    "ounces": "ounce",
    "ounce": "ounce",

    "lb": "pound",
    "lb.": "pound",
    "lbs": "pound",
    "pounds": "pound",
    "pound": "pound",

    "g": "gram",
    "grams": "gram",
    "gram": "gram",

    "kg": "kilogram",
    "kilograms": "kilogram",
    "kilogram": "kilogram",

    "cloves": "clove",
    "clove": "clove",

    "cans": "can",
    "can": "can",

    "packages": "package",
    "package": "package",

    "slices": "slice",
    "slice": "slice",

    "pieces": "piece",
    "piece": "piece",

    "bunches": "bunch",
    "bunch": "bunch",

    "pinches": "pinch",
    "pinch": "pinch",

    "dashes": "dash",
    "dash": "dash",
}


VULGAR_FRACTIONS = {
    "¼": "1/4",
    "½": "1/2",
    "¾": "3/4",
    "⅐": "1/7",
    "⅑": "1/9",
    "⅒": "1/10",
    "⅓": "1/3",
    "⅔": "2/3",
    "⅕": "1/5",
    "⅖": "2/5",
    "⅗": "3/5",
    "⅘": "4/5",
    "⅙": "1/6",
    "⅚": "5/6",
    "⅛": "1/8",
    "⅜": "3/8",
    "⅝": "5/8",
    "⅞": "7/8",
}


def normalize_fraction_characters(
    text: str,
) -> str:
    """
    Convert common Unicode fractions into plain-text fractions.
    """

    result = str(text or "")

    for character, fraction in (
        VULGAR_FRACTIONS.items()
    ):
        result = result.replace(
            character,
            f" {fraction}",
        )

    return " ".join(
        result.split()
    )


def parse_imported_ingredient(
    original_text: str,
) -> dict:
    """
    Split a recipe ingredient into quantity, unit, and name.

    Parsing is deliberately conservative because the review page
    remains the final authority.
    """

    cleaned = normalize_fraction_characters(
        clean_text(original_text)
    )

    quantity = ""
    unit = ""
    ingredient_name = cleaned

    quantity_pattern = re.compile(
        r"^\s*"
        r"(?P<quantity>"
        r"(?:\d+\s+\d+/\d+)"
        r"|(?:\d+/\d+)"
        r"|(?:\d+(?:\.\d+)?)"
        r")"
        r"(?:\s*[-–]\s*"
        r"(?:\d+\s+\d+/\d+|\d+/\d+|\d+(?:\.\d+)?)"
        r")?"
        r"\s+"
        r"(?P<remaining>.+)$"
    )

    quantity_match = quantity_pattern.match(
        cleaned
    )

    if quantity_match:
        quantity = quantity_match.group(
            "quantity"
        ).strip()

        ingredient_name = quantity_match.group(
            "remaining"
        ).strip()

    alias_candidates = sorted(
        UNIT_ALIASES,
        key=len,
        reverse=True,
    )

    for alias in alias_candidates:
        pattern = re.compile(
            rf"^{re.escape(alias)}(?:\s+|$)",
            re.IGNORECASE,
        )

        if pattern.match(ingredient_name):
            unit = UNIT_ALIASES[alias]

            ingredient_name = pattern.sub(
                "",
                ingredient_name,
                count=1,
            ).strip()

            break

    ingredient_name = ingredient_name.strip(
        " ,"
    )

    return {
        "original_text": cleaned,
        "quantity": quantity,
        "unit": unit,
        "name": ingredient_name or cleaned,
        "section": "",
    }


def prepare_import_for_review(
    imported_recipe: dict,
) -> dict:
    """
    Add editable parsed fields to extracted import data.
    Preserve ingredient sections when available.
    """

    review_recipe = dict(
        imported_recipe
    )

    review_recipe["ingredients"] = []

    for item in imported_recipe.get(
        "ingredients",
        [],
    ):
        parsed = parse_imported_ingredient(
            item.get(
                "original_text",
                "",
            )
        )

        parsed["section"] = (
            item.get(
                "section",
                "",
            )
            or ""
        )

        review_recipe["ingredients"].append(
            parsed
        )

    review_recipe["steps"] = [
        {
            "instruction": clean_text(
                step.get(
                    "instruction",
                    "",
                )
            ),
            "timer_minutes": "",
        }
        for step in imported_recipe.get(
            "steps",
            []
        )
        if clean_text(
            step.get(
                "instruction",
                "",
            )
        )
    ]

    return review_recipe
    
MAX_IMAGE_BYTES = 10 * 1024 * 1024

ALLOWED_IMAGE_CONTENT_TYPES = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}


def download_imported_image(
    image_url: str,
    recipe_id: int,
) -> tuple[str, Path]:
    """
    Download a source recipe image into the existing upload folder.

    Returns the stored filename and full local path.
    """

    validate_public_url(image_url)

    try:
        response = requests.get(
            image_url,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": (
                    "image/jpeg,"
                    "image/png,"
                    "image/webp"
                ),
            },
            timeout=REQUEST_TIMEOUT,
            stream=True,
            allow_redirects=False,
        )

    except requests.RequestException as error:
        raise RecipeImportError(
            "The recipe image could not be downloaded."
        ) from error

    try:
        response.raise_for_status()

        content_type = (
            response.headers.get(
                "Content-Type",
                "",
            )
            .split(";", 1)[0]
            .strip()
            .lower()
        )

        extension = (
            ALLOWED_IMAGE_CONTENT_TYPES.get(
                content_type
            )
        )

        if not extension:
            raise RecipeImportError(
                "The source image is not JPG, PNG, or WebP."
            )

        upload_directory = (
            Path(current_app.static_folder)
            / "uploads"
            / "recipes"
        )

        upload_directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        stored_filename = (
            f"recipe_{recipe_id}_{uuid4().hex}."
            f"{extension}"
        )

        file_path = (
            upload_directory
            / stored_filename
        )

        downloaded_bytes = 0

        with file_path.open("wb") as output_file:
            for chunk in response.iter_content(
                chunk_size=64 * 1024
            ):
                if not chunk:
                    continue

                downloaded_bytes += len(chunk)

                if (
                    downloaded_bytes
                    > MAX_IMAGE_BYTES
                ):
                    output_file.close()
                    file_path.unlink(
                        missing_ok=True
                    )

                    raise RecipeImportError(
                        "The source recipe image is too large."
                    )

                output_file.write(chunk)

        return stored_filename, file_path

    finally:
        response.close()