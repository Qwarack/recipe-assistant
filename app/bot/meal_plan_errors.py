import httpx


def get_meal_plan_error_message(exc: httpx.HTTPError) -> str:
    if isinstance(exc, httpx.TimeoutException):
        return "De receptenservice reageert momenteel niet op tijd."
    if isinstance(exc, httpx.ConnectError):
        return "De receptenservice is momenteel niet bereikbaar."
    if not isinstance(exc, httpx.HTTPStatusError):
        return "Er ging iets mis bij het benaderen van de receptenservice."

    status_code = exc.response.status_code
    try:
        detail = str(exc.response.json().get("detail", ""))
    except ValueError:
        detail = ""
    normalized_detail = detail.lower()

    if status_code == 404:
        if "recipe" in normalized_detail:
            return "Het recept kon niet worden gevonden."
        if "entry" in normalized_detail:
            return "De planning-entry kon niet worden gevonden."
        if "draft" in normalized_detail:
            return "Het weekvoorstel kon niet worden gevonden."
        return "Er is geen weekplanning gevonden."
    if status_code == 409:
        if "unfilled" in normalized_detail:
            return "Dit voorstel heeft nog ongevulde verplichte dagen."
        if "alternative" in normalized_detail:
            return "Er is geen geschikt alternatief recept gevonden."
        if "already active" in normalized_detail:
            return "Deze planning is al actief."
        return "Dit maaltijdslot is al bezet."
    if status_code in {400, 422}:
        if "date" in normalized_detail or "datum" in normalized_detail:
            return "De datum valt niet binnen deze planning."
        if "servings" in normalized_detail or "porties" in normalized_detail:
            return "Het aantal porties is ongeldig."
        return "De opgegeven wijziging is ongeldig."
    if status_code >= 500:
        return "De receptenservice heeft een interne fout gemeld."
    return "De receptenservice kon het verzoek niet verwerken."
