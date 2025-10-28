"""Generate static trip pages from database content and templates.

This module provides a CLI entry point::

    python -m src.generator turkey.html snippet.html

It loads snippets from the database, renders them using the snippet template and
injects them into the page skeleton.
"""

from __future__ import annotations

import argparse
import configparser
import logging
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional

try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError as exc:  # pragma: no cover - import guard
    psycopg = None  # type: ignore[assignment]
    dict_row = None  # type: ignore[assignment]
    _IMPORT_ERROR = exc
else:
    _IMPORT_ERROR = None

LOGGER = logging.getLogger(__name__)
PLACEHOLDER_MARKER = "--- INSERT SNIPPETS HERE ---"
DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "database.ini"
DEFAULT_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
DEFAULT_SNIPPET_TEMPLATE_NAME = Path("snippet.html")

PLACEHOLDER_PATTERN = re.compile(r"%%([a-zA-Z0-9_]+)%%")


@dataclass
class DBConfig:
    """Connection configuration for PostgreSQL."""

    host: str
    port: int
    dbname: str
    user: str
    password: str

    def to_kwargs(self) -> Dict[str, object]:
        return {
            "host": self.host,
            "port": self.port,
            "dbname": self.dbname,
            "user": self.user,
            "password": self.password,
        }


class GenerationError(RuntimeError):
    """Raised when page generation cannot be completed."""


def load_db_config() -> DBConfig:
    """Load database configuration from environment variables or a config file.

    Environment variables override configuration file values.
    Supported environment variables: ``DB_HOST``, ``DB_PORT``, ``DB_NAME``,
    ``DB_USER``, ``DB_PASSWORD``.

    If ``DB_CONFIG_FILE`` is set, it will be used as the configuration file path;
    otherwise ``config/database.ini`` relative to the repository root is used
    (if it exists). The file is expected to have a ``[postgresql]`` section.
    """

    config_values: Dict[str, str] = {}

    config_file_env = os.getenv("DB_CONFIG_FILE")
    config_file = (
        Path(config_file_env).expanduser() if config_file_env else DEFAULT_CONFIG_PATH
    )
    if config_file.exists():
        parser = configparser.ConfigParser()
        parser.read(config_file)
        if parser.has_section("postgresql"):
            config_values.update(parser["postgresql"])
            LOGGER.debug("Loaded DB config from %s", config_file)
        else:
            LOGGER.warning(
                "Config file %s exists but is missing [postgresql] section", config_file
            )
    else:
        LOGGER.info("Config file %s not found; relying on environment variables", config_file)

    env_mapping = {
        "host": os.getenv("DB_HOST"),
        "port": os.getenv("DB_PORT"),
        "dbname": os.getenv("DB_NAME"),
        "user": os.getenv("DB_USER"),
        "password": os.getenv("DB_PASSWORD"),
    }
    for key, value in env_mapping.items():
        if value is not None:
            config_values[key] = value

    missing = [key for key in ("host", "port", "dbname", "user", "password") if key not in config_values]
    if missing:
        raise GenerationError(
            "Missing database configuration values: " + ", ".join(sorted(missing))
        )

    try:
        port = int(config_values["port"])
    except ValueError as exc:  # pragma: no cover - config error branch
        raise GenerationError(f"Invalid port number: {config_values['port']}") from exc

    return DBConfig(
        host=config_values["host"],
        port=port,
        dbname=config_values["dbname"],
        user=config_values["user"],
        password=config_values["password"],
    )


def connect_to_db(config: DBConfig):
    """Create a PostgreSQL connection using the supplied config."""

    if psycopg is None:  # pragma: no cover - environment specific branch
        raise GenerationError(
            "psycopg is required to connect to PostgreSQL. Install it before running the generator."
        ) from _IMPORT_ERROR

    LOGGER.debug("Connecting to PostgreSQL at %s:%s", config.host, config.port)
    return psycopg.connect(**config.to_kwargs())


def fetch_page(cursor, page_name: str) -> Mapping[str, object]:
    """Fetch the trip page record for the given page name."""

    LOGGER.debug("Fetching trip_page for %s", page_name)
    cursor.execute("SELECT * FROM tlinq.trip_page WHERE page_name = %s", (page_name,))
    row = cursor.fetchone()
    if row is None:
        raise GenerationError(f"No trip_page entry found for {page_name!r}")
    return row


def fetch_snippets(cursor, page_id: object) -> List[Mapping[str, object]]:
    """Fetch all trip snippets for the supplied page id."""

    LOGGER.debug("Fetching trip_snippet rows for page_id=%s", page_id)
    cursor.execute(
        "SELECT * FROM tlinq.trip_snippet WHERE page_id = %s ORDER BY snippet_id",
        (page_id,),
    )
    return list(cursor.fetchall())


