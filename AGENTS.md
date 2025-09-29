# Repository Guidelines

## Project Structure & Module Organization
- `src/main.py`: FastAPI entrypoint registering routers and templates.
- `src/api/`: REST endpoints (auth, inventory, materials, production_schedule, material_management, etc.).
- `src/templates/` & `src/static/`: Jinja2 pages and Tailwind-based assets.
- `src/db/`: SQLAlchemy models, session helpers, and bootstrap scripts.
- `src/utils/`: Shared utilities (auth helpers, token handling).
- Root scripts such as `run.py`, `reset_db.py`, and `analyze_excel.py` support local tooling.

## Build, Test, and Development Commands
- `python -m venv .venv` then `pip install -r requirements.txt`: create and populate the virtual environment.
- `uvicorn src.main:app --reload`: launch the FastAPI server with hot reload (default port 8000).
- `python run.py`: alternative launcher that applies project defaults from `src/config.py`.
- `pytest`: execute the automated test suite (add `-q` for terse output).
- `python reset_db.py`: rebuild development tables; run only on disposable databases.

## Coding Style & Naming Conventions
- Follow PEP 8 with 4-space indentation; prefer explicit imports over `*`.
- Name modules and files in `snake_case`; Jinja templates mirror route names.
- Keep routers under `src/api/` prefixed with resource nouns (e.g., `materials`, `inventory`).
- Use type hints for public functions; run `ruff` or `flake8` if configured locally.

## Testing Guidelines
- Adopt `pytest` for unit and integration tests; place new tests under `tests/` mirroring `src/` structure.
- Name test modules `test_*.py` and functions `test_<feature>_<scenario>`.
- Ensure critical branches (auth, ordering, inventory) have regression coverage before merging.

## Commit & Pull Request Guidelines
- Prefer Conventional Commits (e.g., `feat:`, `fix:`, `chore:`) as seen in repository history.
- Write present-tense, descriptive summaries; include linked issue IDs when applicable.
- Pull requests should describe scope, testing evidence, and screenshots/GIFs for UI changes.
- Request review when CI (lint + pytest) is green; update PR body if requirements shift.

## Security & Configuration Tips
- Never commit `.env` or secrets; use `.env.example` as the template.
- Review `src/config.py` before deploying—environment variables override defaults.
- Restrict database reset scripts to non-production environments.
