# Recipe Assistant

Self-hosted receptenimporter voor een homelabomgeving. De applicatie zet recepten uit verschillende bronnen om naar een gevalideerd `Recipe`-model en slaat ze op als consistente Markdown-bestanden met YAML-frontmatter.

De huidige versie omvat **fase 1 t/m 4** van een groter systeem voor receptenbeheer, weekplanning, boodschappenlijsten en later voorraadbeheer. Naast import en handmatige planning ondersteunt de applicatie reproduceerbare automatische weekvoorstellen.

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
- Handmatige weekplanning via de API en Discord, standaard van woensdag t/m dinsdag.

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
APP_TIMEZONE=Europe/Amsterdam
```

Bij lokaal draaien zonder Docker kunnen deze paden bijvoorbeeld worden aangepast naar:

```env
RECIPES_PATH=./data/recipes
IMPORTS_PATH=./data/imports
```

`RECIPES_PATH` bevat de gegenereerde Markdown-recepten.

`IMPORTS_PATH` bevat optioneel ruwe HTML van mislukte website-imports voor debugging.

`APP_TIMEZONE` bepaalt welke lokale kalenderdatum voor de actuele planning wordt gebruikt. De standaard is `Europe/Amsterdam`.

## Weekplanning (fase 3)

Alle datums gebruiken het formaat `JJJJ-MM-DD`. Een planning omvat zeven dagen. Wanneer `/week plan` geen startdatum krijgt, berekent de bot de meest recente woensdag vanaf de gekozen eetdatum; zo loopt de standaardperiode van woensdag t/m dinsdag. Een expliciete startdatum blijft mogelijk.

Beschikbare Discord-commando's:

- `/week toon [startdatum]`: toont de actuele planning, met fallback naar de nieuwste planning, of een expliciete planning.
- `/week plan`: plant een recept in; het receptveld heeft autocomplete en het maaltijdtype vaste keuzes.
- `/week wijzig`: wijzigt datum, maaltijdtype, porties of notitie van een entry. Gebruik `-` als notitie om die te wissen.
- `/week verwijder`: verwijdert een entry. Het benodigde entry-ID staat in `/week toon`.

Na toevoegen, wijzigen of verwijderen toont Discord direct de bijgewerkte planning.

### Meal-plan-API

```bash
curl http://127.0.0.1:8000/meal-plans/current
```

```bash
curl -X POST \
  http://127.0.0.1:8000/meal-plans/2026-07-15/entries \
  -H "Content-Type: application/json" \
  -d '{
    "planned_date": "2026-07-18",
    "recipe_identifier": "pasta-carbonara",
    "meal_type": "dinner",
    "servings": 3
  }'
```

```bash
curl -X PATCH \
  http://127.0.0.1:8000/meal-plans/2026-07-15/entries/42 \
  -H "Content-Type: application/json" \
  -d '{"servings": 4, "notes": null}'

curl -X DELETE \
  http://127.0.0.1:8000/meal-plans/2026-07-15/entries/42
