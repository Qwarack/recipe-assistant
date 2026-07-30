# Recipe Assistant

Self-hosted receptenimporter voor een homelabomgeving. De applicatie zet recepten uit verschillende bronnen om naar een gevalideerd `Recipe`-model en slaat ze op als consistente Markdown-bestanden met YAML-frontmatter.

De huidige versie omvat **fase 1 t/m 4 plus de lokale Gemma-importlaag** van een groter systeem voor receptenbeheer, weekplanning, boodschappenlijsten en later voorraadbeheer. Naast import en handmatige planning ondersteunt de applicatie reproduceerbare automatische weekvoorstellen.

## Huidige functionaliteit

De applicatie ondersteunt momenteel:

- Importeren vanaf een receptenwebsite via URL.
- Extractie van schema.org `Recipe` JSON-LD.
- `recipe-scrapers` als fallback wanneer JSON-LD ontbreekt of onbruikbaar is.
- Importeren uit een lokaal HTML-bestand.
- Importeren uit een bestaand Markdown-recept.
- Importeren uit handmatig geplakte recepttekst.
- Importeren uit een JPEG-, PNG- of WebP-afbeelding met Gemma vision.
- Handmatige AI-fallback en AI-herparse vanuit een Discord-preview.
- Voorzichtige AI-verrijking van ontbrekende receptmetadata.
- Normalisatie van ingrediënten, hoeveelheden, eenheden, servings, tijden, tags en maaltijdtypes.
- Opslag als Markdown met YAML-frontmatter.
- Unieke recept-ID en import-ID.
- SHA-256 content-hash voor duplicaatdetectie.
- Duplicaatcontrole op bron-URL, inhoud en genormaliseerde titel.
- Geforceerd opnieuw importeren met `force=true`.
- Optionele opslag van ruwe HTML bij mislukte imports.
- FastAPI-endpoints voor previews, bevestigde imports, AI-herparse en bestandsuploads.
- Unit-, snapshot-, fixture- en integratietests.
- Handmatige weekplanning via de API en Discord, standaard van woensdag t/m dinsdag.

## Architectuur

```text
Discord / HTTP / lokaal bestand
              |
              v
        Importsessie + bron
              |
       +------+------+
       |             |
       v             v
Normale parser   Gemma vision
       |             |
       +------+------+
              |
              v
     Pydantic Recipe-model
              |
              v
 Ontbrekende velden detecteren
              |
              v
   Optionele AI-verrijking
              |
              v
       Preview + bevestiging
              |
              v
     RecipeImportService
              |
       +------+------+
       |             |
       v             v
DuplicateDetector MarkdownRenderer
                     |
                     v
              Markdown-bestand
```

Belangrijke onderdelen:

```text
app/
├── ai/                  Ollama-client, prompts en AI-schema's
├── api/                 FastAPI-routes en API-schema's
├── bot/                 Discord-commando's, embeds en views
├── core/                Configuratie, logging en HTTP-client
├── importers/           Normale importers en de AI-receptmapper
├── models/              Pydantic-modellen
├── services/            Importflow, AI-orchestratie, rendering en opslag
├── templates/           Jinja2 Markdown-template
├── utils/               Normalisatie en content-hashing
└── main.py              FastAPI-applicatie
```

## Vereisten

