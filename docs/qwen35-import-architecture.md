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
  metadata-aanvulactie, een foutview en een laatste expliciete ChatGPT-optie
  nadat Qwen3.5 is mislukt of onvoldoende betrouwbaar blijft.
- `app/bot/attachments.py`: de bestaande attachmentvalidatie wordt uitgebreid
  voor JPEG, PNG en WebP.
- `app/services/markdown_renderer.py` en `app/services/recipe_storage.py`: AI
  schrijft nooit rechtstreeks Markdown.

## Nieuwe verantwoordelijkheden

- `app/ai/`: dunne Ollama- en OpenAI-clients, strikte AI-outputschema's,
  prompts en getypeerde fouten.
- `app/importers/ai_recipe.py`: omzetting van gevalideerde Qwen3.5-output naar
  het bestaande `Recipe`-model.
- `app/services/import_session_repository.py`: oorspronkelijke input, actieve
  preview, herkomstmetadata, status en parsepogingen tijdens de
  bevestigingsflow.
- `app/services/recipe_enrichment_service.py`: ontbrekende velden detecteren
  en na een expliciete gebruikerskeuze uitsluitend lege, veilige velden
  aanvullen.
- `app/services/import_confidence.py`: hybride confidence bepalen uit de
  modelschatting en objectieve volledigheid, en die vertalen naar klaar,
  waarschuwing, lokale retry, OpenAI-fallback of handmatige review.
- `app/services/ai_import_orchestrator.py`: AI-fallback, volledige herparse,
  vision-import, afzonderlijke metadata-verrijking en server-side handhaving
  dat OpenAI alleen na een mislukte of onvoldoende betrouwbare lokale parse
  wordt gebruikt. De OpenAI-importer laadt daarvoor opnieuw de oorspronkelijke
  importsessiebron, niet de Qwen-uitvoer.
- `app/services/image_processing.py`: afbeeldingvalidatie, EXIF-correctie,
  verkleining en normalisatie vóór verzending naar Ollama.

Importsessiondata leeft in het API-proces. Afbeeldingen worden alleen tijdelijk
onder `IMPORTS_PATH` bewaard en bij opslaan of annuleren verwijderd. Daardoor
blijft het databaseschema voor recepten en weekplanning ongewijzigd. Een
herstart van de API maakt nog niet bevestigde importpreviews ongeldig; dit is
een bewuste eerste beperking omdat het bestaande project geen persistent
importrecord had.

De OpenAI-key komt uitsluitend uit `OPENAI_API_KEY` en wordt alleen aan de
API-container doorgegeven. Zonder sleutel wordt geen OpenAI-client gebouwd en
verschijnt geen ChatGPT-optie. Een OpenAI-resultaat gebruikt hetzelfde
gevalideerde `Recipe`-model en blijft, net als ieder ander resultaat, achter
preview en expliciete opslagbevestiging staan.

De standaard confidence-banden zijn `>= 0.95` voor klaar, `>= 0.80` voor
opslaan met waarschuwing en `>= 0.60` voor één lokale retry. Onder `0.60`, of
wanneer die retry nog steeds onder `0.80` blijft, mag de expliciete
ChatGPT-optie verschijnen. Een GPT-resultaat onder `0.80` wordt als handmatige
review gemarkeerd. De drempels zijn via `.env` instelbaar.
