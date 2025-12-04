import pytest
from bs4 import BeautifulSoup

@pytest.mark.django_db
def test_viewport_meta_present(client):
    """
    Mobile: page must define responsive viewport meta.
    """
    resp = client.get("/")
    assert resp.status_code == 200

    soup = BeautifulSoup(resp.content, "html.parser")
    meta = soup.find("meta", attrs={"name": "viewport"})
    assert meta is not None
    assert meta["content"] == "width=device-width, initial-scale=1"


@pytest.mark.django_db
def test_dark_theme_script_present(client):
    """
    Dark theme: JS that sets data-theme based on localStorage or prefers-color-scheme
    must be present in the HTML.
    """
    resp = client.get("/")
    assert resp.status_code == 200

    html = resp.content.decode("utf-8")

    # Check the initial theme script is included
    assert "localStorage.getItem('theme')" in html
    assert "prefers-color-scheme: dark" in html
    assert "document.documentElement.setAttribute('data-theme', 'dark')" in html


@pytest.mark.django_db
def test_theme_toggle_script_present(client):
    """
    Dark theme: page must include the toggle script that flips data-theme and localStorage.
    """
    resp = client.get("/")
    assert resp.status_code == 200

    html = resp.content.decode("utf-8")

    # Basic sanity: script that wires #theme-toggle
    assert "var btn = document.getElementById('theme-toggle')" in html
    assert "setTheme(isDark ? 'light' : 'dark')" in html
    assert "localStorage.setItem('theme', theme)" in html


@pytest.mark.django_db
def test_theme_toggle_button_exists_in_dom(client):
    """
    Dark theme: layout must render a button with id='theme-toggle' somewhere
    (usually in top menu).
    """
    resp = client.get("/")
    assert resp.status_code == 200

    soup = BeautifulSoup(resp.content, "html.parser")
    toggle = soup.find(id="theme-toggle")
    # If it's rendered in the top menu include, this will be True.
    assert toggle is not None


@pytest.mark.django_db
def test_core_css_included(client):
    resp = client.get("/")
    assert resp.status_code == 200
    html = resp.content.decode("utf-8")

    assert 'v1/dist/css/center_style.css' in html
    assert 'v1/dist/css/responsive-overrides.css' in html


@pytest.mark.django_db
def test_layout_uses_bootstrap_grid(client):
    resp = client.get("/")
    soup = BeautifulSoup(resp.content, "html.parser")

    columns = soup.select(".container .row .col-xs-12")
    assert len(columns) >= 1
