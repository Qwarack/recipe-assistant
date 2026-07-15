from recipe_scrapers import scrape_html

from app.models.import_result import ImportWarning
from app.models.recipe import Recipe, SourceType
from app.services.ingredient_parser import (
    parse_ingredient_line_with_warnings,
)


class RecipeScrapersFallback:
    extractor_name = "recipe-scrapers"

    def extract(
        self,
        html: str,
        source_url: str,
    ) -> tuple[Recipe, list[ImportWarning]]:
        scraper = scrape_html(
            html=html,
            org_url=source_url,
        )

        ingredients = []
        warnings: list[ImportWarning] = []

        for raw_ingredient in scraper.ingredients():
            parse_result = parse_ingredient_line_with_warnings(raw_ingredient)

            ingredients.append(parse_result.ingredient)
            warnings.extend(
                ImportWarning(
                    code=warning.code,
                    message=warning.message,
                )
                for warning in parse_result.warnings
            )

        instructions = [
            line.strip() for line in scraper.instructions_list() if line.strip()
        ]

        recipe = Recipe(
            title=scraper.title(),
            source_type=SourceType.WEBSITE,
            source_url=source_url,
            source_name=scraper.site_name(),
            extractor=self.extractor_name,
            servings=self._parse_servings(scraper.yields()),
            prep_time_minutes=scraper.prep_time(),
            cook_time_minutes=scraper.cook_time(),
            total_time_minutes=scraper.total_time(),
            ingredients=ingredients,
            instructions=instructions,
        )

        return recipe, warnings

    @staticmethod
    def _parse_servings(value: str | None) -> int | None:
        if value is None:
            return None

        digits = "".join(character for character in value if character.isdigit())

        if not digits:
            return None

        return int(digits)
