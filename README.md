## Trip page generator

This project generates static HTML “trip pages” from PostgreSQL data and HTML templates. It includes:

- A command‑line generator module (`src/generator.py`) that renders pages.
- A Tkinter GUI manager (`src/gui_manager.py`) to view/edit page/snippet data and trigger generation.

The sections below explain how each module works, how to configure the system, and how to use both the CLI and the GUI.

### Quick start

1) Configure your database connection in `config/database.ini` (see Configuration).
2) Ensure you have templates in `templates/` (see Templates).
3) Generate a page from the CLI:

```
python -m src.generator turkey.html --snippet-template templates/snippet.html
```

4) Or start the GUI and use the Generate button from the Page section:

```
python -m src.gui_manager
```

---

### Configuration

The generator reads PostgreSQL connection settings from environment variables or a configuration file; environment variables take precedence.

- Config file (default): `config/database.ini`
- Alternative file via env var: `DB_CONFIG_FILE=/path/to/database.ini`

Expected INI structure:

```
[postgresql]
host=127.0.0.1
port=5432
dbname=your_db
user=your_user
password=your_password
```

Environment variables (override file values): `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`.

Logging can be controlled with `--log-level` (CLI) or `LOG_LEVEL` env var.

---

### Data model (expected tables)

The code expects two tables with (at least) the following columns:

- trip_page
  - `page_id` (PK, integer)
  - `page_name` (text, e.g., `turkey.html`)
  - `page_desc` (text, optional)

- trip_snippet
  - `snippet_id` (PK, integer)
  - `page_id` (FK to `trip_page.page_id`)
  - `code`, `request_desc`, `destination`, `image`, `imagetitle`
  - `tagline1`, `tagline2`, `price`, `title`, `shortdesc`, `description`, `inclusionhtml`
  - `active` (integer; non‑zero is considered active)

The GUI code inserts IDs using database sequences named `trip_page_gen` and `trip_snippet_gen`. Adjust to your schema if needed.

---

### Templates

- Templates directory: `templates/` (default). You can override via env var `TEMPLATES_DIR`.
- Page skeleton: a file named `<page_name>.skel`, for example `templates/turkey.html.skel`.
- Snippet template: an HTML snippet template. Default is `templates/snippet.html`.
- Injection marker: the page skeleton must contain the exact line/text:

```
--- INSERT SNIPPETS HERE ---
```

During generation, rendered snippets are concatenated and replace this marker in the skeleton.

Placeholders in templates use double percent syntax and are case‑insensitive:

```
%%title%%, %%ShortDesc%%, %%PRICE%%, etc.
```

The renderer matches placeholder names ignoring case and will output an empty string if a value is missing.

---

### Module: src/generator.py (CLI page generator)

Purpose
- Load DB config, fetch page and its snippets, render each active snippet through a snippet template, inject into the skeleton, and write the final HTML to disk.

Key behavior
- Skeleton path: `templates/<page_name>.skel`.
- Snippet template path: defaults to `templates/snippet.html`, can be overridden via `--snippet-template` or an absolute/relative path.
- Only snippets with an integer `active` value that is non‑zero are rendered; others are skipped.
- Placeholders (`%%name%%`) are matched case‑insensitively; data lookup is also case‑insensitive, preferring exact‑case keys when available.
- The skeleton must contain the marker `--- INSERT SNIPPETS HERE ---` or generation fails.
- Output file defaults to `<page_name>` in the current working directory; can be overridden with `--output`.

Command‑line usage

```
python -m src.generator PAGE_NAME [--snippet-template PATH] [--output PATH] [--log-level LEVEL]

# Example
python -m src.generator turkey.html --snippet-template templates/snippet.html --log-level DEBUG
```

Environment
- `DB_CONFIG_FILE`, `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`
- `TEMPLATES_DIR` to override the templates directory
- `LOG_LEVEL` (alternative to `--log-level`)

Errors and exits
- Raises `GenerationError` when required config/inputs are missing or invalid (e.g., missing skeleton, no page row, marker absent). The CLI logs and exits with a non‑zero code on failure.

---

### Module: src/gui_manager.py (Tkinter GUI)

Purpose
- Manage `trip_page` and `trip_snippet` records and trigger page generation from a graphical interface.

Main features
- Left pane lists Trip Pages; right pane lists Snippets for the selected page.
- Forms for editing page/snippet fields; Add and Save actions for both.
- Generate button in the Page section that calls the generator to render the currently selected page using `templates/snippet.html`.
- Inline validation and user feedback via message boxes; logging for troubleshooting.

Starting the GUI

```
python -m src.gui_manager          # add --debug for verbose logs
```

Usage steps
- Select a page or click Add Page, enter `page_name` (required) and optional `page_desc`, then Save.
- Select a page and manage its snippets: Add Snippet, fill fields, set `active` (integer; 0/1), then Save.
- Click Generate to render the selected page. On success, the output file path is shown.

Database connection
- Uses the same configuration resolution as the CLI via `src.generator.load_db_config()`.
- Requires `psycopg` installed and reachable PostgreSQL instance.

---

### How generation works (end‑to‑end)

1) Load DB config (env overrides file).
2) Resolve `templates/` directory (env `TEMPLATES_DIR` overrides default).
3) Read page skeleton `templates/<page_name>.skel`.
4) Read snippet template (default `templates/snippet.html`, or user path/CLI arg).
5) Query `trip_page` by `page_name`; read its `page_id`.
6) Query `trip_snippet` rows by `page_id` ordered by `snippet_id`.
7) Filter to active snippets; render each against the snippet template, replacing `%%placeholders%%`.
8) Inject concatenated snippets into the skeleton at `--- INSERT SNIPPETS HERE ---`.
9) Write final HTML to `<page_name>` (or provided `--output`).

---

### Examples

- Generate `turkey.html` using default snippet template:

```
python -m src.generator turkey.html
```

- Generate with a custom snippet template and output location:

```
python -m src.generator turkey.html --snippet-template path/to/custom_snippet.html --output dist/turkey.html
```

- Start the GUI and generate from there:

```
python -m src.gui_manager --debug
```

---

### Dependencies

- Python 3.9+
- `psycopg` (PostgreSQL driver)

Install with:

```
pip install psycopg
```

---

### Testing

Run the tests (if you have a test suite configured locally):

```
pytest -q
```

`tests/test_generator.py` covers core rendering behaviors (e.g., placeholder handling, active flag, injection marker).

---

### Troubleshooting

- Generation failed: Missing `--- INSERT SNIPPETS HERE ---` in skeleton.
  - Ensure your `<page_name>.skel` contains the exact marker.
- No `trip_page` entry found.
  - Verify `trip_page.page_name` matches the name you provide (e.g., `turkey.html`).
- DB connection errors.
  - Check env vars or `config/database.ini`, and confirm the database is reachable.
- Nothing renders (empty page content area).
  - Check that your snippets have `active` set to a non‑zero integer.

---

### License

This repository is intended for internal use in examples. Add license details here if distributing.
