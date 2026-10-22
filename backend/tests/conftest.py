import os

import pytest
from flask_jwt_extended import create_access_token


# Ensure importing the Flask app never reads a developer's real credentials.
os.environ["JWT_SECRET_KEY"] = "devtrack-pytest-only-jwt-signing-key-32-bytes-minimum"
os.environ["DB_PASSWORD"] = "devtrack-pytest-only-db-password"

import app as app_module


@pytest.fixture
def client():
    previous_testing = app_module.app.config.get("TESTING")
    app_module.app.config["TESTING"] = True
    try:
        yield app_module.app.test_client()
    finally:
        app_module.app.config["TESTING"] = previous_testing


@pytest.fixture(autouse=True)
def prohibit_real_database_access(monkeypatch):
    def fail_on_real_database_access():
        pytest.fail("A backend unit test attempted unmocked database access")

    monkeypatch.setattr(
        app_module, "get_db_connection", fail_on_real_database_access
    )


@pytest.fixture
def auth_headers():
    def make_headers(user_id=41, role="tester"):
        with app_module.app.app_context():
            token = create_access_token(
                identity=str(user_id),
                additional_claims={"role": role},
            )
        return {"Authorization": f"Bearer {token}"}

    return make_headers
