import pytest
from bs4 import BeautifulSoup


@pytest.mark.django_db
def test_viewport_meta_for_mobile(client):
    resp = client.get("/")
    soup = BeautifulSoup(resp.content, "html.parser")

    meta = soup.find("meta", attrs={"name": "viewport"})
    assert meta is not None
    assert meta.get("content") == "width=device-width, initial-scale=1"


@pytest.mark.django_db
def test_responsive_css_included(client):
    resp = client.get("/")
    html = resp.content.decode("utf-8")

    assert "v1/dist/css/center_style.css" in html
    assert "v1/dist/css/responsive-overrides.css" in html


@pytest.mark.django_db
def test_bootstrap_grid_present(client):
    resp = client.get("/")
    soup = BeautifulSoup(resp.content, "html.parser")

    cols = soup.select(".container .row .col-xs-12")
    assert len(cols) >= 1
