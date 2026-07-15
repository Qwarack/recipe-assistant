from recipe_scrapers import scrape_html

from app.models.recipe import Recipe, SourceType
from app.services.ingredient_parser import parse_ingredient_line


class RecipeScrapersFallback:
    extractor_name = "recipe-scrapers"

    def extract(
        self,
        html: str,
        source_url: str,
    ) -> Recipe:
        scraper = scrape_html(
            html=html,
            org_url=source_url,
        )

        ingredients = [
            parse_ingredient_line(raw_ingredient)
            for raw_ingredient in scraper.ingredients()
        ]

        instructions = [
            line.strip() for line in scraper.instructions_list() if line.strip()
        ]

        return Recipe(
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

    @staticmethod
    def _parse_servings(value: str | None) -> int | None:
        if value is None:
            return None

        digits = "".join(character for character in value if character.isdigit())

        if not digits:
            return None

        return int(digits)
