from enum import Enum
from typing import Optional, Any
from datetime import datetime
from pydantic import BaseModel, Field, field_validator


# =============================================================================
# Tavily Research Models
# =============================================================================

class ResearchModel(str, Enum):
    MINI = "mini"
    PRO = "pro"
    AUTO = "auto"


class Source(BaseModel):
    url: str
    title: str
    favicon: Optional[str] = None


class ResearchResult(BaseModel):
    request_id: str
    status: str
    content: str
    sources: list[Source] = Field(default_factory=list)
    model: str
    cached: bool = False


class SearchResult(BaseModel):
    query: str
    answer: Optional[str] = None
    results: list[dict[str, Any]] = Field(default_factory=list)
    response_time: float = 0.0
    cached: bool = False


class ExtractResult(BaseModel):
    results: list[dict[str, Any]] = Field(default_factory=list)
    failed_results: list[str] = Field(default_factory=list)


class ResearchRequest(BaseModel):
    query: str
    model: ResearchModel = ResearchModel.PRO
    max_results: int = Field(default=10, ge=1, le=50)
    include_domains: list[str] = Field(default_factory=list)
    exclude_domains: list[str] = Field(default_factory=list)

    @field_validator("query")
    @classmethod
    def query_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("query cannot be empty")
        if len(v) > 10000:
            raise ValueError("query too long")
        return v.strip()


class SearchRequest(BaseModel):
    query: str
    search_depth: str = Field(default="advanced", pattern="^(basic|advanced)$")
    max_results: int = Field(default=10, ge=1, le=50)
    include_domains: list[str] = Field(default_factory=list)
    exclude_domains: list[str] = Field(default_factory=list)
    include_answer: bool = True
    include_raw_content: bool = False

    @field_validator("query")
    @classmethod
    def query_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("query cannot be empty")
        if len(v) > 10000:
            raise ValueError("query too long")
        return v.strip()


class ExtractRequest(BaseModel):
    urls: list[str] = Field(min_length=1, max_length=20)
    include_images: bool = False

    @field_validator("urls")
    @classmethod
    def urls_valid(cls, v: list[str]) -> list[str]:
        for url in v:
            if not url.startswith(("http://", "https://")):
                raise ValueError(f"invalid URL: {url}")
        return v


# =============================================================================
# Kaggle Models
# =============================================================================

class KaggleDatasetFile(BaseModel):
    name: str
    size: int = 0
    creation_date: Optional[str] = None


class KaggleDataset(BaseModel):
    id: int
    ref: str
    title: str
    subtitle: Optional[str] = None
    description: Optional[str] = None
    owner_name: str
    owner_ref: str
    total_bytes: int = 0
    download_count: int = 0
    vote_count: int = 0
    view_count: int = 0
    usability_rating: float = 0.0
    is_private: bool = False
    license_name: Optional[str] = None
    url: Optional[str] = None
    last_updated: Optional[str] = None
    current_version_number: int = 1
    files: list[KaggleDatasetFile] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class KaggleModelInstance(BaseModel):
    id: int
    slug: str
    framework: str
    overview: Optional[str] = None
    version_number: int = 1
    license_name: Optional[str] = None


class KaggleModel(BaseModel):
    id: int
    ref: str
    title: str
    subtitle: Optional[str] = None
    author: str
    slug: str
    description: Optional[str] = None
    is_private: bool = False
    vote_count: int = 0
    url: Optional[str] = None
    instances: list[KaggleModelInstance] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class KaggleNotebook(BaseModel):
    id: int
    ref: str
    title: str
    author: str
    language: Optional[str] = None
    kernel_type: Optional[str] = None
    total_votes: int = 0
    url: Optional[str] = None
    last_run_time: Optional[str] = None


# =============================================================================
# Errors
# =============================================================================

class ResearchToolError(Exception):
    pass


class RateLimitError(ResearchToolError):
    pass


class CircuitOpenError(ResearchToolError):
    pass


class KaggleMCPError(Exception):
    pass
