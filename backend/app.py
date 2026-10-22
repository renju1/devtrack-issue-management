
import os
import mysql.connector
from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask_cors import CORS
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.exceptions import HTTPException
from flask_jwt_extended import (
    JWTManager,
    create_access_token,
    jwt_required,
    get_jwt_identity,
    get_jwt
)

load_dotenv()

required_secrets = ("JWT_SECRET_KEY", "DB_PASSWORD")
missing_secrets = [
    name for name in required_secrets if not os.getenv(name, "").strip()
]
if missing_secrets:
    raise RuntimeError(
        "Missing required environment variable(s): "
        + ", ".join(missing_secrets)
        + ". Set them in backend/.env or the process environment."
    )

app = Flask(__name__)
cors_origins = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    ).split(",")
    if origin.strip()
]
CORS(app, resources={r"/api/*": {"origins": cors_origins}})


@app.errorhandler(HTTPException)
def handle_api_http_error(error):
    if request.path.startswith("/api/"):
        return jsonify({"error": error.description}), error.code
    return error

app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET_KEY")
jwt = JWTManager(app)


def get_db_connection():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "3306")),
        user=os.getenv("DB_USER", "root"),
        password=os.environ["DB_PASSWORD"],
        database=os.getenv("DB_NAME", "devtrack_db"),
    )
@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}

    username = data.get("username", "").strip()
    password = data.get("password", "")

    if not username or not password:
        return jsonify({"error": "Username and password are required"}), 400

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            "SELECT user_id, username, password_hash, role "
            "FROM users WHERE username = %s",
            (username,)
        )
        user = cursor.fetchone()

        if not user or not check_password_hash(
            user["password_hash"], password
        ):
            return jsonify({"error": "Invalid username or password"}), 401

        access_token = create_access_token(
            identity=str(user["user_id"]),
            additional_claims={"role": user["role"]}
        )

        return jsonify({
            "message": "Login successful",
            "access_token": access_token,
            "user": {
                "user_id": user["user_id"],
                "username": user["username"],
                "role": user["role"]
            }
        }), 200

    except Exception:
        app.logger.exception("Login failed")
        return jsonify({"error": "Unable to process login"}), 500

    finally:
        if cursor is not None:
            cursor.close()
        if connection is not None and connection.is_connected():
            connection.close()

@app.route("/api/users", methods=["GET"])
@jwt_required()
def get_users():
    if get_jwt().get("role") != "admin":
        return jsonify({"error": "Only admins can view users"}), 403

    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            "SELECT user_id, username, role FROM users ORDER BY user_id"
        )
        return jsonify({"users": cursor.fetchall()}), 200
    except mysql.connector.Error:
        app.logger.exception("Database error while fetching users")
        return jsonify({"error": "Could not retrieve users"}), 500
    finally:
        if cursor is not None:
            cursor.close()
        if connection is not None and connection.is_connected():
            connection.close()


@app.route("/api/users", methods=["POST"])
@jwt_required()
def create_user():
    if get_jwt().get("role") != "admin":
        return jsonify({"error": "Only admins can create users"}), 403

    data = request.get_json(silent=True)
    if not isinstance(data, dict) or set(data) != {"username", "password", "role"}:
        return jsonify({
            "error": "Username, password, and role are required"
        }), 400

    username = data["username"]
    password = data["password"]
    role = data["role"]
    if not isinstance(username, str) or not username.strip():
        return jsonify({"error": "Username is required"}), 400
    username = username.strip()
    if not isinstance(password, str) or not password.strip():
        return jsonify({"error": "Password is required"}), 400
    if role not in ("tester", "developer", "admin"):
        return jsonify({"error": "Role must be tester, developer, or admin"}), 400

    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            "SELECT user_id FROM users WHERE username = %s",
            (username,)
        )
        if cursor.fetchone() is not None:
            return jsonify({"error": "Username already exists"}), 409

        password_hash = generate_password_hash(password)
        cursor.execute(
            "INSERT INTO users (username, password_hash, role) "
            "VALUES (%s, %s, %s)",
            (username, password_hash, role)
        )
        user_id = cursor.lastrowid
        connection.commit()
        return jsonify({
            "message": "User created successfully",
            "user": {"user_id": user_id, "username": username, "role": role}
        }), 201
    except mysql.connector.IntegrityError as error:
        if connection is not None:
            connection.rollback()
        if error.errno == 1062:
            return jsonify({"error": "Username already exists"}), 409
        app.logger.exception("Database integrity error while creating user")
        return jsonify({"error": "Could not create user"}), 500
    except mysql.connector.Error:
        if connection is not None:
            connection.rollback()
        app.logger.exception("Database error while creating user")
        return jsonify({"error": "Could not create user"}), 500
    finally:
        if cursor is not None:
            cursor.close()
        if connection is not None and connection.is_connected():
            connection.close()