- Python 3.12 of nieuwer.
- `uv` voor dependency management.
- Docker en Docker Compose voor containerized gebruik.
- Voor NVIDIA-GPU-versnelling op Ubuntu: Docker Compose 2.30.0 of nieuwer,
  een ondersteunde NVIDIA-driver en de NVIDIA Container Toolkit.
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
RECIPES_PATH=/data/vault
IMPORTS_PATH=/data/imports
APP_TIMEZONE=Europe/Amsterdam
```

Bij lokaal draaien zonder Docker kunnen deze paden bijvoorbeeld worden aangepast naar:

```env
RECIPES_PATH=./data/recipes
IMPORTS_PATH=./data/imports
```

`RECIPES_PATH` bevat de gegenereerde Markdown-recepten. Docker Compose stelt dit
pad in op `/data/vault`, gekoppeld aan
`/srv/obsidian/ReceptenVault` op de host.

`IMPORTS_PATH` bevat optioneel ruwe HTML van mislukte website-imports voor debugging.

`APP_TIMEZONE` bepaalt welke lokale kalenderdatum voor de actuele planning wordt gebruikt. De standaard is `Europe/Amsterdam`.

## Discord-bot configureren en gebruiken

Vul minimaal de bot-token in `.env` in. Voor snelle commandosynchronisatie
tijdens ontwikkeling is een guild-ID sterk aanbevolen:

```env
DISCORD_BOT_TOKEN=je-bot-token
DISCORD_GUILD_ID=123456789012345678
DISCORD_ALLOWED_CHANNEL_ID=123456789012345678
DISCORD_ALLOWED_ROLE_IDS=123456789012345678,987654321098765432
```

- `DISCORD_GUILD_ID` synchroniseert slash-commando's direct naar die server.
  Zonder deze waarde worden de commando's globaal gesynchroniseerd; het kan
  dan langer duren voordat Discord wijzigingen toont.
- `DISCORD_ALLOWED_CHANNEL_ID` beperkt de `/recept`-commando's en automatische
  URL-detectie tot één kanaal. Laat de waarde leeg om ieder kanaal toe te
  staan.
- `DISCORD_ALLOWED_ROLE_IDS` is een kommalijst. Recepten importeren,
  uploaden en verwijderen vereist één van deze rollen. Laat de waarde leeg
  om de rolcontrole uit te schakelen.
- Schakel voor automatische URL-detectie de **Message Content Intent** in het
  Discord Developer Portal in. Slash-commando's zelf gebruiken deze intent
  niet.

De bot gebruikt slash-commando's. Er zijn momenteel geen gebruikerscommando's
met het `!`-prefix.

### Receptcommando's

| Discord-commando | Verplichte invoer | Gedrag |
| --- | --- | --- |
| `/recept import` | `url` | Maakt een preview van een receptenwebsite. |
| `/recept tekst` | geen | Opent een modal waarin je titel, ingrediënten en stappen plakt. |
| `/recept upload` | `bestand` | Accepteert `.md`, `.txt`, `.html`, `.htm`, `.jpg`, `.jpeg`, `.png` en `.webp`. |
| `/recept zoek` | `query` | Zoekt maximaal tien opgeslagen recepten. |
| `/recept toon` | `identifier` | Toont een recept; het identifier-veld heeft autocomplete. |
| `/recept verwijder` | `identifier` | Toont eerst een bevestiging en verwijdert daarna het recept. |

Voorbeelden zoals je ze in Discord invoert:

```text
/recept import url:https://voorbeeld.nl/recept/pasta
/recept tekst
/recept upload bestand:<kies een bestand of screenshot>
/recept zoek query:pasta
/recept toon identifier:pasta-carbonara
/recept verwijder identifier:pasta-carbonara
```

Een normale importpreview toont **Opslaan**, **Parse met AI** en
**Annuleren** wanneer AI beschikbaar is. Na een AI-parse verandert de
AI-knop in **Opnieuw met AI**. Wanneer de normale parser niets bruikbaars
vindt, toont Discord **Opnieuw met AI** en **Annuleren**. Bij een sterk
duplicaat verschijnen **Toch opnieuw opslaan** en **Niet opslaan**.

Je kunt ook een URL als gewoon bericht in het toegestane kanaal plaatsen.
De bot reageert dan met **Preview maken** voor de eerste URL in het bericht.

### Weekcommando's

Alle datums gebruiken `JJJJ-MM-DD`. De volledige actuele set is:

| Discord-commando | Verplicht | Optioneel/default |
| --- | --- | --- |
| `/week toon` | geen | `startdatum`; zonder waarde wordt de huidige of nieuwste planning getoond. |
| `/week plan` | `recept_id`, `datum` | `startdatum`, `porties=2`, `maaltijd=dinner`, `notitie`. |
| `/week wijzig` | `entry_id` | `datum`, `startdatum`, `porties`, `maaltijd`, `notitie`; geef minstens één echte wijziging op en gebruik `-` om de notitie te wissen. |
| `/week verwijder` | `entry_id` | `startdatum`; zonder waarde wordt de huidige planning gebruikt. |
| `/week genereer` | geen | `startdatum`, `porties=2`, `max_werktijd`, `vegetarische_dagen`, `recente_recepten_vermijden=21`. |
| `/week vervang` | `voorstel_id`, `entry_id` | geen; kiest opnieuw voor één entry uit een gegenereerd voorstel. |

Voorbeelden:

```text
/week toon
/week toon startdatum:2026-07-29
/week plan recept_id:pasta-carbonara datum:2026-07-31 porties:4 maaltijd:Avondeten
/week wijzig entry_id:42 porties:6 notitie:extra groenten
/week verwijder entry_id:42
/week genereer porties:4 max_werktijd:30 vegetarische_dagen:do,zo
/week vervang voorstel_id:12 entry_id:42
```

`recept_id` gebruikt autocomplete en `maaltijd` biedt de keuzes
**Ontbijt**, **Lunch** en **Avondeten**. Een gegenereerd weekvoorstel toont
de knoppen **Accepteren**, **Opnieuw genereren** en **Annuleren**. Alleen de
gebruiker die het voorstel maakte kan die knoppen bedienen.

## Lokale AI met Gemma

Ollama en Gemma vormen een optionele lokale laag boven op de bestaande
parsers. Website-, tekst-, HTML- en Markdown-parsers blijven altijd de
standaardroute. Gemma wordt alleen gebruikt voor een handmatige fallback of
herparse, voor afbeeldingsinput en voor het voorzichtig aanvullen van
ontbrekende metadata. Een AI-resultaat wordt met Pydantic gevalideerd en pas
na een Discord-preview en expliciete bevestiging opgeslagen. Voor
afbeeldingsimport is een vision-capabel model nodig; `gemma3:4b` is daarom
de standaard.

### NVIDIA-GPU gebruiken met Docker op Ubuntu

Ollama detecteert bij het opstarten automatisch welke compatibele GPU's
zichtbaar zijn en hoeveel VRAM beschikbaar is. Het model wordt vervolgens
automatisch volledig of gedeeltelijk op de GPU geladen wanneer dat mogelijk
is. De Recipe Assistant hoeft daarvoor geen CUDA-optie of andere
applicatiecode in te stellen.

Een container ziet de GPU niet automatisch. De basisconfiguratie in
`compose.yml` vraagt daarom bewust geen GPU aan: zo start Ollama ook op een
server zonder NVIDIA-hardware of toolkit en gebruikt het automatisch de CPU.
De resourcegrenzen blijven in beide situaties actief:

```yaml
services:
  ollama:
    image: ollama/ollama
    restart: unless-stopped
    cpus: 3.0
    cpu_shares: 256
    mem_limit: 7g
    mem_reservation: 4g
    memswap_limit: 9g
    volumes:
      - ollama_data:/root/.ollama
