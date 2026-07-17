from pydantic import BaseModel, HttpUrl


class RecipeSearchResult(BaseModel):
    identifier: str
    title: str
    path: str
    source_url: HttpUrl | None = None
