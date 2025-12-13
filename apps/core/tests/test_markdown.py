import pytest
from apps.core.utils import render_markdown

def test_render_markdown_basic():
    html = render_markdown("# Hello *world*")

    assert "<h1>" in html
    assert "Hello" in html
    assert "<em>world</em>" in html or "<i>world</i>" in html


def test_render_markdown_table():
    markdown = """
| A | B |
|---|---|
| 1 | 2 |
"""
    html = render_markdown(markdown)

    # basic sanity check: it produces a table
    assert "<table>" in html
    assert "<td>1</td>" in html
    assert "<td>2</td>" in html


def test_render_markdown_sanitizes_script():
    markdown = 'Hello <script>alert("x")</script>'

    html = render_markdown(markdown)

    assert "Hello" in html
    assert "<script" not in html  # bleach should strip this
