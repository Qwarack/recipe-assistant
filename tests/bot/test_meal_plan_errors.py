import httpx
from app.bot.meal_plan_errors import get_meal_plan_error_message


def _status_error(status_code: int, detail: str) -> httpx.HTTPStatusError:
    request = httpx.Request("PATCH", "http://api.test/meal-plans/test")
    response = httpx.Response(
        status_code,
        request=request,
        json={"detail": detail},
    )
    return httpx.HTTPStatusError(
        "API error",
        request=request,
        response=response,
    )


def test_maps_meal_plan_http_errors_to_dutch_messages() -> None:
    assert (
        get_meal_plan_error_message(_status_error(404, "Recipe not found"))
        == "Het recept kon niet worden gevonden."
    )
    assert (
        get_meal_plan_error_message(_status_error(404, "Meal plan entry not found"))
        == "De planning-entry kon niet worden gevonden."
    )
    assert (
        get_meal_plan_error_message(
            _status_error(409, "This meal slot is already planned")
        )
        == "Dit maaltijdslot is al bezet."
    )
    assert (
        get_meal_plan_error_message(_status_error(422, "Planned date is outside range"))
        == "De datum valt niet binnen deze planning."
    )


def test_maps_connection_and_timeout_errors() -> None:
    request = httpx.Request("GET", "http://api.test/meal-plans/current")

    assert (
        get_meal_plan_error_message(httpx.ConnectError("offline", request=request))
        == "De receptenservice is momenteel niet bereikbaar."
    )
    assert (
        get_meal_plan_error_message(httpx.ReadTimeout("slow", request=request))
        == "De receptenservice reageert momenteel niet op tijd."
    )
