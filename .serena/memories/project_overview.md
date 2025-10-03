# Project Overview
- **Name**: 材料管理システム (matemane)
- **Purpose**: Hybrid count/weight inventory management for lathe bar stock, covering ordering, receiving, stock control, traceability, and Excel-based scheduling/inventory reconciliation.
- **Tech Stack**: Python 3.12, FastAPI, SQLAlchemy, MySQL 8, Jinja2 templates with Tailwind CSS and vanilla JS; JWT auth (present but optional).
- **Architecture**: FastAPI app in `src/main.py`, Pydantic settings in `src/config.py`, SQLAlchemy models in `src/db/models.py`, API routers under `src/api/`, templates in `src/templates/`, static assets in `src/static/`, utilities in `src/utils/`.
- **Key Features**: Material master management with CSV import (two formats), purchase order & receiving flow with UUID labels, inventory querying and movements, density presets, production scheduling via Excel, Excel inventory viewer.
- **Current Status**: Most APIs and UI implemented; movements and labels APIs still stubs; automated tests largely absent.