from pathlib import Path

import pytest

from src import generator


def test_parse_args_defaults_snippet_template():
    args = generator.parse_args(["page.html"])
    assert args.page_name == "page.html"
    assert args.snippet_template is None


def test_parse_args_accepts_optional_snippet_template():
    args = generator.parse_args(["page.html", "--snippet-template", "snippet.html"])
    assert args.page_name == "page.html"
    assert args.snippet_template == Path("snippet.html")


@pytest.mark.parametrize(
    "template,data,expected",
    [
        ("<h1>%%title%%</h1>", {"title": "Hello"}, "<h1>Hello</h1>"),
        (
            "<p>%%title%% %%subtitle%%</p>",
            {"title": "Hello", "subtitle": "World"},
            "<p>Hello World</p>",
        ),
        (
            "<p>%%title%% %%subtitle%%</p>",
            {"title": "Hello", "subtitle": None},
            "<p>Hello </p>",
        ),
    ],
)
def test_render_snippet_replaces_placeholders(template, data, expected):
    assert generator.render_snippet(template, data) == expected


def test_render_snippets_concatenates_results():
    template = "<p>%%title%%</p>"
    data = [
        {"title": "First", "active": 1},
        {"title": "Second", "active": 2},
    ]
    assert generator.render_snippets(template, data) == "<p>First</p>\n<p>Second</p>"


def test_render_snippets_skips_inactive_snippets():
    template = "<p>%%title%%</p>"
    data = [
        {"title": "First", "active": 0},
        {"title": "Second", "active": 1},
        {"title": "Third", "active": "0"},
        {"title": "Fourth", "active": "2"},
        {"title": "Fifth"},
    ]
    assert generator.render_snippets(template, data) == "<p>Second</p>\n<p>Fourth</p>"


def test_inject_snippets_missing_marker_raises():
    with pytest.raises(generator.GenerationError):
        generator.inject_snippets("<section></section>", "content")


def test_inject_snippets_replaces_marker():
    skeleton = "<section name=\"data_placeholder\">--- INSERT SNIPPETS HERE ---</section>"
    rendered = "<p>Hello</p>"
    assert (
        generator.inject_snippets(skeleton, rendered)
        == "<section name=\"data_placeholder\"><p>Hello</p></section>"
    )


def test_generate_page_uses_provided_snippet_template(monkeypatch, tmp_path):
    templates_dir = tmp_path / "templates"
    templates_dir.mkdir()

    skeleton_path = templates_dir / "example.html.skel"
    skeleton_path.write_text(
        '<section name="data_placeholder">--- INSERT SNIPPETS HERE ---</section>',
        encoding="utf-8",
    )

    snippet_template_path = templates_dir / "custom_snippet.html"
    snippet_template_path.write_text(
        "<article>%%title%% %%extra%%</article>",
        encoding="utf-8",
    )

    class DummyCursor:
        def __init__(self):
            self._fetched_page = False
            self.queries = []

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, query, params):
            self.queries.append((query, params))

        def fetchone(self):
            if not self._fetched_page:
                self._fetched_page = True
                return {"page_id": 7}
            return None

        def fetchall(self):
            return [{"title": "Hello", "extra": "World", "active": 1}]

    class DummyConnection:
        def __init__(self):
            self.cursor_instance = DummyCursor()

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def cursor(self, row_factory=None):
            return self.cursor_instance

    connection = DummyConnection()

    monkeypatch.setenv("TEMPLATES_DIR", str(templates_dir))
    monkeypatch.setattr(generator, "load_db_config", lambda: None)
    monkeypatch.setattr(generator, "connect_to_db", lambda config: connection)

    output_path = tmp_path / "example.html"
    result = generator.generate_page(
        "example.html",
        snippet_template_name=snippet_template_path,
        output_path=output_path,
    )

    assert result == output_path
    assert (
        output_path.read_text(encoding="utf-8")
        == '<section name="data_placeholder"><article>Hello World</article></section>'
    )

    executed_queries = connection.cursor_instance.queries
    assert executed_queries[0][0].startswith("SELECT * FROM tlinq.trip_page")
    assert executed_queries[1][0].startswith("SELECT * FROM tlinq.trip_snippet")
