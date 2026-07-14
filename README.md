````markdown
# Recipe Assistant

Self-hosted applicatie voor het importeren, opslaan en later plannen van recepten.

## Vereisten

- Python 3.12
- uv
- Docker
- Docker Compose
- Git

## Lokale installatie

Clone de repository:

```bash
git clone <repository-url>
cd recipe-assistant
````

Installeer dependencies:

```bash
uv sync
```

Maak een lokale configuratie:

```bash
cp .env.example .env
```

Op Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

Installeer de Git pre-commit hook:

```bash
uv run pre-commit install
```

## Lokaal starten zonder Docker

```bash
uv run uvicorn app.main:app --reload
```

De API is beschikbaar op:

* [http://127.0.0.1:8000](http://127.0.0.1:8000)
* [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
* [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)

## Starten met Docker Compose

```bash
docker compose up --build
```

Op de achtergrond:

```bash
docker compose up --build -d
```

Logs bekijken:

```bash
docker compose logs -f api
```

Stoppen:

```bash
docker compose down
```

## Kwaliteitscontroles

Tests uitvoeren:

```bash
uv run python -m pytest
```

Linting uitvoeren:

```bash
uv run ruff check .
```

Formatting controleren:

```bash
uv run ruff format . --check
```

Alle pre-commit hooks uitvoeren:

```bash
uv run pre-commit run --all-files
```

## Projectstructuur

```text
app/
├── api/
├── core/
└── main.py

data/
├── database/
└── recipes/

tests/
└── test_health.py
```

## Persistente data

Recepten worden opgeslagen in:

```text
data/recipes/
```

De SQLite-database wordt opgeslagen in:

```text
data/database/recipes.db
```

