import pytest


@pytest.mark.django_db
def test_dark_theme_initial_script_present(client):
    resp = client.get("/")
    html = resp.content.decode("utf-8")

    # script that reads localStorage and prefers-color-scheme
    assert "localStorage.getItem('theme')" in html
    assert "prefers-color-scheme: dark" in html
    assert "document.documentElement.setAttribute('data-theme', 'dark')" in html


@pytest.mark.django_db
def test_theme_toggle_script_present(client):
    resp = client.get("/")
    html = resp.content.decode("utf-8")

    # script that wires #theme-toggle and setTheme()
    assert "var btn = document.getElementById('theme-toggle')" in html
    assert "function setTheme(theme)" in html
    assert "localStorage.setItem('theme', theme)" in html


@pytest.mark.django_db
def test_dark_theme_css_hooks_exist(client):
    resp = client.get("/")
    html = resp.content.decode("utf-8")

    # Check some crucial CSS selectors in the <style> block
    assert 'html[data-theme="dark"]' in html
    assert "background: var(--bg)" in html
    assert ".menu.lvl1" in html
    assert ".menu.lvl2" in html
    assert ".footer" in html
