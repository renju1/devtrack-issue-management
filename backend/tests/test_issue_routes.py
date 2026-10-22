import os
import unittest
from unittest.mock import patch

os.environ["JWT_SECRET_KEY"] = "test-only-secret-key-for-route-tests"
os.environ["DB_PASSWORD"] = "test-only-password"

import app as app_module
from flask_jwt_extended import create_access_token


class FakeCursor:
    def __init__(self, fetchone_results=()):
        self.fetchone_results = list(fetchone_results)
        self.fetchall_result = []
        self.executions = []
        self.rowcount = 1
        self.lastrowid = 88

    def execute(self, query, params=()):
        self.executions.append((query, params))

    def fetchone(self):
        if self.fetchone_results:
            return self.fetchone_results.pop(0)
        return None

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


class IssueRouteTests(unittest.TestCase):
    def setUp(self):
        app_module.app.config.update(TESTING=True)
        self.client = app_module.app.test_client()

    def auth_headers(self, user_id=41, role="tester"):
        with app_module.app.app_context():
            token = create_access_token(
                identity=str(user_id),
                additional_claims={"role": role},
            )
        return {"Authorization": f"Bearer {token}"}

    def test_tester_issue_list_is_scoped_to_jwt_user_and_combines_filters(self):
        cursor = FakeCursor()
        connection = FakeConnection(cursor)
        with patch.object(app_module, "get_db_connection", return_value=connection):
            response = self.client.get(
                "/api/issues?status=Open&priority=High&date_range=10",
                headers=self.auth_headers(user_id=41),
            )

        self.assertEqual(response.status_code, 200)
        query, params = cursor.executions[0]
        self.assertIn("i.created_by_user_id = %s", query)
        self.assertIn("i.status = %s", query)
        self.assertIn("i.priority = %s", query)
        self.assertIn("i.created_at >= CURRENT_TIMESTAMP", query)
        self.assertEqual(params, (41, "Open", "High", 10))

    def test_my_issues_endpoint_uses_jwt_owner_and_rejects_other_roles(self):
        cursor = FakeCursor()
        connection = FakeConnection(cursor)
        with patch.object(app_module, "get_db_connection", return_value=connection):
            response = self.client.get(
                "/api/my/issues", headers=self.auth_headers(user_id=52)
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(cursor.executions[0][1], (52,))

        with patch.object(app_module, "get_db_connection") as connect:
            forbidden = self.client.get(
                "/api/my/issues", headers=self.auth_headers(role="developer")
            )
        self.assertEqual(forbidden.status_code, 403)
        connect.assert_not_called()

    def test_tester_issue_detail_is_scoped_by_jwt_owner(self):
        cursor = FakeCursor(fetchone_results=[None])
        connection = FakeConnection(cursor)
        with patch.object(app_module, "get_db_connection", return_value=connection):
            response = self.client.get(
                "/api/issues/73", headers=self.auth_headers(user_id=41)
            )

        self.assertEqual(response.status_code, 404)
        query, params = cursor.executions[0]
        self.assertIn("i.created_by_user_id = %s", query)
        self.assertEqual(params, (73, 41))

    def test_issue_creation_rejects_unknown_project(self):
        cursor = FakeCursor(fetchone_results=[None])
        connection = FakeConnection(cursor)
        payload = {
            "title": "Example",
            "description": "Description",
            "priority": "Medium",
            "project_id": 999,
        }
        with patch.object(app_module, "get_db_connection", return_value=connection):
            response = self.client.post(
                "/api/issues", json=payload, headers=self.auth_headers()
            )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(len(cursor.executions), 1)
        self.assertIn("FROM projects", cursor.executions[0][0])
        self.assertFalse(connection.committed)

    def test_issue_creation_stores_creator_from_jwt(self):
        cursor = FakeCursor(fetchone_results=[{"project_id": 7, "name": "Core"}])
        connection = FakeConnection(cursor)
        payload = {
            "title": "Example",
            "description": "Description",
            "priority": "High",
            "project_id": "7",
        }
        with patch.object(app_module, "get_db_connection", return_value=connection):
            response = self.client.post(
                "/api/issues", json=payload, headers=self.auth_headers(user_id=41)
            )

        self.assertEqual(response.status_code, 201)
        self.assertTrue(connection.committed)
        insert_query, insert_params = cursor.executions[1]
        self.assertIn("created_by_user_id", insert_query)
        self.assertEqual(insert_params, ("Example", "Description", "High", 7, 41))
        self.assertEqual(response.get_json()["project_name"], "Core")

    def test_comments_require_authentication(self):
        with patch.object(app_module, "get_db_connection") as connect:
            response = self.client.get("/api/issues/73/comments")
            post_response = self.client.post(
                "/api/issues/73/comments", json={"comment_text": "Hello"}
            )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(post_response.status_code, 401)
        connect.assert_not_called()

    def test_tester_comment_access_is_scoped_to_jwt_owner(self):
        cursor = FakeCursor(fetchone_results=[None])
        connection = FakeConnection(cursor)
        with patch.object(app_module, "get_db_connection", return_value=connection):
            response = self.client.get(
                "/api/issues/73/comments", headers=self.auth_headers(user_id=41)
            )
        self.assertEqual(response.status_code, 404)
        self.assertIn("created_by_user_id = %s", cursor.executions[0][0])
        self.assertEqual(cursor.executions[0][1], (73, 41))

    def test_developer_comment_access_is_scoped_to_assigned_user(self):
        cursor = FakeCursor(fetchone_results=[None])
        connection = FakeConnection(cursor)
        with patch.object(app_module, "get_db_connection", return_value=connection):
            response = self.client.get(
                "/api/issues/73/comments",
                headers=self.auth_headers(user_id=42, role="developer"),
            )
        self.assertEqual(response.status_code, 404)
        self.assertIn("assigned_developer_id = %s", cursor.executions[0][0])
        self.assertEqual(cursor.executions[0][1], (73, 42))

    def test_empty_comment_is_rejected(self):
        with patch.object(app_module, "get_db_connection") as connect:
            response = self.client.post(
                "/api/issues/73/comments",
                json={"comment_text": " \n  "},
                headers=self.auth_headers(),
            )
        self.assertEqual(response.status_code, 400)
        connect.assert_not_called()

    def test_comment_rejects_excessive_length_and_client_author_id(self):
        with patch.object(app_module, "get_db_connection") as connect:
            too_long = self.client.post(
                "/api/issues/73/comments",
                json={"comment_text": "x" * 5001},
                headers=self.auth_headers(),
            )
            supplied_author = self.client.post(
                "/api/issues/73/comments",
                json={"comment_text": "Hello", "user_id": 999},
                headers=self.auth_headers(),
            )
        self.assertEqual(too_long.status_code, 400)
        self.assertEqual(supplied_author.status_code, 400)
        connect.assert_not_called()

    def test_nonexistent_issue_comment_is_not_created(self):
        cursor = FakeCursor(fetchone_results=[None])
        connection = FakeConnection(cursor)
        with patch.object(app_module, "get_db_connection", return_value=connection):
            response = self.client.post(
                "/api/issues/73/comments",
                json={"comment_text": "A comment"},
                headers=self.auth_headers(user_id=41),
            )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(len(cursor.executions), 1)
        self.assertFalse(connection.committed)

    def test_missing_comments_table_returns_actionable_unavailable_response(self):
        db_error = app_module.mysql.connector.Error(
            msg="Table 'devtrack_db.issue_comments' doesn't exist",
            errno=1146,
            sqlstate="42S02",
        )

        class MissingCommentsCursor(FakeCursor):
            def execute(self, query, params=()):
                super().execute(query, params)
                if query.startswith("INSERT INTO issue_comments"):
                    raise db_error

        cursor = MissingCommentsCursor(fetchone_results=[{"issue_id": 73}])
        connection = FakeConnection(cursor)
        with patch.object(app_module, "get_db_connection", return_value=connection):
            response = self.client.post(
                "/api/issues/73/comments",
                json={"comment_text": "A comment"},
                headers=self.auth_headers(user_id=41),
            )
        self.assertEqual(response.status_code, 503)
        self.assertIn("003_add_issue_comments.sql", response.get_json()["error"])
        self.assertTrue(connection.rolled_back)

    def test_valid_comment_creation_uses_jwt_author(self):
        cursor = FakeCursor(fetchone_results=[
            {"issue_id": 73},
            {
                "comment_id": 88, "issue_id": 73, "user_id": 41,
                "username": "tester", "comment_text": "Looks good",
                "created_at": "2026-10-22 10:00:00",
            },
        ])
        connection = FakeConnection(cursor)
        with patch.object(app_module, "get_db_connection", return_value=connection):
            response = self.client.post(
                "/api/issues/73/comments",
                json={"comment_text": "  Looks good  "},
                headers=self.auth_headers(user_id=41),
            )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(connection.committed)
        insert_query, insert_params = cursor.executions[1]
        self.assertIn("INSERT INTO issue_comments", insert_query)
        self.assertEqual(insert_params, (73, 41, "Looks good"))
        self.assertEqual(response.get_json()["comment"]["username"], "tester")

    def test_comment_retrieval_returns_chronological_comments(self):
        cursor = FakeCursor(fetchone_results=[{"issue_id": 73}])
        cursor.fetchall_result = [
            {"comment_id": 1, "username": "tester", "comment_text": "First"},
            {"comment_id": 2, "username": "developer", "comment_text": "Second"},
        ]
        connection = FakeConnection(cursor)
        with patch.object(app_module, "get_db_connection", return_value=connection):
            response = self.client.get(
                "/api/issues/73/comments", headers=self.auth_headers(role="admin")
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [comment["comment_text"] for comment in response.get_json()["comments"]],
            ["First", "Second"],
        )
        comments_query, params = cursor.executions[1]
        self.assertIn("ORDER BY c.created_at ASC, c.comment_id ASC", comments_query)
        self.assertEqual(params, (73,))


if __name__ == "__main__":
    unittest.main()