@app.route("/api/users/<int:user_id>", methods=["DELETE"])
@jwt_required()
def delete_user(user_id):
    if get_jwt().get("role") != "admin":
        return jsonify({"error": "Only admins can delete users"}), 403
    if user_id < 1:
        return jsonify({"error": "Invalid user ID"}), 400

    try:
        current_user_id = int(get_jwt_identity())
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid authenticated user"}), 401
    if user_id == current_user_id:
        return jsonify({"error": "You cannot delete your own account"}), 409

    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        connection.start_transaction()
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            "SELECT user_id, role FROM users WHERE user_id = %s FOR UPDATE",
            (user_id,)
        )
        target_user = cursor.fetchone()
        if target_user is None:
            connection.rollback()
            return jsonify({"error": "User not found"}), 404

        if target_user["role"] == "admin":
            cursor.execute(
                "SELECT user_id FROM users WHERE role = 'admin' FOR UPDATE"
            )
            if len(cursor.fetchall()) <= 1:
                connection.rollback()
                return jsonify({"error": "Cannot delete the last admin account"}), 409

        cursor.execute(
            "SELECT issue_id FROM issues "
            "WHERE assigned_developer_id = %s LIMIT 1 FOR UPDATE",
            (user_id,)
        )
        if cursor.fetchone() is not None:
            connection.rollback()
            return jsonify({
                "error": "Reassign or unassign this user's issues before deleting the account"
            }), 409

        cursor.execute("DELETE FROM users WHERE user_id = %s", (user_id,))
        if cursor.rowcount == 0:
            connection.rollback()
            return jsonify({"error": "User not found"}), 404

        connection.commit()
        return jsonify({
            "message": "User deleted successfully",
            "user_id": user_id
        }), 200
    except mysql.connector.IntegrityError as error:
        if connection is not None:
            connection.rollback()
        if error.errno == 1451:
            return jsonify({
                "error": "Cannot delete this account while it is referenced by existing records"
            }), 409
        app.logger.exception("Database integrity error while deleting user")
        return jsonify({"error": "Could not delete user"}), 500
    except mysql.connector.Error:
        if connection is not None:
            connection.rollback()
        app.logger.exception("Database error while deleting user")
        return jsonify({"error": "Could not delete user"}), 500
    finally:
        if cursor is not None:
            cursor.close()
        if connection is not None and connection.is_connected():
            connection.close()


@app.route("/api/health", methods=["GET"])
def health_check():
    return jsonify({
        "status": "success",
        "message": "DevTrack API is running!"
    }), 200


@app.route("/api/projects", methods=["GET"])
@jwt_required()
def get_projects():
    if get_jwt().get("role") not in ("tester", "developer", "admin"):
        return jsonify({"error": "Invalid user role"}), 403

    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT project_id, name FROM projects ORDER BY name")
        return jsonify({"projects": cursor.fetchall()}), 200
    except mysql.connector.Error:
        app.logger.exception("Database error while fetching projects")
        return jsonify({"error": "Could not retrieve projects"}), 500
    finally:
        if cursor is not None:
            cursor.close()
        if connection is not None and connection.is_connected():
            connection.close()


@app.route("/api/projects", methods=["POST"])
@jwt_required()
def create_project():
    if get_jwt().get("role") != "admin":
        return jsonify({"error": "Only admins can create projects"}), 403

    data = request.get_json(silent=True)
    if not isinstance(data, dict) or set(data) != {"name"}:
        return jsonify({"error": "Project name is required"}), 400
    name = data["name"]
    if not isinstance(name, str) or not name.strip():
        return jsonify({"error": "Project name is required"}), 400
    name = name.strip()
    if len(name) > 100:
        return jsonify({"error": "Project name cannot exceed 100 characters"}), 400

    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT project_id FROM projects WHERE name = %s", (name,))
        if cursor.fetchone() is not None:
            return jsonify({"error": "Project already exists"}), 409
        cursor.execute("INSERT INTO projects (name) VALUES (%s)", (name,))
        project_id = cursor.lastrowid
        connection.commit()
        return jsonify({
            "message": "Project created successfully",
            "project": {"project_id": project_id, "name": name}
        }), 201
    except mysql.connector.IntegrityError as error:
        if connection is not None:
            connection.rollback()
        if error.errno == 1062:
            return jsonify({"error": "Project already exists"}), 409
        app.logger.exception("Database integrity error while creating project")
        return jsonify({"error": "Could not create project"}), 500
    except mysql.connector.Error:
        if connection is not None:
            connection.rollback()
        app.logger.exception("Database error while creating project")
        return jsonify({"error": "Could not create project"}), 500
    finally:
        if cursor is not None:
            cursor.close()
        if connection is not None and connection.is_connected():
            connection.close()


