import pytest

from app import create_app
from models import MAX_URL_LENGTH, SHORT_CODE_LENGTH, Link, db, generate_short_code, validate_url


@pytest.fixture
def shortener_app():
    """A fresh app (in-memory database) whose app context is not left open."""
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"})
    with app.app_context():
        db.create_all()
    yield app
    with app.app_context():
        db.session.remove()
        db.drop_all()
        db.engine.dispose()


def logged_in(app, username="alice"):
    """A new client that has registered (and so is logged in) as the given user."""
    client = app.test_client()
    client.post("/register", data={"username": username, "password": "password123"})
    return client


def make_link(client, url="https://example.com/some/long/page"):
    response = client.post("/api/links", json={"url": url})
    assert response.status_code == 201
    return response.get_json()




@pytest.mark.parametrize("url", ["https://www.swinburne.edu.au", "http://example.com/a/b?x=1#top"])
def test_validate_url_accepts_http_and_https(url):
    assert validate_url(url) == url


def test_validate_url_strips_surrounding_spaces():
    assert validate_url("  https://example.com  ") == "https://example.com"


@pytest.mark.parametrize("bad", [
    None,
    123,
    ["https://example.com"],
    "",
    "   ",
    "hello",
    "javascript:alert(1)",
    "ftp://example.com",
    "https://",
    "https://exa mple.com",
    "https://example.com/" + "a" * MAX_URL_LENGTH,
])
def test_validate_url_rejects_bad_input(bad):
    with pytest.raises(ValueError):
        validate_url(bad)




def test_generated_code_has_expected_length_and_characters():
    code = generate_short_code()
    assert len(code) == SHORT_CODE_LENGTH
    assert code.isalnum()


def test_generated_codes_are_not_all_identical():
    assert len({generate_short_code() for _ in range(50)}) > 1




def test_managing_links_requires_login(shortener_app):
    anonymous = shortener_app.test_client()
    assert anonymous.get("/links").status_code == 302
    assert "/login" in anonymous.get("/links").headers["Location"]
    assert anonymous.post("/links", data={"url": "https://example.com"}).status_code == 302
    assert anonymous.get("/api/links").status_code == 401
    assert anonymous.post("/api/links", json={"url": "https://example.com"}).status_code == 401




def test_api_creates_a_short_link(shortener_app):
    alice = logged_in(shortener_app)
    link = make_link(alice, "https://www.swinburne.edu.au")
    assert link["original_url"] == "https://www.swinburne.edu.au"
    assert len(link["short_code"]) == SHORT_CODE_LENGTH
    assert link["clicks"] == 0
    assert link["short_url"].endswith("/s/" + link["short_code"])


def test_form_creates_a_short_link_and_shows_it(shortener_app):
    alice = logged_in(shortener_app)
    response = alice.post("/links", data={"url": "https://example.com/page"}, follow_redirects=True)
    assert response.status_code == 200
    assert b"https://example.com/page" in response.data


def test_api_rejects_a_dangerous_url(shortener_app):
    alice = logged_in(shortener_app)
    response = alice.post("/api/links", json={"url": "javascript:alert(1)"})
    assert response.status_code == 400
    assert "http" in response.get_json()["error"]
    assert alice.get("/api/links").get_json() == []          


def test_api_rejects_a_url_that_is_not_text(shortener_app):
    alice = logged_in(shortener_app)
    response = alice.post("/api/links", json={"url": 123})
    assert response.status_code == 400                      # previously crashed with a 500
    assert response.get_json()["error"] == "URL is required."


def test_form_shows_an_error_for_a_bad_url(shortener_app):
    alice = logged_in(shortener_app)
    response = alice.post("/links", data={"url": "hello"})
    assert response.status_code == 400
    assert b"must start with http" in response.data


def test_link_is_saved_in_the_database(shortener_app):
    alice = logged_in(shortener_app)
    link = make_link(alice, "https://example.com/stored")
    with shortener_app.app_context():
        stored = db.session.execute(db.select(Link)).scalar_one()
        assert stored.short_code == link["short_code"]
        assert stored.original_url == "https://example.com/stored"
        assert stored.clicks == 0




def test_short_link_redirects_without_logging_in(shortener_app):
    alice = logged_in(shortener_app)
    link = make_link(alice, "https://www.swinburne.edu.au")
    visitor = shortener_app.test_client()                    # not logged in
    response = visitor.get("/s/" + link["short_code"])
    assert response.status_code == 302
    assert response.headers["Location"] == "https://www.swinburne.edu.au"


def test_following_a_link_counts_clicks(shortener_app):
    alice = logged_in(shortener_app)
    link = make_link(alice)
    visitor = shortener_app.test_client()
    visitor.get("/s/" + link["short_code"])
    visitor.get("/s/" + link["short_code"])
    assert alice.get("/api/links").get_json()[0]["clicks"] == 2


def test_unknown_short_code_returns_404(shortener_app):
    visitor = shortener_app.test_client()
    assert visitor.get("/s/zzzzzz").status_code == 404




def test_users_only_see_their_own_links(shortener_app):
    alice = logged_in(shortener_app, "alice")
    bob = logged_in(shortener_app, "bob")
    make_link(alice, "https://example.com/alice")
    assert bob.get("/api/links").get_json() == []
    assert len(alice.get("/api/links").get_json()) == 1


def test_owner_can_delete_a_link(shortener_app):
    alice = logged_in(shortener_app)
    link = make_link(alice)
    assert alice.post(f"/links/{link['id']}/delete").status_code == 302
    assert alice.get("/api/links").get_json() == []
    assert shortener_app.test_client().get("/s/" + link["short_code"]).status_code == 404


def test_user_cannot_delete_another_users_link(shortener_app):
    alice = logged_in(shortener_app, "alice")
    bob = logged_in(shortener_app, "bob")
    link = make_link(alice)
    assert bob.post(f"/links/{link['id']}/delete").status_code == 404
    assert len(alice.get("/api/links").get_json()) == 1

def test_home_page_for_visitors_is_the_register_page(shortener_app):
    response = shortener_app.test_client().get("/")
    assert response.status_code == 200
    assert b"Create an account" in response.data
    assert b'action="/register"' in response.data 

def test_registering_from_the_home_page_lands_on_the_shortener(shortener_app):
    visitor = shortener_app.test_client()
    response = visitor.post("/register", data={"username": "newuser", "password": "password123"})
    assert response.headers["Location"] == "/"
    page = visitor.get("/")
    assert b"logout-button" in page.data  

# ---- homepage ----

def test_home_page_for_visitors_is_the_register_page(shortener_app):
    response = shortener_app.test_client().get("/")
    assert response.status_code == 200
    assert b"Create an account" in response.data
    assert b'action="/register"' in response.data      


def test_registering_from_the_home_page_lands_on_the_shortener(shortener_app):
    visitor = shortener_app.test_client()
    response = visitor.post("/register", data={"username": "newuser", "password": "password123"})
    assert response.headers["Location"] == "/"
    page = visitor.get("/")
    assert b"logout-button" in page.data                


def test_home_page_shows_the_links_when_logged_in(shortener_app):
    alice = logged_in(shortener_app)
    make_link(alice, "https://example.com/on-home")
    response = alice.get("/")
    assert response.status_code == 200
    assert b"https://example.com/on-home" in response.data