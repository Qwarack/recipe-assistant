# Recipe Assistant

Self-hosted receptenimporter voor een homelabomgeving. De applicatie zet recepten uit verschillende bronnen om naar een gevalideerd `Recipe`-model en slaat ze op als consistente Markdown-bestanden met YAML-frontmatter.

De huidige versie vormt **fase 1 en 2** van een groter systeem voor receptenbeheer, weekplanning, boodschappenlijsten en later voorraadbeheer.

## Huidige functionaliteit

De applicatie ondersteunt momenteel:

- Importeren vanaf een receptenwebsite via URL.
- Extractie van schema.org `Recipe` JSON-LD.
- `recipe-scrapers` als fallback wanneer JSON-LD ontbreekt of onbruikbaar is.
- Importeren uit een lokaal HTML-bestand.
- Importeren uit een bestaand Markdown-recept.
- Importeren uit handmatig geplakte recepttekst.
- Normalisatie van ingrediënten, hoeveelheden, eenheden, servings, tijden, tags en maaltijdtypes.
- Opslag als Markdown met YAML-frontmatter.
- Unieke recept-ID en import-ID.
- SHA-256 content-hash voor duplicaatdetectie.
- Duplicaatcontrole op bron-URL, inhoud en genormaliseerde titel.
- Geforceerd opnieuw importeren met `force=true`.
- Optionele opslag van ruwe HTML bij mislukte imports.
- FastAPI-endpoint voor website-imports.
- Unit-, snapshot-, fixture- en integratietests.

## Architectuur

```text
HTTP request / lokale input
        |
        v
Importer
        |
        v
Pydantic Recipe-model
        |
        v
RecipeImportService
        |
        +--> DuplicateDetector
        |
        +--> MarkdownRenderer
        |
        v
RecipeStorage
        |
        v
Markdown-bestand
```

Belangrijke onderdelen:

```text
app/
├── api/                 FastAPI-routes en API-schema's
├── core/                Configuratie, logging en HTTP-client
├── importers/           Website-, HTML-, Markdown- en tekstimporters
├── models/              Pydantic-modellen
├── services/            Importflow, parsing, rendering en opslag
├── templates/           Jinja2 Markdown-template
├── utils/               Normalisatie en content-hashing
└── main.py              FastAPI-applicatie
```

## Vereisten

- Python 3.12 of nieuwer.
- `uv` voor dependency management.
- Docker en Docker Compose voor containerized gebruik.
- Git voor versiebeheer.

## Installatie voor lokale ontwikkeling

Clone de repository en ga naar de projectmap:

```bash
git clone <repository-url>
cd recipe-assistant
```

Installeer de dependencies:

```bash
uv sync
```

Kopieer de voorbeeldconfiguratie:

```bash
cp .env.example .env
```

Op PowerShell:

```powershell
Copy-Item .env.example .env
```

Maak de datamappen aan wanneer die nog niet bestaan:

```bash
mkdir -p data/recipes data/imports
```

Op PowerShell:

```powershell
New-Item -ItemType Directory -Force data/recipes
New-Item -ItemType Directory -Force data/imports
```

## Configuratie

Voorbeeld `.env`:

```env
RECIPES_PATH=/data/recipes
IMPORTS_PATH=/data/imports
```

Bij lokaal draaien zonder Docker kunnen deze paden bijvoorbeeld worden aangepast naar:

```env
RECIPES_PATH=./data/recipes
IMPORTS_PATH=./data/imports
```

`RECIPES_PATH` bevat de gegenereerde Markdown-recepten.

`IMPORTS_PATH` bevat optioneel ruwe HTML van mislukte website-imports voor debugging.

## Applicatie lokaal starten

Start FastAPI met Uvicorn:

```bash
uv run uvicorn app.main:app --reload
```

De API is daarna beschikbaar op:

```text
http://127.0.0.1:8000
```

Swagger UI:

```text
http://127.0.0.1:8000/docs
```

Healthcheck:

```text
GET /health
```

## Starten met Docker Compose

Bouw en start de applicatie:

```bash
docker compose up --build
```

Op de achtergrond:

```bash
docker compose up --build -d
```

Logs bekijken:

```bash
docker compose logs -f
```

Stoppen:

```bash
docker compose down
```

De mappen onder `data/` worden als volumes gemount, zodat recepten en debugbestanden bewaard blijven na een containerrestart.

## Website-recept importeren via de API

Endpoint:

```text
POST /imports/website
```

Normale import:

```json
{
  "url": "https://example.com/recipe"
}
```

Geforceerde import wanneer een duplicaat bestaat:

```json
{
  "url": "https://example.com/recipe",
  "force": true
}
```

Voorbeeldresponse:

```json
{
  "import_id": "550e8400-e29b-41d4-a716-446655440000",
  "created_at": "2026-07-15T08:30:00Z",
  "status": "success",
  "destination": "/data/recipes/pasta-carbonara-8ee66cc9.md",
  "warnings": []
}
```

Mogelijke statussen:

- `success`: volledig verwerkt.
- `partial`: bruikbaar resultaat met waarschuwingen of een gevonden duplicaat.
- `failed`: geen geldig recept kunnen maken.

## Importstrategie voor websites

De website-importer gebruikt deze volgorde:

1. URL valideren en beveiligen tegen SSRF.
2. HTML ophalen met timeout, redirectlimiet, user-agent en maximum responsegrootte.
3. schema.org `Recipe` JSON-LD uitlezen.
4. `recipe-scrapers` proberen wanneer JSON-LD niet bruikbaar is.
5. Een foutresultaat teruggeven wanneer alle extractors falen.
6. Optioneel de ruwe HTML bewaren voor debugging.

