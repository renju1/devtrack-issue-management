# DevTrack

DevTrack uses a Flask API with MySQL and a React/Vite frontend.

## Configure the environment

Create local environment files from the examples. If `backend/.env` already exists, keep it and update only the required settings; do not replace it with the example.

In PowerShell, from the project root:

```powershell
if (-not (Test-Path backend/.env)) { Copy-Item backend/.env.example backend/.env }
if (-not (Test-Path frontend/.env)) { Copy-Item frontend/.env.example frontend/.env }
```

Set `DB_PASSWORD` and `JWT_SECRET_KEY` in `backend/.env`. The Flask app stops at startup and names any missing required variables without displaying their values. `DB_HOST`, `DB_PORT`, `DB_USER`, and `DB_NAME` can also be adjusted for the local MySQL installation.

`CORS_ORIGINS` is a comma-separated list of exact frontend origins, including scheme and port. The example allows the usual Vite development origins. For another environment, set it to the deployed frontend origin(s), for example `CORS_ORIGINS=https://devtrack.example.com`; do not include paths or trailing slashes.

`VITE_API_URL` is the full API base URL and is read by Vite at build/dev-server startup. The example points to the local Flask API. For another environment, set it in `frontend/.env` to that environment's API URL, such as `VITE_API_URL=https://api.example.com/api`, then restart Vite or rebuild the frontend. Vite variables are included in client-side code, so never put secrets in `VITE_*` variables.

## Database migration

`backend/migrations/001_add_issue_assignment.sql` assumes the existing InnoDB `issues` and `users` tables, `users.user_id` is an integer primary key, and `issues.assigned_developer` is the existing text field. It adds a nullable `assigned_developer_id` field, an index, and a foreign key; it preserves issue records and legacy assignee names. Legacy names are not mapped automatically. In the database inspected on 2026-10-22, `assigned_developer_id` and `fk_issues_assigned_developer` were present. The issue list supports status and `created_at` date filters.

### Projects and tester issue ownership

The database inspected on 2026-10-22 had three issue rows, but no `projects` table, `issues.project_id`, or issue creator column. Review `backend/migrations/002_add_projects_and_issue_ownership.sql` before applying it. In MySQL Workbench, select the intended `devtrack_db` schema, make a backup, open the migration file, verify the target schema and statements, then execute it manually. Do not apply it automatically from the application.

The migration creates the projects table and adds nullable project and creator links to `issues`. It does not update or delete existing issue rows. After applying it, start the updated backend and sign in as an admin. Open **Manage Accounts** and create the initial project; testers can then select it when creating issues. New issues receive their project and creator from a validated project selection and the authenticated JWT identity.

Existing issues keep `NULL` project and creator values. Do not assign them arbitrarily. If a reliable source identifies the correct project and reporter, review a separate explicit backfill for those specific issue IDs. Until creator ownership is safely backfilled, those legacy issues will not appear in a tester's **My Issues** list; admins can still view them, and developers continue to see issues assigned to them.

## Start the application

Ensure MySQL is running and the `devtrack_db` schema and tables are already set up. In one PowerShell terminal:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install Flask flask-cors flask-jwt-extended mysql-connector-python python-dotenv
python app.py
```

In a second terminal:

```powershell
cd frontend
npm install
npm run dev
```

Open the local URL printed by Vite. The Flask API listens on `http://127.0.0.1:5000`.
