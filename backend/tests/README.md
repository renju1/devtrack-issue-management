# Backend tests

The Pytest suite contains Flask route unit tests. Database connections are replaced with fake cursors/connections or a failure stub, so the tests do not connect to MySQL. There are currently no live-database integration tests.

From the `backend` directory, install the declared dependencies and run:

```powershell
python -m pip install -r requirements.txt
python -m pytest -q
```

On Windows, the project's virtual environment can be used instead:

```powershell
.\venv\Scripts\python.exe -m pytest -q
```
