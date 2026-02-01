import httpx
from typing import Optional, Any
from src.config import config
from src.utils import logger
from .models import (
    KaggleDataset,
    KaggleDatasetFile,
    KaggleModel,
    KaggleModelInstance,
    KaggleNotebook,
    KaggleMCPError,
)


class KaggleMCPClient:
    BASE_URL = "https://www.kaggle.com/mcp"

    def __init__(self):
        self._token = config.kaggle_api_token
        self._headers = {}
        if self._token:
            self._headers["Authorization"] = f"Bearer {self._token}"

    async def _request(self, tool: str, params: dict[str, Any]) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.BASE_URL}/tools/{tool}",
                json=params,
                headers=self._headers,
            )
            if response.status_code != 200:
                raise KaggleMCPError(f"Kaggle MCP error: {response.status_code} - {response.text}")
            return response.json()

    # =========================================================================
    # Datasets
    # =========================================================================

    async def search_datasets(
        self,
        search: str,
        sort_by: str = "DATASET_SORT_BY_HOTTEST",
        page_size: int = 10,
        file_type: Optional[str] = None,
    ) -> list[KaggleDataset]:
        logger.info("Kaggle search_datasets", search=search, sort_by=sort_by)
        params = {
            "search": search,
            "sort_by": sort_by,
            "page_size": page_size,
            "group": "DATASET_SELECTION_GROUP_PUBLIC",
        }
        if file_type:
            params["file_type"] = file_type
        result = await self._request("search_datasets", params)
        datasets = result.get("datasets", [])
        return [KaggleDataset(
            id=d.get("id", 0),
            ref=d.get("ref", ""),
            title=d.get("title", ""),
            subtitle=d.get("subtitle"),
            description=d.get("description"),
            owner_name=d.get("ownerName", d.get("owner_name", "")),
            owner_ref=d.get("ownerRef", d.get("owner_ref", "")),
            total_bytes=d.get("totalBytes", d.get("total_bytes", 0)),
            download_count=d.get("downloadCount", d.get("download_count", 0)),
            vote_count=d.get("voteCount", d.get("vote_count", 0)),
            view_count=d.get("viewCount", d.get("view_count", 0)),
            usability_rating=d.get("usabilityRating", d.get("usability_rating", 0.0)),
            is_private=d.get("isPrivate", d.get("is_private", False)),
            license_name=d.get("licenseName", d.get("license_name")),
            url=d.get("url"),
        ) for d in datasets]

    async def get_dataset_info(self, owner_slug: str, dataset_slug: str) -> KaggleDataset:
        logger.info("Kaggle get_dataset_info", owner=owner_slug, dataset=dataset_slug)
        params = {"owner_slug": owner_slug, "dataset_slug": dataset_slug}
        d = await self._request("get_dataset_info", params)
        files = [KaggleDatasetFile(
            name=f.get("name", ""),
            size=f.get("totalBytes", f.get("size", 0)),
            creation_date=f.get("creationDate"),
        ) for f in d.get("files", [])]
        tags = [t.get("name", "") for t in d.get("tags", [])]
        return KaggleDataset(
            id=d.get("id", 0),
            ref=d.get("ref", ""),
            title=d.get("title", ""),
            subtitle=d.get("subtitle"),
            description=d.get("description"),
            owner_name=d.get("ownerName", d.get("owner_name", "")),
            owner_ref=d.get("ownerRef", d.get("owner_ref", "")),
            total_bytes=d.get("totalBytes", d.get("total_bytes", 0)),
            download_count=d.get("downloadCount", d.get("download_count", 0)),
            vote_count=d.get("voteCount", d.get("vote_count", 0)),
            view_count=d.get("viewCount", d.get("view_count", 0)),
            usability_rating=d.get("usabilityRating", d.get("usability_rating", 0.0)),
            is_private=d.get("isPrivate", d.get("is_private", False)),
            license_name=d.get("licenseName", d.get("license_name")),
            url=d.get("url"),
            last_updated=d.get("lastUpdated", d.get("last_updated")),
            current_version_number=d.get("currentVersionNumber", d.get("current_version_number", 1)),
            files=files,
            tags=tags,
        )

    async def list_dataset_files(
        self,
        owner_slug: str,
        dataset_slug: str,
        page_size: int = 50,
    ) -> list[KaggleDatasetFile]:
        logger.info("Kaggle list_dataset_files", owner=owner_slug, dataset=dataset_slug)
        params = {
            "owner_slug": owner_slug,
            "dataset_slug": dataset_slug,
            "page_size": page_size,
        }
        result = await self._request("list_dataset_files", params)
        files = result.get("dataset_files", result.get("datasetFiles", []))
        return [KaggleDatasetFile(
            name=f.get("name", ""),
            size=f.get("totalBytes", f.get("size", 0)),
            creation_date=f.get("creationDate"),
        ) for f in files]

    async def get_dataset_download_url(
        self,
        owner_slug: str,
        dataset_slug: str,
        file_name: Optional[str] = None,
    ) -> str:
        logger.info("Kaggle download_dataset", owner=owner_slug, dataset=dataset_slug, file=file_name)
        params = {"owner_slug": owner_slug, "dataset_slug": dataset_slug}
        if file_name:
            params["file_name"] = file_name
        result = await self._request("download_dataset", params)
        return result.get("url", "")

    # =========================================================================
    # Models
    # =========================================================================

    async def search_models(
        self,
        search: str,
        owner: Optional[str] = None,
        sort_by: str = "LIST_MODELS_ORDER_BY_HOTNESS",
        page_size: int = 10,
    ) -> list[KaggleModel]:
        logger.info("Kaggle search_models", search=search, owner=owner)
        params = {
            "search": search,
            "sort_by": sort_by,
            "page_size": page_size,
        }
        if owner:
            params["owner"] = owner
        result = await self._request("list_models", params)
        models = result.get("models", [])
        return [KaggleModel(
            id=m.get("id", 0),
            ref=m.get("ref", ""),
            title=m.get("title", ""),
            subtitle=m.get("subtitle"),
            author=m.get("author", ""),
            slug=m.get("slug", ""),
            description=m.get("description"),
            is_private=m.get("isPrivate", m.get("is_private", False)),
            vote_count=m.get("voteCount", m.get("vote_count", 0)),
            url=m.get("url"),
        ) for m in models]

    async def get_model_info(self, owner_slug: str, model_slug: str) -> KaggleModel:
        logger.info("Kaggle get_model_info", owner=owner_slug, model=model_slug)
        params = {"owner_slug": owner_slug, "model_slug": model_slug}
        m = await self._request("get_model", params)
        instances = [KaggleModelInstance(
            id=i.get("id", 0),
            slug=i.get("slug", ""),
            framework=i.get("framework", ""),
            overview=i.get("overview"),
            version_number=i.get("versionNumber", i.get("version_number", 1)),
            license_name=i.get("licenseName", i.get("license_name")),
        ) for i in m.get("instances", [])]
        tags = [t.get("name", "") for t in m.get("tags", [])]
        return KaggleModel(
            id=m.get("id", 0),
            ref=m.get("ref", ""),
            title=m.get("title", ""),
            subtitle=m.get("subtitle"),
            author=m.get("author", ""),
            slug=m.get("slug", ""),
            description=m.get("description"),
            is_private=m.get("isPrivate", m.get("is_private", False)),
            vote_count=m.get("voteCount", m.get("vote_count", 0)),
            url=m.get("url"),
            instances=instances,
            tags=tags,
        )

    # =========================================================================
    # Notebooks
    # =========================================================================

    async def search_notebooks(
        self,
        search: str,
        language: str = "python",
        sort_by: str = "HOTNESS",
        page_size: int = 10,
    ) -> list[KaggleNotebook]:
        logger.info("Kaggle search_notebooks", search=search, language=language)
        params = {
            "search": search,
            "language": language,
            "sort_by": sort_by,
            "page_size": page_size,
        }
        result = await self._request("search_notebooks", params)
        kernels = result.get("kernels", [])
        return [KaggleNotebook(
            id=k.get("id", 0),
            ref=k.get("ref", ""),
            title=k.get("title", ""),
            author=k.get("author", ""),
            language=k.get("language"),
            kernel_type=k.get("kernelType", k.get("kernel_type")),
            total_votes=k.get("totalVotes", k.get("total_votes", 0)),
            url=k.get("url"),
            last_run_time=k.get("lastRunTime", k.get("last_run_time")),
        ) for k in kernels]

    async def get_notebook_info(self, user_name: str, kernel_slug: str) -> KaggleNotebook:
        logger.info("Kaggle get_notebook_info", user=user_name, kernel=kernel_slug)
        params = {"user_name": user_name, "kernel_slug": kernel_slug}
        result = await self._request("get_notebook_info", params)
        meta = result.get("metadata", result)
        return KaggleNotebook(
            id=meta.get("id", 0),
            ref=meta.get("ref", ""),
            title=meta.get("title", ""),
            author=meta.get("author", ""),
            language=meta.get("language"),
            kernel_type=meta.get("kernelType", meta.get("kernel_type")),
            total_votes=meta.get("totalVotes", meta.get("total_votes", 0)),
            url=meta.get("url"),
            last_run_time=meta.get("lastRunTime", meta.get("last_run_time")),
        )


_kaggle_client: KaggleMCPClient | None = None


def get_kaggle_client() -> KaggleMCPClient:
    global _kaggle_client
    if _kaggle_client is None:
        _kaggle_client = KaggleMCPClient()
    return _kaggle_client