@app.route("/api/issues", methods=["POST"])
@jwt_required()
def create_issue():
    if get_jwt().get("role") != "tester":
        return jsonify({
            "error": "Only testers can create issues"
        }), 403

    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({"error": "Request body must be valid JSON"}), 400

    title = data.get("title")
    description = data.get("description")
    priority = data.get("priority", "Medium")
    raw_project_id = data.get("project_id")

    if "assigned_developer" in data or "assigned_developer_id" in data:
        return jsonify({"error": "Only admins can assign developers"}), 403

    if not isinstance(title, str) or not title.strip():
        return jsonify({"error": "Title is required"}), 400

    if len(title.strip()) > 150:
        return jsonify({"error": "Title cannot exceed 150 characters"}), 400

    if not isinstance(description, str) or not description.strip():
        return jsonify({"error": "Description is required"}), 400

    if priority not in ("Low", "Medium", "High", "Critical"):
        return jsonify({"error": "Invalid priority"}), 400
    if (isinstance(raw_project_id, bool)
            or not isinstance(raw_project_id, (int, str))
            or (isinstance(raw_project_id, str)
                and not raw_project_id.isdecimal())):
        return jsonify({"error": "A valid project is required"}), 400
    project_id = int(raw_project_id)
    if project_id < 1:
        return jsonify({"error": "A valid project is required"}), 400
    try:
        creator_user_id = int(get_jwt_identity())
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid authenticated user"}), 401

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            "SELECT project_id, name FROM projects WHERE project_id = %s",
            (project_id,)
        )
        project = cursor.fetchone()
        if project is None:
            return jsonify({"error": "Project not found"}), 400

        cursor.execute("""
            INSERT INTO issues
                (title, description, priority, project_id, created_by_user_id)
            VALUES (%s, %s, %s, %s, %s)
        """, (
            title.strip(),
            description.strip(),
            priority,
            project_id,
            creator_user_id,
        ))

        connection.commit()
        issue_id = cursor.lastrowid

        return jsonify({
            "message": "Issue created successfully",
            "issue_id": issue_id,
            "title": title.strip(),
            "description": description.strip(),
            "priority": priority,
            "project_id": project_id,
            "project_name": project["name"],
            "status": "Open",
        }), 201

    except mysql.connector.Error:
        app.logger.exception("Database error while creating issue")
        if connection is not None:
            connection.rollback()
        return jsonify({"error": "Could not create issue"}), 500

    finally:
        if cursor is not None:
            cursor.close()
        if connection is not None and connection.is_connected():
            connection.close()

@app.route("/api/issues", methods=["GET"])
@jwt_required()
def get_issues():
    role = get_jwt().get("role")
    if role not in ("tester", "developer", "admin"):
        return jsonify({"error": "Invalid user role"}), 403

    try:
        user_id = int(get_jwt_identity())
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid authenticated user"}), 401

    return _fetch_issues_for_role(role, user_id)


@app.route("/api/issues/<int:issue_id>", methods=["GET"])
@jwt_required()
def get_issue(issue_id):
    role = get_jwt().get("role")
    if role not in ("tester", "developer", "admin"):
        return jsonify({"error": "Invalid user role"}), 403
    try:
        user_id = int(get_jwt_identity())
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid authenticated user"}), 401

    conditions = ["i.issue_id = %s"]
    values = [issue_id]
    if role == "tester":
        conditions.append("i.created_by_user_id = %s")
        values.append(user_id)
    elif role == "developer":
        conditions.append("i.assigned_developer_id = %s")
        values.append(user_id)

    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute("""
            SELECT i.issue_id, i.title, i.description, i.priority, i.status,
                   i.project_id, projects.name AS project_name,
                   i.assigned_developer_id,
                   COALESCE(users.username, i.assigned_developer)
                       AS assigned_developer,
                   i.created_at, i.updated_at
            FROM issues AS i
            LEFT JOIN projects ON projects.project_id = i.project_id
            LEFT JOIN users ON users.user_id = i.assigned_developer_id
            WHERE """ + " AND ".join(conditions), tuple(values))
        issue = cursor.fetchone()
        if issue is None:
            return jsonify({"error": "Issue not found"}), 404
        return jsonify({"issue": issue}), 200
    except mysql.connector.Error:
        app.logger.exception("Database error while fetching issue")
        return jsonify({"error": "Could not retrieve issue"}), 500
    finally:
        if cursor is not None:
            cursor.close()
        if connection is not None and connection.is_connected():
            connection.close()