```

## Automatische maaltijdplanning (fase 4)

Fase 4 kan een reproduceerbaar weekvoorstel genereren. Een voorstel wordt altijd als `draft` opgeslagen en overschrijft een actieve of handmatige planning niet. Na expliciet accepteren wordt het voorstel `active`; een eerdere actieve planning voor dezelfde startdatum krijgt de status `archived` en blijft bewaard.

De standaardperiode loopt van de meest recente woensdag tot en met dinsdag. `start_date` kan dit vervangen. Weekdagen in de API gebruiken `0 = maandag` tot en met `6 = zondag`. Zonder `days_to_plan` worden alle zeven dagen gevuld; een expliciet lege lijst plant geen dagen.

Ondersteunde voorkeuren zijn onder andere:

- aantal porties en maaltijdtype;
- maximale bereidingstijd voor werk- en weekenddagen;
- vegetarische dagen;
- verplichte en uitgesloten tags;
- expliciet uitgesloten recepten;
- vermijden van recent geplande recepten;
- wel of geen herhaling binnen één voorstel;
- bestaande entries behouden;
- ongevulde slots bij activatie toestaan;
- een vaste `random_seed` voor reproduceerbare selectie.

Harde filters bepalen welke recepten geschikt zijn. Losse scoringsregels geven vervolgens voorkeur aan lang niet geplande recepten, snelle werkdagmaaltijden, passende moeilijkheid en tagvariatie. Bij een gelijke hoogste score beslist een lokale randomgenerator op basis van de seed. De globale randomstate wordt niet gebruikt.

### Werkdag- en weekendvoorkeuren aanpassen

Per generatie kun je harde tijdslimieten instellen met `max_preparation_time_weekday` en `max_preparation_time_weekend`. Beide velden accepteren een geheel aantal minuten van `0` of hoger. Laat een veld weg of gebruik `null` voor geen tijdslimiet. `days_to_plan` en `vegetarian_days` accepteren de volgende weekdagwaarden:

| Waarde | Dag |
| ---: | --- |
| `0` | maandag |
| `1` | dinsdag |
| `2` | woensdag |
| `3` | donderdag |
| `4` | vrijdag |
| `5` | zaterdag |
| `6` | zondag |

Voorbeeld met verschillende limieten voor werkdagen en het weekend:

```json
{
  "days_to_plan": [0, 1, 2, 3, 4, 5, 6],
  "max_preparation_time_weekday": 30,
  "max_preparation_time_weekend": 90
}
```

De zachte gewichten zijn momenteel codeconfiguratie en kunnen niet via `.env`, Discord of de generatie-API worden aangepast. Wijzig hiervoor `app/services/planning_rules.py`. Een score mag een geheel getal of kommagetal zijn: positief geeft voorkeur, `0` is neutraal en negatief maakt een recept minder aantrekkelijk. De planner telt alle regels bij elkaar op, dus de grootte van een gewicht bepaalt ook hoe zwaar het meetelt tegenover de andere regels.

De standaardgewichten zijn:

| Regel | Werkdag | Weekend | Mogelijke standaardscore |
| --- | --- | --- | ---: |
| Bereidingstijd | `(60 - minuten) / 20`, begrensd op `-2` t/m `3` | `min(2, minuten / 60)` | `-2` t/m `3` |
| Moeilijkheid | `+1,5` voor `easy` of `makkelijk` | `+1,5` voor `hard` of `moeilijk` | `0` of `1,5` |
| Recentheid | gelijk op alle dagen | gelijk op alle dagen | `0` t/m `5`; nooit gepland is `5` |
| Tagvariatie | gelijk op alle dagen | gelijk op alle dagen | `-3`, `0` of `3` |

Andere moeilijkheidswaarden, waaronder `unknown`, krijgen een neutrale moeilijkheidsscore van `0`. Gebruik bij eigen gewichten bij voorkeur eindige getallen en pas de `RuleScore(...)`-waarden of formules in de betreffende regel aan. Herstart daarna de API en bot. Controleer een wijziging met:

```bash
uv run ruff check app tests alembic
uv run python -m pytest tests/services/test_planning_rules.py
```

Wanneer geen recept aan de filters voldoet, blijft alleen dat slot ongevuld en bevat de response een concrete waarschuwing. Standaard kan zo'n voorstel niet worden geactiveerd. Zet `allow_unfilled_slots` alleen bewust op `true` om dit toe te staan.

Discord biedt:

- `/week genereer` met startdatum, porties, maximale werktijd, vegetarische dagen en een recencyvenster;
- knoppen **Accepteren**, **Opnieuw genereren** en **Annuleren** onder de preview;
- `/week vervang` om één gegenereerde entry opnieuw te selecteren.

Voor vegetarische dagen accepteert Discord zowel `ma,di,wo,do,vr,za,zo` als `mon,tue,wed,thu,fri,sat,sun`. Alleen de gebruiker die het voorstel genereerde kan de actieknoppen bedienen.

### Generatie-API

```bash
curl -X POST \
  http://127.0.0.1:8000/meal-plans/generate \
  -H "Content-Type: application/json" \
  -d '{
    "start_date": "2026-07-22",
    "servings": 2,
    "max_preparation_time_weekday": 35,
    "vegetarian_days": [3],
    "avoid_recent_days": 21,
    "random_seed": 12345
  }'
```

Een draft activeren:

```bash
curl -X POST \
  http://127.0.0.1:8000/meal-plans/42/activate
```

Verder beschikbaar:

```text
POST   /meal-plans/{plan_id}/regenerate
POST   /meal-plans/{plan_id}/entries/{entry_id}/reroll
DELETE /meal-plans/{plan_id}
```

De seed is geen beveiligingswaarde; hij legt alleen de tie-breaking vast zodat hetzelfde receptaanbod en dezelfde configuratie hetzelfde voorstel opleveren.

### Receptmetadata voor planning

De SQLite-index synchroniseert `tags`, `meal_types`, `preparation_time_minutes`, `difficulty`, `servings`, `vegetarian`, `vegan` en leftoversmetadata uit YAML-frontmatter. Ontbrekende maaltijdtypes worden `dinner`, ontbrekende moeilijkheid wordt `unknown` en ontbrekende porties worden `2`. Voor vegetarisch en veganistisch blijft `null` bewust “onbekend”; dit is niet hetzelfde als `false` en voldoet niet aan een harde vegetarische-dagfilter.

`enable_leftovers` en metadata zoals `suitable_for_leftovers`, `leftover_servings` en `leftover_days` zijn voorbereid. Automatisch aanmaken van leftovers-entries staat in fase 4 uit, omdat bestaande recepten nog niet betrouwbaar genoeg aangeven hoeveel porties werkelijk overblijven. Een request met `enable_leftovers=true` wordt daarom expliciet met 422 geweigerd in plaats van stilzwijgend genegeerd.

### Database migreren en auditvelden

Voer na een update de Alembic-migratie uit:

```bash
uv run alembic upgrade head
```

Drafts bewaren hun generatieconfiguratie, seed en generatietijd. Wanneer Discord de actie uitvoert worden `created_by` en `activated_by` gevuld met de Discord-user-ID als tekst. Deze IDs worden uitsluitend gebruikt voor audit en autorisatie van de voorstelactie; tokens en overige profielgegevens worden niet opgeslagen.

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
uv run ruff check app tests alembic
```

Formatting:

```bash
uv run ruff format app tests
```

Alle controles achter elkaar:

```bash
uv run ruff check app tests alembic
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
uv run ruff check app tests alembic
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

Fase 1 t/m 4 zijn functioneel compleet voor de huidige scope:

- Website-import.
- Fallbackextractie.
- Normalisatie.
- Markdown-opslag.
- Duplicaatdetectie.
- Lokale HTML-, Markdown- en tekstimport.
- Debugopslag.
- Tests en integratiechecks.
- Discord als primaire invoerinterface.
- Handmatige weekplanning met toevoegen, tonen, wijzigen en verwijderen.
- Automatische, deterministische weekvoorstellen met draft- en activatieworkflow.

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
