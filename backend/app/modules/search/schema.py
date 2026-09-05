from pydantic import BaseModel


class SearchResultItem(BaseModel):
    type: str
    id: int
    title: str
    slug: str | None = None
    url: str


class SearchResponse(BaseModel):
    query: str
    total: int
    results: list[SearchResultItem]