MAX_COMMENT_LENGTH = 5000


def _log_comment_database_error(operation, error):
    app.logger.error(
        "Issue comment %s database failure (errno=%s, sqlstate=%s)",
        operation,
        getattr(error, "errno", None),
        getattr(error, "sqlstate", None),
    )


def _is_comments_table_missing(error):
    return (
        getattr(error, "errno", None) == 1146
        and "issue_comments" in (getattr(error, "msg", "") or "")
    )


def _comment_issue_access(issue_id):
    if issue_id < 1:
        return None, None, (jsonify({"error": "Invalid issue ID"}), 400)
    role = get_jwt().get("role")
    if role not in ("tester", "developer", "admin"):
        return None, None, (jsonify({"error": "Invalid user role"}), 403)
    try:
        current_user_id = int(get_jwt_identity())
    except (TypeError, ValueError):
        return None, None, (jsonify({"error": "Invalid authenticated user"}), 401)

    conditions = ["issue_id = %s"]
    values = [issue_id]
    if role == "tester":
        conditions.append("created_by_user_id = %s")
        values.append(current_user_id)
    elif role == "developer":
        conditions.append("assigned_developer_id = %s")
        values.append(current_user_id)
    return role, current_user_id, (conditions, values)


@app.route("/api/issues/<int:issue_id>/comments", methods=["GET"])
@jwt_required()
def get_issue_comments(issue_id):
    role, user_id, access = _comment_issue_access(issue_id)
    if role is None:
        return access
    conditions, values = access
    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            "SELECT issue_id FROM issues WHERE " + " AND ".join(conditions),
            tuple(values),
        )
        if cursor.fetchone() is None:
            return jsonify({"error": "Issue not found"}), 404
        cursor.execute(
            "SELECT c.comment_id, c.issue_id, c.user_id, u.username, "
            "c.comment_text, c.created_at FROM issue_comments AS c "
            "JOIN users AS u ON u.user_id = c.user_id "
            "WHERE c.issue_id = %s "
            "ORDER BY c.created_at ASC, c.comment_id ASC",
            (issue_id,),
        )
        return jsonify({"comments": cursor.fetchall()}), 200
    except mysql.connector.Error as error:
        _log_comment_database_error("retrieval", error)
        if _is_comments_table_missing(error):
            return jsonify({
                "error": "Issue comments are not installed. Apply migration 003_add_issue_comments.sql."
            }), 503
        return jsonify({"error": "Could not retrieve comments"}), 500
    finally:
        if cursor is not None:
            cursor.close()
        if connection is not None and connection.is_connected():
            connection.close()


@app.route("/api/issues/<int:issue_id>/comments", methods=["POST"])
@jwt_required()
def create_issue_comment(issue_id):
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or set(data) != {"comment_text"}:
        return jsonify({"error": "comment_text is required"}), 400
    comment_text = data.get("comment_text")
    if not isinstance(comment_text, str) or not comment_text.strip():
        return jsonify({"error": "Comment text cannot be empty"}), 400
    comment_text = comment_text.strip()
    if len(comment_text) > MAX_COMMENT_LENGTH:
        return jsonify({"error": "Comment text must be 5000 characters or fewer"}), 400

    role, user_id, access = _comment_issue_access(issue_id)
    if role is None:
        return access
    conditions, values = access
    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            "SELECT issue_id FROM issues WHERE " + " AND ".join(conditions),
            tuple(values),
        )
        if cursor.fetchone() is None:
            return jsonify({"error": "Issue not found"}), 404
        cursor.execute(
            "INSERT INTO issue_comments (issue_id, user_id, comment_text) "
            "VALUES (%s, %s, %s)",
            (issue_id, user_id, comment_text),
        )
        comment_id = cursor.lastrowid
        cursor.execute(
            "SELECT c.comment_id, c.issue_id, c.user_id, u.username, "
            "c.comment_text, c.created_at FROM issue_comments AS c "
            "JOIN users AS u ON u.user_id = c.user_id "
            "WHERE c.comment_id = %s",
            (comment_id,),
        )
        comment = cursor.fetchone()
        if comment is None:
            return jsonify({"error": "Comment created but could not be retrieved"}), 500
        connection.commit()
        return jsonify({"message": "Comment added", "comment": comment}), 201
    except mysql.connector.Error as error:
        if connection is not None:
            connection.rollback()
        _log_comment_database_error("creation", error)
        if _is_comments_table_missing(error):
            return jsonify({
                "error": "Issue comments are not installed. Apply migration 003_add_issue_comments.sql."
            }), 503
        return jsonify({"error": "Could not create comment"}), 500
    finally:
        if cursor is not None:
            cursor.close()
        if connection is not None and connection.is_connected():
            connection.close()


