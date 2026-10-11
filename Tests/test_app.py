from app import app

def test_health():
    client = app.test_client()
    assert client.get("/health").status_code == 200

def test_index():
    client = app.test_client()
    assert client.get("/").status_code == 200