## Ondersteunde lokale inputs

### Lokaal HTML-bestand

```python
from pathlib import Path

from app.importers.local_html import LocalHtmlRecipeImporter

result = LocalHtmlRecipeImporter().import_recipe(
    Path("recipe.html")
)
```

### Markdown-bestand

```python
from pathlib import Path

from app.importers.markdown import MarkdownRecipeImporter

result = MarkdownRecipeImporter().import_recipe(
    Path("recipe.md")
)
```

### Handmatige tekst

```python
from app.importers.manual_text import ManualTextRecipeImporter

source = """
Pasta Carbonara

Ingrediënten:
- 400 g spaghetti
- 2 eieren

Bereiding:
1. Kook de pasta.
2. Meng met de eieren.
"""

result = ManualTextRecipeImporter().import_recipe(source)
```

## Markdown-output

Een opgeslagen recept ziet er ongeveer zo uit:

```markdown
---
id: 11111111-1111-1111-1111-111111111111
import_id: 22222222-2222-2222-2222-222222222222
content_hash: abc123
type: recipe
title: Pasta Carbonara
source_type: website
source_url: https://example.com/carbonara
imported_at: '2026-07-15T08:30:00+00:00'
servings: 4
meal_types:
- dinner
tags:
- pasta
- quick
---

# Pasta Carbonara

## Ingrediënten

- 400 g spaghetti
- 2 eieren

## Bereiding

1. Kook de pasta.
2. Meng met de eieren.
```

De volledige UUID in de frontmatter is de technische identiteit. De bestandsnaam gebruikt een verkorte UUID om leesbaar en uniek te blijven.

## Duplicaatdetectie

De importservice controleert in deze volgorde:

1. Genormaliseerde bron-URL.
2. Content-hash van titel, ingrediënten en instructies.
3. Genormaliseerde titel.

Gedrag:

- Dezelfde URL blokkeert een nieuwe opslag.
- Dezelfde inhoud blokkeert een nieuwe opslag.
- Een vergelijkbare titel geeft alleen een warning en wordt wel opgeslagen.
- Met `force=true` kunnen sterke duplicaatchecks bewust worden genegeerd.

## Warnings

Een recept kan bruikbaar zijn terwijl een onderdeel niet volledig betrouwbaar is geïnterpreteerd. Bijvoorbeeld een ongeldige hoeveelheid.

In dat geval blijft het recept beschikbaar, maar wordt de status `partial` en bevat `ImportResult.warnings` de details.

Dit voorkomt dat informatie stil verloren gaat.

## Tests uitvoeren

Alle tests:

```bash
uv run python -m pytest
```

Ruff linting:

```bash
uv run ruff check app tests
```

Formatting:

```bash
uv run ruff format app tests
```

Alle controles achter elkaar:

```bash
uv run ruff check app tests
uv run ruff format app tests
uv run python -m pytest
```

Op Windows wordt bewust `app tests` gebruikt in plaats van `.`. Daarmee voorkomt Ruff dat het onnodig door runtime-data, volumes of vergrendelde OneDrive-bestanden loopt.

## Teststructuur

De testsuite bevat onder andere:

- Unit tests voor modellen en utilities.
- Tests voor ingredient parsing.
- Tests voor URL- en titelnormalisatie.
- Tests voor content-hashing.
- HTML-fixtures met verschillende JSON-LD-structuren.
- Tests voor `recipe-scrapers` fallback.
- Snapshot-test voor de volledige Markdown-output.
- Integratietest van HTML-fixture tot opgeslagen Markdown-bestand.
- Test die controleert dat dezelfde URL geen tweede bestand maakt.

## Ontwikkelworkflow

Aanbevolen workflow na een wijziging:

```bash
uv run ruff check app tests
uv run ruff format app tests
uv run python -m pytest
```

Daarna committen:

```bash
git add .
git commit -m "Describe the change"
```

## Beveiliging

De website-importer bevat beschermingen tegen onveilige requests:

- Alleen toegestane protocollen.
- SSRF-validatie.
- DNS-resolutiecontrole.
- Timeout.
- Maximale responsegrootte.
- Beperkte redirects.
- Vaste user-agent.

De website-importer leest geen `file://`-URL's. Lokale bestanden worden uitsluitend via de daarvoor bedoelde lokale importers gelezen.

## Huidige projectfase

Fase 1 is functioneel compleet voor de huidige scope:

- Website-import.
- Fallbackextractie.
- Normalisatie.
- Markdown-opslag.
- Duplicaatdetectie.
- Lokale HTML-, Markdown- en tekstimport.
- Debugopslag.
- Tests en integratiechecks.

## Volgende fase

Fase 2 voegt Discord als primaire invoerinterface toe.

Geplande onderdelen:

- Discord-bot met `discord.py`.
- Slash command voor een recepten-URL.
- Automatische verwerking van links in een toegestaan kanaal.
- Preview van een geïmporteerd recept.
- Knoppen voor opslaan, aanpassen en annuleren.
- Status opvragen via import-ID.
- Permission checks en rate limiting.
- API en bot als afzonderlijke containers of processen.

## Langetermijndoel

Het uiteindelijke systeem moet recepten kunnen:

1. Ontvangen via Discord.
2. Importeren en normaliseren.
3. Opslaan in Markdown en later indexeren in een database.
4. Inplannen voor een weekmenu.
5. Omzetten naar een gecombineerde boodschappenlijst.
6. Vergelijken met de actuele voorraad.
7. Automatisch voorstellen op basis van voorkeuren, tijd en houdbaarheid.

## Licentie
