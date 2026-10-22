import pytest

import app as app_module


class FakeCursor:
    def __init__(self, fetchone_results=(), fetchall_result=(), rowcount=1):
        self.fetchone_results = list(fetchone_results)
        self.fetchall_result = list(fetchall_result)
        self.rowcount = rowcount
        self.lastrowid = 88
        self.executions = []

    def execute(self, query, params=()):
        self.executions.append((query, params))

    def fetchone(self):
        return self.fetchone_results.pop(0) if self.fetchone_results else None

    def fetchall(self):
        return self.fetchall_result

    def close(self):
        pass


class FakeConnection:
    def __init__(self, cursor):
        self.fake_cursor = cursor
        self.committed = False
        self.rolled_back = False

    def cursor(self, dictionary=False):
        return self.fake_cursor

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def is_connected(self):
        return True

    def close(self):
        pass


@pytest.fixture
def fake_db(monkeypatch):
    def install(cursor):
        connection = FakeConnection(cursor)
        monkeypatch.setattr(app_module, "get_db_connection", lambda: connection)
        return connection

    return install


def test_login_success_returns_safe_user_and_token(client, monkeypatch, fake_db):
    cursor = FakeCursor(fetchone_results=[{
        "user_id": 41,
        "username": "pytest_tester",
        "password_hash": "not-a-real-password-hash",
        "role": "tester",
    }])
    fake_db(cursor)
    monkeypatch.setattr(app_module, "check_password_hash", lambda stored, supplied: (
        stored == "not-a-real-password-hash" and supplied == "test-password"
    ))

    response = client.post("/api/login", json={
        "username": "pytest_tester",
        "password": "test-password",
    })

    assert response.status_code == 200
    body = response.get_json()
    assert body["access_token"]
    assert body["user"] == {
        "user_id": 41,
        "username": "pytest_tester",
        "role": "tester",
    }
    assert "password_hash" not in body


@pytest.mark.parametrize("user", [None, {
    "user_id": 41,
    "username": "pytest_tester",
    "password_hash": "not-a-real-password-hash",
    "role": "tester",
}])
def test_login_rejects_unknown_user_or_invalid_password(
    client, monkeypatch, fake_db, user
):
    fake_db(FakeCursor(fetchone_results=[user]))
    monkeypatch.setattr(app_module, "check_password_hash", lambda *_: False)

    response = client.post("/api/login", json={
        "username": "pytest_tester",
        "password": "wrong-password",
    })

    assert response.status_code == 401
    assert "access_token" not in response.get_json()


def test_issue_list_requires_authentication(client, monkeypatch):
    def unexpected_database_access():
        pytest.fail("Unauthenticated request must not reach the database")

    monkeypatch.setattr(app_module, "get_db_connection", unexpected_database_access)
    response = client.get("/api/issues")
    assert response.status_code == 401


@pytest.mark.parametrize(("role", "user_id", "expected_scope"), [
    ("developer", 42, "WHERE i.assigned_developer_id = %s"),
    ("admin", 7, ""),
])
def test_issue_list_keeps_role_specific_visibility(
    client, auth_headers, fake_db, role, user_id, expected_scope
):
    cursor = FakeCursor()
    fake_db(cursor)

    response = client.get(
        "/api/issues", headers=auth_headers(user_id=user_id, role=role)
    )

    assert response.status_code == 200
    query, params = cursor.executions[0]
    if expected_scope:
        assert expected_scope in query
        assert params == (user_id,)
    else:
        assert "WHERE" not in query
        assert params == ()


@pytest.mark.parametrize("role", ["developer", "admin"])
def test_only_testers_can_create_issues(client, auth_headers, monkeypatch, role):
    def unexpected_database_access():
        pytest.fail("Forbidden issue creation must not reach the database")

    monkeypatch.setattr(app_module, "get_db_connection", unexpected_database_access)
    response = client.post(
        "/api/issues",
        json={"title": "Issue", "description": "Details", "project_id": 7},
        headers=auth_headers(role=role),
    )
    assert response.status_code == 403


@pytest.mark.parametrize("payload", [
    {"description": "Details", "project_id": 7},
    {"title": "  ", "description": "Details", "project_id": 7},
    {"title": "x" * 151, "description": "Details", "project_id": 7},
    {"title": "Issue", "description": " ", "project_id": 7},
    {"title": "Issue", "description": "Details", "priority": "Urgent", "project_id": 7},
    {"title": "Issue", "description": "Details", "project_id": "not-an-id"},
])
def test_issue_creation_rejects_invalid_fields_before_database(
    client, auth_headers, monkeypatch, payload
):
    def unexpected_database_access():
        pytest.fail("Invalid issue input must be rejected before database access")

    monkeypatch.setattr(app_module, "get_db_connection", unexpected_database_access)
    response = client.post("/api/issues", json=payload, headers=auth_headers())
    assert response.status_code == 400