```

GPU-toegang staat in de optionele override `compose.gpu.yml`:

```yaml
services:
  ollama:
    gpus: all
```

Deze beginconfiguratie begrenst Ollama tot drie CPU-cores en 7 GB werkgeheugen.
De reservering van 4 GB is een zachte ondergrens voor resourceplanning;
`memswap_limit: 9g` staat naast de 7 GB RAM maximaal 2 GB swap toe.
`cpu_shares: 256` geeft Ollama bij CPU-concurrentie een lagere relatieve
prioriteit dan een container met de standaardwaarde 1024.

De applicatie serialiseert daarnaast alle modelgeneraties met een gedeelde
`asyncio.Semaphore(1)`. Daardoor voert het huidige API-proces maximaal één
Ollama-generatie tegelijk uit, inclusief eventuele retries. Andere AI-aanvragen
wachten asynchroon en blokkeren de normale niet-AI-routes niet. Deze begrenzing
geldt per API-proces; bij meerdere Uvicorn-workers of API-replica's ontstaat
één semaphore per proces. De meegeleverde Dockerfile start één worker.

`gpus: all` vereist Docker Compose 2.30.0 of nieuwer. Op de Ubuntu-host moeten
een compatibele NVIDIA-driver en de NVIDIA Container Toolkit geïnstalleerd
zijn. Controleer eerst of de hostdriver werkt:

```bash
nvidia-smi
docker compose version
```

Installeer daarna op Ubuntu de toolkit via de officiële NVIDIA-repository:

```bash
sudo apt-get update
sudo apt-get install -y --no-install-recommends ca-certificates curl gnupg2

curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey \
  | sudo gpg --dearmor \
    -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg

curl -s -L \
  https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list \
  | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' \
  | sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
```

Controleer vóór het starten van de GPU-variant of Docker de GPU kan benaderen:

```bash
docker run --rm --gpus all ubuntu nvidia-smi
```

Als dit commando mislukt, start dan de gewone CPU-configuratie en laat de
GPU-override weg. Start na een geslaagde controle de GPU-variant, laad het
model eenmalig en bekijk daarna de verdeling:

```bash
docker compose -f compose.yml -f compose.gpu.yml up -d ollama
docker compose exec ollama ollama run gemma3:4b "Geef alleen het woord OK."
docker compose exec ollama ollama ps
```

Gebruik op een NVIDIA-host de twee `-f`-opties bij ieder later `up`-commando
waarmee `ollama` wordt aangemaakt of bijgewerkt. Een gewoon
`docker compose up` gebruikt bewust de CPU-veilige basisconfiguratie.

De kolom `PROCESSOR` van `ollama ps` toont bijvoorbeeld `100% GPU`, `100% CPU`
of een CPU/GPU-verdeling. Zie de officiële documentatie van
[Ollama voor Docker](https://docs.ollama.com/docker),
[Ollama-hardwareondersteuning](https://docs.ollama.com/gpu),
[Docker Compose GPU-support](https://docs.docker.com/reference/compose-file/services/#gpus)
en de
[NVIDIA Container Toolkit-installatie](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html).

Samengevat:

- Zonder NVIDIA-hardware of toolkit: gebruik gewoon `docker compose up`; Ollama
  start op CPU.
- Met werkende NVIDIA-hardware en toolkit: voeg
  `-f compose.yml -f compose.gpu.yml` toe; Ollama detecteert en gebruikt de GPU
  automatisch.

### Gemma voor het eerst toevoegen

Kopieer eerst `.env.example` naar `.env` en controleer deze waarden:

```env
AI_ENABLED=true
OLLAMA_MODEL=gemma3:4b
```

Start vervolgens Ollama, download het model en controleer de installatie:

```bash
docker compose up -d ollama
docker compose exec ollama ollama pull gemma3:4b
docker compose exec ollama ollama list
docker compose exec ollama ollama show gemma3:4b
docker compose up -d --build api bot
```

Het model staat in het persistente volume `ollama_data`; het pull-commando
hoeft dus niet bij iedere start opnieuw te worden uitgevoerd. Poort 11434
wordt niet naar de host gepubliceerd. De API bereikt Ollama alleen via
`http://ollama:11434` op het interne Compose-netwerk.

Het model wordt bewust niet automatisch bij containerstart gedownload.
Modelbestanden zijn groot en een tijdelijk internetprobleem mag het starten
van normale receptenimports niet blokkeren.

### Een ander Gemma-model toevoegen of kiezen

Gebruik exact dezelfde Ollama-modeltag in het pull-commando en in `.env`.
Vervang `<modeltag>` hieronder bijvoorbeeld door een andere Gemma-tag:

```bash
docker compose exec ollama ollama pull <modeltag>
docker compose exec ollama ollama show <modeltag>
```

Pas daarna `.env` aan:

```env
OLLAMA_MODEL=<modeltag>
```

Maak de API en bot opnieuw aan zodat de nieuwe configuratie wordt ingelezen:

```bash
docker compose up -d --force-recreate api bot
```

Voor screenshots en foto's moet de gekozen tag afbeeldingen ondersteunen.
Voor alleen tekstuele fallback kan een tekstmodel technisch werken, maar de
app verwacht nog steeds betrouwbare, schema-conforme JSON. De applicatie
selecteert niet automatisch tussen meerdere modellen.

Een bestaande tag opnieuw downloaden of bijwerken:

```bash
docker compose exec ollama ollama pull <modeltag>
```

Een niet meer gebruikt model verwijderen:

```bash
docker compose exec ollama ollama rm <modeltag>
```

Dit verwijdert alleen het model uit `ollama_data`; recepten en imports onder
`data/` blijven behouden.

