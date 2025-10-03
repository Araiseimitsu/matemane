# Code Style & Conventions
- **Backend**: Python 3.12 with FastAPI and SQLAlchemy models; follow existing module patterns in `src/api/` and `src/db/`. Use descriptive snake_case for functions/variables; leverage Pydantic schemas and dependency injection conventions already present.
- **Routing**: Ensure all API endpoints end with a trailing slash to avoid 307 redirect issues (`/api/.../`).
- **Templates/JS**: Jinja2 templates under `src/templates/` and Tailwind-based styling; extend `base.html`/`dashboard.html` scripts for UI changes; keep JS within established modules (`src/static/js/api-client.js`, `utils.js`, `qr-scanner.js`).
- **Database Rules**: MySQL only (no SQLite); lengths in millimeters; maintain usage_type propagation (material → PO item → receiving); adhere to existing enums and relationships in models.
- **Comments/Docs**: Minimal necessary comments; follow existing style without excessive inline documentation.