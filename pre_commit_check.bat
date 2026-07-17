uv run ruff check app tests alembic --fix 
uv run ruff format app tests alembic
uv run python -m pytest --disable-warnings
pause