def load_file(path: Path) -> str:
    """Load the content of a file as text."""

    try:
        content = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise GenerationError(f"Required template file not found: {path}") from exc
    LOGGER.debug("Loaded template file %s", path)
    return content


def resolve_templates_dir() -> Path:
    """Resolve the templates directory, allowing overrides via env var."""

    override = os.getenv("TEMPLATES_DIR")
    return Path(override) if override else DEFAULT_TEMPLATES_DIR


def render_snippet(snippet_template: str, data: Mapping[str, object]) -> str:
    """Render a single snippet using the provided template and data."""

    def replace(match: re.Match[str]) -> str:
        field = match.group(1)
        value = data.get(field)
        return "" if value is None else str(value)

    return PLACEHOLDER_PATTERN.sub(replace, snippet_template)


def _is_snippet_active(snippet: Mapping[str, object]) -> bool:
    """Return True if the snippet contains an active flag that is non-zero."""

    if "active" not in snippet:
        LOGGER.debug("Skipping snippet without 'active' flag: %s", snippet)
        return False

    active_value = snippet["active"]
    try:
        return int(active_value) != 0
    except (TypeError, ValueError):
        LOGGER.warning(
            "Snippet has non-integer active flag %r; skipping snippet", active_value
        )
        return False


def render_snippets(snippet_template: str, snippets: Iterable[Mapping[str, object]]) -> str:
    """Render all active snippets using the template and concatenate them."""

    rendered_snippets: List[str] = []
    skipped = 0
    for snippet in snippets:
        if not _is_snippet_active(snippet):
            skipped += 1
            continue
        rendered_snippets.append(render_snippet(snippet_template, snippet))

    LOGGER.debug(
        "Rendered %d snippet(s); skipped %d inactive snippet(s)",
        len(rendered_snippets),
        skipped,
    )
    return "\n".join(rendered_snippets)


def inject_snippets(skeleton: str, rendered_snippets: str) -> str:
    """Inject rendered snippets into the skeleton, replacing the placeholder marker."""

    if PLACEHOLDER_MARKER not in skeleton:
        raise GenerationError(
            "Skeleton template missing placeholder marker '--- INSERT SNIPPETS HERE ---'"
        )
    return skeleton.replace(PLACEHOLDER_MARKER, rendered_snippets)


def resolve_snippet_template_path(snippet_template: Path, templates_dir: Path) -> Path:
    """Resolve the snippet template path relative to the templates directory."""

    candidate = Path(snippet_template)
    if candidate.is_absolute() or candidate.exists():
        return candidate
    return templates_dir / candidate


def generate_page(
    page_name: str,
    snippet_template_name: Optional[Path] = None,
    *,
    output_path: Optional[Path] = None,
) -> Path:
    """Generate a page from database content and templates.

    :param page_name: The name of the page file to build (e.g. "turkey.html").
    :param snippet_template_name: The snippet template filename/path to render snippets with.
    :param output_path: Optional override for the output path.
    :returns: The path to the generated file.
    :raises GenerationError: When generation fails for any reason.
    """

    config = load_db_config()
    templates_dir = resolve_templates_dir()
    skeleton_path = templates_dir / f"{page_name}.skel"
    snippet_template_input = snippet_template_name or DEFAULT_SNIPPET_TEMPLATE_NAME
    snippet_template_path = resolve_snippet_template_path(snippet_template_input, templates_dir)

    skeleton = load_file(skeleton_path)
    snippet_template = load_file(snippet_template_path)

    with connect_to_db(config) as conn:
        with conn.cursor(row_factory=dict_row) as cursor:
            page = fetch_page(cursor, page_name)
            page_id = page.get("page_id")
            if page_id is None:
                raise GenerationError("trip_page row is missing a 'page_id' column")
            snippets = fetch_snippets(cursor, page_id)

    rendered_snippets = render_snippets(snippet_template, snippets)
    final_content = inject_snippets(skeleton, rendered_snippets)

    output = output_path or Path(page_name)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(final_content, encoding="utf-8")
    LOGGER.info("Generated page %s", output)
    return output


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate static trip pages")
    parser.add_argument(
        "page_name",
        help="Page name to generate (e.g. turkey.html)",
    )
    parser.add_argument(
        "--snippet-template",
        type=Path,
        default=None,
        help="Snippet template filename (defaults to templates/snippet.html)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional output path. Defaults to <page_name> in the working directory.",
    )
    parser.add_argument(
        "--log-level",
        default=os.getenv("LOG_LEVEL", "INFO"),
        help="Logging level (DEBUG, INFO, etc.)",
    )
    return parser.parse_args(argv)


def configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    configure_logging(args.log_level)

    try:
        generate_page(args.page_name, args.snippet_template, output_path=args.output)
    except GenerationError as exc:
        LOGGER.error("Generation failed: %s", exc)
        return 1
    except Exception:  # pragma: no cover - catch-all logging path
        LOGGER.exception("Unexpected error during page generation")
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    sys.exit(main())