def test_assigned_developer_can_update_status(client, auth_headers, fake_db):
    updated_issue = {"issue_id": 73, "status": "In Progress"}
    cursor = FakeCursor(fetchone_results=[updated_issue])
    connection = fake_db(cursor)

    response = client.put(
        "/api/issues/73",
        json={"status": "In Progress"},
        headers=auth_headers(user_id=42, role="developer"),
    )

    assert response.status_code == 200
    assert response.get_json()["issue"] == updated_issue
    assert cursor.executions[0][1] == ("In Progress", 73, 42)
    assert "assigned_developer_id = %s" in cursor.executions[0][0]
    assert connection.committed


def test_invalid_status_is_rejected_before_database(client, auth_headers, monkeypatch):
    def unexpected_database_access():
        pytest.fail("Invalid status must be rejected before database access")

    monkeypatch.setattr(app_module, "get_db_connection", unexpected_database_access)
    response = client.put(
        "/api/issues/73",
        json={"status": "Reopened"},
        headers=auth_headers(user_id=42, role="developer"),
    )
    assert response.status_code == 400


@pytest.mark.parametrize("role", ["tester", "admin"])
def test_only_developers_can_update_issue_status(
    client, auth_headers, monkeypatch, role
):
    def unexpected_database_access():
        pytest.fail("Forbidden status update must not reach the database")

    monkeypatch.setattr(app_module, "get_db_connection", unexpected_database_access)
    response = client.put(
        "/api/issues/73",
        json={"status": "Closed"},
        headers=auth_headers(role=role),
    )
    assert response.status_code == 403


def test_developer_cannot_update_unassigned_issue(client, auth_headers, fake_db):
    cursor = FakeCursor(fetchone_results=[None], rowcount=0)
    connection = fake_db(cursor)

    response = client.put(
        "/api/issues/73",
        json={"status": "Closed"},
        headers=auth_headers(user_id=42, role="developer"),
    )

    assert response.status_code == 404
    assert cursor.executions[0][1] == ("Closed", 73, 42)
    assert cursor.executions[1][1] == (73, 42)
    assert not connection.committed


@pytest.mark.parametrize("role", ["tester", "developer"])
def test_only_admins_can_assign_issues(client, auth_headers, monkeypatch, role):
    def unexpected_database_access():
        pytest.fail("Forbidden assignment must not reach the database")

    monkeypatch.setattr(app_module, "get_db_connection", unexpected_database_access)
    response = client.patch(
        "/api/issues/73/assignee",
        json={"assignee_user_id": 55},
        headers=auth_headers(role=role),
    )
    assert response.status_code == 403


@pytest.mark.parametrize("role", ["tester", "developer"])
def test_only_admins_can_delete_issues(client, auth_headers, monkeypatch, role):
    def unexpected_database_access():
        pytest.fail("Forbidden issue deletion must not reach the database")

    monkeypatch.setattr(app_module, "get_db_connection", unexpected_database_access)
    response = client.delete(
        "/api/issues/73", headers=auth_headers(role=role)
    )
    assert response.status_code == 403


def test_admin_can_assign_valid_developer(client, auth_headers, fake_db):
    cursor = FakeCursor(fetchone_results=[{"username": "pytest_developer"}])
    connection = fake_db(cursor)

    response = client.patch(
        "/api/issues/73/assignee",
        json={"assignee_user_id": 55},
        headers=auth_headers(role="admin"),
    )

    assert response.status_code == 200
    assert response.get_json()["assigned_developer"] == "pytest_developer"
    assert cursor.executions[0][1] == (55,)
    assert "role = 'developer'" in cursor.executions[0][0]
    assert cursor.executions[1][1] == (55, "pytest_developer", 73)
    assert connection.committed


def test_admin_cannot_assign_non_developer_account(client, auth_headers, fake_db):
    cursor = FakeCursor(fetchone_results=[None])
    connection = fake_db(cursor)

    response = client.patch(
        "/api/issues/73/assignee",
        json={"assignee_user_id": 55},
        headers=auth_headers(role="admin"),
    )

    assert response.status_code == 404
    assert len(cursor.executions) == 1
    assert not connection.committed


def test_database_failure_returns_api_error_without_leaking_details(
    client, auth_headers, monkeypatch
):
    def database_failure():
        raise app_module.mysql.connector.Error("private database detail")

    monkeypatch.setattr(app_module, "get_db_connection", database_failure)
    response = client.get("/api/issues", headers=auth_headers(role="admin"))

    assert response.status_code == 500
    assert response.get_json() == {"error": "Could not retrieve issues"}