### Ollama buiten Docker gebruiken

Wanneer API en Ollama beide rechtstreeks op de ontwikkelmachine draaien,
gebruik je niet de Compose-servicenaam:

```env
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=gemma3:4b
```

Installeer en start Ollama volgens de instructies voor je besturingssysteem.
Download daarna het model:

```bash
ollama pull gemma3:4b
ollama list
```

Start `ollama serve` alleen wanneer de Ollama-app of systeemservice de server
niet al heeft gestart.

Gebruik binnen Compose altijd `http://ollama:11434`; `localhost` zou daar
naar de API-container zelf wijzen.

### AI-instellingen

De belangrijkste instellingen zijn:

```env
AI_ENABLED=true
OLLAMA_BASE_URL=http://ollama:11434
OLLAMA_MODEL=gemma3:4b
OLLAMA_TIMEOUT_SECONDS=120
OLLAMA_MAX_RETRIES=1
AI_ENRICH_MISSING_FIELDS=true
AI_ALLOW_INGREDIENT_QUANTITY_ESTIMATES=false
AI_ALLOW_TEMPERATURE_ESTIMATES=false
MAX_IMAGE_UPLOAD_BYTES=10485760
MAX_IMAGE_DIMENSION=2048
MAX_AI_SOURCE_CHARACTERS=50000
MAX_AI_PROMPT_CHARACTERS=65000
```

Normale imports blijven werken wanneer `AI_ENABLED=false`, Ollama offline is
of het model nog niet is geïnstalleerd. Alleen AI-acties geven dan een gerichte
foutmelding. Zie [de Gemma-importarchitectuur](docs/gemma-import-architecture.md)
voor de hergebruikte componenten en de gekozen grens tussen preview en opslag.

Probleemoplossing:

- `docker compose ps` toont of de Ollama-container gezond is.
- `docker compose logs ollama` toont model- en runtimefouten.
- `docker run --rm --gpus all ubuntu nvidia-smi` controleert of Docker toegang
  heeft tot de NVIDIA-GPU.
- `docker compose exec ollama ollama list` controleert of `gemma3:4b`
  beschikbaar is.
- `docker compose exec ollama ollama ps` toont welk model momenteel geladen
  is en of het op CPU, GPU of een combinatie daarvan draait.
- Controleer dat `OLLAMA_MODEL` in `.env` exact overeenkomt met een tag uit
  `ollama list`.
- Maak `api` en `bot` na een wijziging in `.env` opnieuw aan met
  `docker compose up -d --force-recreate api bot`; een gewone restart leest
  gewijzigde environmentvariabelen niet opnieuw in.
- Zet `AI_ENABLED=false` om alle AI-knoppen en AI-endpoints tijdelijk uit te
  schakelen zonder normale imports te blokkeren.

Rollback: zet `AI_ENABLED=false` en start `api` en `bot` opnieuw. Omdat deze
stap geen databasekolommen toevoegt, is geen databasemigratie of downgrade
nodig.

Nieuwe Discord-interacties:

- Na een normale preview staat `Parse met AI`; het normale resultaat blijft
  beschikbaar totdat Gemma met succes een nieuwe preview heeft gemaakt.
- Na een mislukte normale parse staan `Opnieuw met AI` en `Annuleren`.
- `/recept upload` accepteert naast tekstbestanden één JPEG-, PNG- of
  WebP-afbeelding van maximaal 10 MB. Afbeeldingen worden naar maximaal 2048
  pixels verkleind, met EXIF-rotatie gecorrigeerd en daarna door Gemma
  verwerkt.
- Een AI-preview toont het gebruikte model, geschatte velden, nog ontbrekende
  velden en waarschuwingen. `Opslaan` blijft altijd een expliciete stap.

De bot gebruikt hiervoor:

```text
POST /imports/{import_id}/parse-ai
POST /imports/{import_id}/confirm
POST /imports/{import_id}/cancel
GET  /imports/{import_id}
POST /imports/upload/preview
```

Handmatige controle:

1. Start Compose en pull `gemma3:4b`.
2. Importeer een geldige recepten-URL en controleer de normale preview.
3. Kies `Parse met AI`, controleer de herkomstregel en bevestig de nieuwe
   preview.
