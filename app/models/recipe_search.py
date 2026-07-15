from pydantic import BaseModel, HttpUrl


class RecipeSearchResult(BaseModel):
    title: str
    path: str
    source_url: HttpUrl | None = None
