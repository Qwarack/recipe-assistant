# Qwen3.5-importarchitectuur

Deze implementatie bouwt voort op de bestaande importketen en introduceert geen
tweede receptmodel of directe AI-opslag.

## Hergebruikte componenten

- `app/models/recipe.py`: het centrale, gevalideerde `Recipe`-model voor iedere
  normale en AI-import.
- `app/importers/`: de bestaande website-, tekst-, HTML- en Markdown-parsers
  blijven de standaardroute.
- `app/services/recipe_import_service.py`: duplicaatdetectie en definitieve
  Markdown-opslag blijven achter expliciete bevestiging staan.
- `app/services/recipe_preview_service.py`: normale parserpreviews blijven
  ongewijzigd beschikbaar.
- `app/api/imports.py` en `app/api/uploads.py`: FastAPI blijft de grens tussen
  Discord en de importlogica.
- `app/bot/views.py`: de bestaande preview met opslaan en annuleren wordt
  uitgebreid met een volledige AI-herparse, een afzonderlijke
  metadata-aanvulactie en een foutview.
- `app/bot/attachments.py`: de bestaande attachmentvalidatie wordt uitgebreid
  voor JPEG, PNG en WebP.
- `app/services/markdown_renderer.py` en `app/services/recipe_storage.py`: AI
  schrijft nooit rechtstreeks Markdown.

## Nieuwe verantwoordelijkheden

- `app/ai/`: een dunne Ollama-client, strikte AI-outputschema's, prompts en
  getypeerde fouten.
- `app/importers/ai_recipe.py`: omzetting van gevalideerde Qwen3.5-output naar
  het bestaande `Recipe`-model.
- `app/services/import_session_repository.py`: oorspronkelijke input, actieve
  preview, herkomstmetadata, status en parsepogingen tijdens de
  bevestigingsflow.
- `app/services/recipe_enrichment_service.py`: ontbrekende velden detecteren
  en na een expliciete gebruikerskeuze uitsluitend lege, veilige velden
  aanvullen.
- `app/services/ai_import_orchestrator.py`: AI-fallback, volledige herparse,
  vision-import en afzonderlijke metadata-verrijking.
- `app/services/image_processing.py`: afbeeldingvalidatie, EXIF-correctie,
  verkleining en normalisatie vóór verzending naar Ollama.

Importsessiondata leeft in het API-proces. Afbeeldingen worden alleen tijdelijk
onder `IMPORTS_PATH` bewaard en bij opslaan of annuleren verwijderd. Daardoor
blijft het databaseschema voor recepten en weekplanning ongewijzigd. Een
herstart van de API maakt nog niet bevestigde importpreviews ongeldig; dit is
een bewuste eerste beperking omdat het bestaande project geen persistent
importrecord had.
