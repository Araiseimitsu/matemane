# Task Completion Checklist
- Run relevant tests (`pytest`, targeted files, or coverage) and ensure they pass.
- If database schema/data touched, consider running `python reset_db.py` locally to verify integrity.
- Start/verify FastAPI app with `python run.py` or `uvicorn ...` when changes impact runtime behavior.
- Check for trailing slash compliance on new API routes.
- Review for secrets or environment-specific values before committing.
- Summarize changes and confirm no outstanding TODOs remain.