4. Upload een screenshot via `/recept upload` en controleer dat opslaan pas
   na bevestiging plaatsvindt.
5. Stop `ollama`, start nogmaals een AI-actie en controleer de begrijpelijke
   foutmelding; een normale preview moet intact blijven.
6. Annuleer een afbeeldingsimport en controleer dat het tijdelijke bestand
   onder `IMPORTS_PATH/pending-images` verdwijnt.

Bekende beperking: importsessies zijn proceslokaal. Een API-herstart maakt
nog niet bevestigde previews ongeldig. Definitieve recepten en het
Ollama-modelvolume blijven wel bewaard.

## Weekplanning (fase 3)

Alle datums gebruiken het formaat `JJJJ-MM-DD`. Een planning omvat zeven dagen. Wanneer `/week plan` geen startdatum krijgt, berekent de bot de meest recente woensdag vanaf de gekozen eetdatum; zo loopt de standaardperiode van woensdag t/m dinsdag. Een expliciete startdatum blijft mogelijk.

Belangrijkste handmatige Discord-commando's:

- `/week toon [startdatum]`: toont de actuele planning, met fallback naar de nieuwste planning, of een expliciete planning.
- `/week plan`: plant een recept in; het receptveld heeft autocomplete en het maaltijdtype vaste keuzes.
- `/week wijzig`: wijzigt datum, maaltijdtype, porties of notitie van een entry. Gebruik `-` als notitie om die te wissen.
- `/week verwijder`: verwijdert een entry. Het benodigde entry-ID staat in `/week toon`.
- `/week genereer`: maakt een automatisch weekvoorstel.
- `/week vervang`: kiest opnieuw voor één entry uit een gegenereerd voorstel.

Zie [Discord-bot configureren en gebruiken](#discord-bot-configureren-en-gebruiken)
voor alle parameters, defaults en invoervoorbeelden.

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

Maak op de Docker-host eerst de gedeelde vault en de persistente configuratiemap
voor Obsidian Headless aan:

```bash
sudo mkdir -p /srv/obsidian/ReceptenVault
sudo mkdir -p /srv/obsidian/headless-config
```

Configureer Obsidian Headless eenmalig voordat de synchronisatieservice voor het
eerst wordt gestart:

```bash
docker compose run --rm --build obsidian-sync ob login
docker compose run --rm obsidian-sync \
  ob sync-setup --vault "ReceptenVault" --path /vault
```

Vervang `ReceptenVault` bij het tweede commando door de exacte naam van de
remote Obsidian Sync-vault. De login- en vaultconfiguratie blijven bewaard in
`/srv/obsidian/headless-config`.

Bouw en start de applicatie:

```bash
docker compose up --build
```

Op de achtergrond:

```bash
docker compose up --build -d
```

Deze standaardcommando's zijn CPU-veilig en werken zonder NVIDIA-hardware.
Gebruik voor GPU-versnelling de
[NVIDIA Compose-override](#nvidia-gpu-gebruiken-met-docker-op-ubuntu).

Logs bekijken:

```bash
docker compose logs -f
```

Stoppen:

```bash
docker compose down
```

De API en `obsidian-sync` gebruiken beide
`/srv/obsidian/ReceptenVault`. Daardoor schrijft de applicatie recepten direct
naar de vault die continu met Obsidian Sync wordt gesynchroniseerd. De lokale
mappen onder `data/` bewaren de database en debugbestanden na een
containerrestart.

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
- Tests voor de Ollama-client, schema-validatie, AI-verrijking en afbeeldingsimport.
- Bot-tests voor de Discord-commando's, autorisatie en interactieve previews.

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

Fase 1 t/m 4 en de lokale Gemma-importlaag zijn functioneel compleet voor de huidige scope:

- Website-import.
- Fallbackextractie.
- Normalisatie.
- Markdown-opslag.
- Duplicaatdetectie.
- Lokale HTML-, Markdown-, tekst- en afbeeldingsimport.
- Handmatige Gemma-fallback, AI-herparse en voorzichtige metadata-verrijking.
- Debugopslag.
- Tests en integratiechecks.
- Discord als primaire invoerinterface, inclusief preview- en bevestigingsflow.
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