@app.route("/api/my/issues", methods=["GET"])
@jwt_required()
def get_my_issues():
    if get_jwt().get("role") != "tester":
        return jsonify({"error": "Only testers can view their created issues"}), 403
    try:
        user_id = int(get_jwt_identity())
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid authenticated user"}), 401
    return _fetch_issues_for_role("tester", user_id)


def _fetch_issues_for_role(role, user_id):

    status_filter = request.args.get("status") or None
    valid_statuses = ("Open", "In Progress", "Resolved", "Closed")
    if status_filter is not None and status_filter not in valid_statuses:
        return jsonify({"error": "Invalid status filter"}), 400

    priority_filter = request.args.get("priority") or None
    valid_priorities = ("Low", "Medium", "High", "Critical")
    if priority_filter is not None and priority_filter not in valid_priorities:
        return jsonify({"error": "Invalid priority filter"}), 400

    date_range = request.args.get("date_range", "all")
    if date_range not in ("10", "30", "all"):
        return jsonify({"error": "Invalid date range"}), 400

    conditions = []
    values = []
    if role == "developer":
        conditions.append("i.assigned_developer_id = %s")
        values.append(user_id)
    elif role == "tester":
        conditions.append("i.created_by_user_id = %s")
        values.append(user_id)
    if status_filter is not None:
        conditions.append("i.status = %s")
        values.append(status_filter)
    if priority_filter is not None:
        conditions.append("i.priority = %s")
        values.append(priority_filter)
    if date_range != "all":
        conditions.append("i.created_at >= CURRENT_TIMESTAMP - INTERVAL %s DAY")
        values.append(int(date_range))

    where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT i.issue_id, i.title, i.description, i.priority,
                   i.status, i.assigned_developer_id,
                   i.project_id, projects.name AS project_name,
                   COALESCE(users.username, i.assigned_developer)
                       AS assigned_developer,
                   reporter.username AS reporter_username,
                   i.created_at, i.updated_at
            FROM issues AS i
            LEFT JOIN users
                ON users.user_id = i.assigned_developer_id
            LEFT JOIN users AS reporter
                ON reporter.user_id = i.created_by_user_id
            LEFT JOIN projects
                ON projects.project_id = i.project_id
        """ + where_clause + " ORDER BY i.created_at DESC", tuple(values))

        issues = cursor.fetchall()

        return jsonify({
            "count": len(issues),
            "issues": issues
        }), 200

    except mysql.connector.Error:
        app.logger.exception("Database error while fetching issues")
        return jsonify({"error": "Could not retrieve issues"}), 500

    finally:
        if cursor is not None:
            cursor.close()
        if connection is not None and connection.is_connected():
            connection.close()


@app.route("/api/developers", methods=["GET"])
@jwt_required()
def get_developers():
    if get_jwt().get("role") != "admin":
        return jsonify({"error": "Only admins can view developers"}), 403

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            "SELECT user_id, username FROM users "
            "WHERE role = 'developer' ORDER BY username"
        )
        return jsonify({"developers": cursor.fetchall()}), 200
    except mysql.connector.Error:
        app.logger.exception("Database error while fetching developers")
        return jsonify({"error": "Could not retrieve developers"}), 500
    finally:
        if cursor is not None:
            cursor.close()
        if connection is not None and connection.is_connected():
            connection.close()
@app.route("/api/issues/<int:issue_id>", methods=["PUT"])
@jwt_required()
def update_issue(issue_id):
    claims = get_jwt()

    if claims.get("role") != "developer":
        return jsonify({
            "error": "Only developers can update issues"
        }), 403

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Request body must be valid JSON"}), 400

    if set(data.keys()) != {"status"}:
        return jsonify({"error": "Invalid or missing update fields"}), 400

    if "status" in data and data["status"] not in (
        "Open", "In Progress", "Resolved", "Closed"
    ):
        return jsonify({"error": "Invalid status"}), 400

    developer_id = int(get_jwt_identity())
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            "UPDATE issues SET status = %s "
            "WHERE issue_id = %s AND assigned_developer_id = %s",
            (data["status"], issue_id, developer_id)
        )

        if cursor.rowcount == 0:
            cursor.execute(
                "SELECT issue_id FROM issues "
                "WHERE issue_id = %s AND assigned_developer_id = %s",
                (issue_id, developer_id)
            )
            if cursor.fetchone() is None:
                return jsonify({"error": "Issue not found"}), 404

        connection.commit()

        cursor.execute(
            "SELECT * FROM issues "
            "WHERE issue_id = %s AND assigned_developer_id = %s",
            (issue_id, developer_id)
        )
        issue = cursor.fetchone()

        return jsonify({
            "message": "Issue updated successfully",
            "issue": issue
        }), 200

    except mysql.connector.Error:
        if connection is not None:
            connection.rollback()
        app.logger.exception("Database error while updating issue")
        return jsonify({"error": "Could not update issue"}), 500

    finally:
        if cursor is not None:
            cursor.close()
        if connection is not None and connection.is_connected():
            connection.close()


@app.route("/api/issues/<int:issue_id>/assignee", methods=["PATCH"])
@jwt_required()
def assign_issue(issue_id):
    if get_jwt().get("role") != "admin":
        return jsonify({"error": "Only admins can assign issues"}), 403

    data = request.get_json(silent=True)
    if not isinstance(data, dict) or set(data.keys()) != {"assignee_user_id"}:
        return jsonify({"error": "assignee_user_id is required"}), 400

    developer_id = data["assignee_user_id"]
    if developer_id is not None:
        if (isinstance(developer_id, bool)
                or not isinstance(developer_id, (int, str))
                or (isinstance(developer_id, str)
                    and not developer_id.isdecimal())):
            return jsonify({"error": "Invalid developer"}), 400
        developer_id = int(developer_id)
        if developer_id < 1:
            return jsonify({"error": "Invalid developer"}), 400

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        username = None
        if developer_id is not None:
            cursor.execute(
                "SELECT username FROM users "
                "WHERE user_id = %s AND role = 'developer'",
                (developer_id,)
            )
            developer = cursor.fetchone()
            if developer is None:
                return jsonify({"error": "Developer not found"}), 404
            username = developer["username"]

        cursor.execute(
            "UPDATE issues SET assigned_developer_id = %s, "
            "assigned_developer = %s WHERE issue_id = %s",
            (developer_id, username, issue_id)
        )
        if cursor.rowcount == 0:
            cursor.execute(
                "SELECT issue_id FROM issues WHERE issue_id = %s",
                (issue_id,)
            )
            if cursor.fetchone() is None:
                return jsonify({"error": "Issue not found"}), 404

        connection.commit()
        return jsonify({
            "message": "Issue assignment updated successfully",
            "issue_id": issue_id,
            "assignee_user_id": developer_id,
            "assigned_developer": username,
        }), 200
    except mysql.connector.Error:
        if connection is not None:
            connection.rollback()
        app.logger.exception("Database error while assigning issue")
        return jsonify({"error": "Could not assign issue"}), 500
    finally:
        if cursor is not None:
            cursor.close()
        if connection is not None and connection.is_connected():
            connection.close()



@app.route("/api/issues/<int:issue_id>", methods=["DELETE"])
@jwt_required()
def delete_issue(issue_id):
    claims = get_jwt()

    if claims.get("role") != "admin":
        return jsonify({
            "error": "Only admins can delete issues"
        }), 403

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute(
            "DELETE FROM issues WHERE issue_id = %s",
            (issue_id,)
        )

        if cursor.rowcount == 0:
            connection.rollback()
            return jsonify({"error": "Issue not found"}), 404

        connection.commit()

        return jsonify({
            "message": "Issue deleted successfully",
            "issue_id": issue_id
        }), 200

    except mysql.connector.Error:
        if connection is not None:
            connection.rollback()

        app.logger.exception(
            "Database error while deleting issue"
        )
        return jsonify({
            "error": "Could not delete issue"
        }), 500

    finally:
        if cursor is not None:
            cursor.close()

        if connection is not None and connection.is_connected():
            connection.close()



if __name__ == "__main__":
    app.run(debug=True, port=5000)
