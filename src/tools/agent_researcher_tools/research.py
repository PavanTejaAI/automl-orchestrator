import asyncio
import hashlib
import time
import atexit
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, Any, AsyncIterator
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from tavily import TavilyClient
from src.config import config
from src.utils import logger
from src.tools.cost_tracker import get_rate_limiter, get_circuit_breaker, get_usage_tracker
from .models import (
    ResearchModel,
    ResearchResult,
    SearchResult,
    ExtractResult,
    Source,
    ResearchRequest,
    SearchRequest,
    ExtractRequest,
    ResearchToolError,
    RateLimitError,
    CircuitOpenError,
)


class ResearchTool:
    _cache: dict[str, Any] = {}
    _executor: ThreadPoolExecutor | None = None

    def __init__(self):
        if not config.tavily_api_key:
            raise ResearchToolError("TAVILY_API_KEY is required")
        self._client = TavilyClient(api_key=config.tavily_api_key)
        self._rate_limiter = get_rate_limiter(config.research_rate_limit_per_minute, 60)
        self._circuit_breaker = get_circuit_breaker(config.circuit_breaker_threshold, config.circuit_breaker_timeout)
        self._usage_tracker = get_usage_tracker(config.tavily_api_key)
        if ResearchTool._executor is None:
            ResearchTool._executor = ThreadPoolExecutor(max_workers=4)
            atexit.register(ResearchTool._shutdown_executor)
        logger.debug("ResearchTool initialized")

    @classmethod
    def _shutdown_executor(cls):
        if cls._executor:
            cls._executor.shutdown(wait=False)
            cls._executor = None

    def _cache_key(self, prefix: str, **kwargs) -> str:
        data = f"{prefix}:{sorted(kwargs.items())}"
        return hashlib.sha256(data.encode()).hexdigest()

    def _get_cached(self, key: str) -> Optional[Any]:
        entry = self._cache.get(key)
        if entry and time.time() - entry["ts"] < 3600:
            return entry["data"]
        return None

    def _set_cached(self, key: str, data: Any):
        self._cache[key] = {"data": data, "ts": time.time()}

    async def _check_limits(self, user_id: str) -> None:
        if not await self._circuit_breaker.can_execute():
            raise CircuitOpenError("Service temporarily unavailable")
        if not await self._rate_limiter.check(user_id):
            raise RateLimitError(f"Rate limit exceeded for user {user_id}")

    async def get_usage(self, force: bool = False):
        return await self._usage_tracker.fetch(force)

    async def get_remaining_credits(self) -> dict[str, int]:
        return await self._usage_tracker.get_remaining()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((ConnectionError, TimeoutError)),
        reraise=True,
    )
    def _research_sync(self, req: ResearchRequest) -> ResearchResult:
        response = self._client.research(
            input=req.query,
            model=req.model.value,
            max_results=req.max_results,
            include_domains=req.include_domains,
            exclude_domains=req.exclude_domains,
        )
        request_id = response.get("request_id", "")
        result_data = self._client.get_research(request_id)
        sources = [Source(**s) for s in result_data.get("sources", [])]
        return ResearchResult(
            request_id=request_id,
            status=result_data.get("status", "unknown"),
            content=result_data.get("content", ""),
            sources=sources,
            model=req.model.value,
        )

    async def research(
        self,
        query: str,
        model: ResearchModel = ResearchModel.PRO,
        max_results: int = 10,
        include_domains: Optional[list[str]] = None,
        exclude_domains: Optional[list[str]] = None,
        user_id: str = "anonymous",
        session_id: str = "default",
    ) -> ResearchResult:
        req = ResearchRequest(
            query=query,
            model=model,
            max_results=max_results,
            include_domains=include_domains or [],
            exclude_domains=exclude_domains or [],
        )
        await self._check_limits(user_id)
        cache_key = self._cache_key("research", query=req.query, model=req.model.value)
        cached = self._get_cached(cache_key)
        if cached:
            logger.info("Research cache hit", user_id=user_id, session_id=session_id)
            cached.cached = True
            return cached

        logger.info("Research start", query=req.query[:50], model=req.model.value, user_id=user_id, session_id=session_id)
        loop = asyncio.get_running_loop()
        try:
            result = await loop.run_in_executor(self._executor, self._research_sync, req)
            self._set_cached(cache_key, result)
            self._usage_tracker.clear_cache()
            await self._circuit_breaker.record_success()
            logger.info("Research complete", request_id=result.request_id, sources_count=len(result.sources), user_id=user_id)
            return result
        except Exception as e:
            await self._circuit_breaker.record_failure()
            logger.error("Research failed", error=str(e), user_id=user_id, session_id=session_id)
            raise ResearchToolError(f"Research failed: {e}") from e

    async def research_stream(
        self,
        query: str,
        model: ResearchModel = ResearchModel.PRO,
        user_id: str = "anonymous",
        session_id: str = "default",
    ) -> AsyncIterator[dict[str, Any]]:
        req = ResearchRequest(query=query, model=model)
        await self._check_limits(user_id)
        logger.info("Research stream start", query=req.query[:50], user_id=user_id, session_id=session_id)
        loop = asyncio.get_running_loop()
        try:
            stream = await loop.run_in_executor(
                self._executor,
                lambda: self._client.research(input=req.query, model=req.model.value, stream=True),
            )
            for chunk in stream:
                yield {"chunk": chunk.decode("utf-8")}
            self._usage_tracker.clear_cache()
            await self._circuit_breaker.record_success()
        except Exception as e:
            await self._circuit_breaker.record_failure()
            logger.error("Research stream failed", error=str(e), user_id=user_id)
            raise ResearchToolError(f"Research stream failed: {e}") from e

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((ConnectionError, TimeoutError)),
        reraise=True,
    )
    def _search_sync(self, req: SearchRequest) -> SearchResult:
        response = self._client.search(
            query=req.query,
            search_depth=req.search_depth,
            max_results=req.max_results,
            include_domains=req.include_domains,
            exclude_domains=req.exclude_domains,
            include_answer=req.include_answer,
            include_raw_content=req.include_raw_content,
        )
        return SearchResult(
            query=response.get("query", req.query),
            answer=response.get("answer"),
            results=response.get("results", []),
            response_time=response.get("response_time", 0.0),
        )

    async def search(
        self,
        query: str,
        search_depth: str = "advanced",
        max_results: int = 10,
        include_domains: Optional[list[str]] = None,
        exclude_domains: Optional[list[str]] = None,
        include_answer: bool = True,
        include_raw_content: bool = False,
        user_id: str = "anonymous",
        session_id: str = "default",
    ) -> SearchResult:
        req = SearchRequest(
            query=query,
            search_depth=search_depth,
            max_results=max_results,
            include_domains=include_domains or [],
            exclude_domains=exclude_domains or [],
            include_answer=include_answer,
            include_raw_content=include_raw_content,
        )
        await self._check_limits(user_id)
        cache_key = self._cache_key("search", query=req.query, depth=req.search_depth)
        cached = self._get_cached(cache_key)
        if cached:
            logger.info("Search cache hit", user_id=user_id, session_id=session_id)
            cached.cached = True
            return cached

        logger.info("Search start", query=req.query[:50], user_id=user_id, session_id=session_id)
        loop = asyncio.get_running_loop()
        try:
            result = await loop.run_in_executor(self._executor, self._search_sync, req)
            self._set_cached(cache_key, result)
            self._usage_tracker.clear_cache()
            await self._circuit_breaker.record_success()
            logger.info("Search complete", results_count=len(result.results), user_id=user_id)
            return result
        except Exception as e:
            await self._circuit_breaker.record_failure()
            logger.error("Search failed", error=str(e), user_id=user_id, session_id=session_id)
            raise ResearchToolError(f"Search failed: {e}") from e

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((ConnectionError, TimeoutError)),
        reraise=True,
    )
    def _extract_sync(self, req: ExtractRequest) -> ExtractResult:
        response = self._client.extract(urls=req.urls, include_images=req.include_images)
        return ExtractResult(
            results=response.get("results", []),
            failed_results=response.get("failed_results", []),
        )

    async def extract(
        self,
        urls: list[str],
        include_images: bool = False,
        user_id: str = "anonymous",
        session_id: str = "default",
    ) -> ExtractResult:
        req = ExtractRequest(urls=urls, include_images=include_images)
        await self._check_limits(user_id)
        logger.info("Extract start", urls_count=len(req.urls), user_id=user_id, session_id=session_id)
        loop = asyncio.get_running_loop()
        try:
            result = await loop.run_in_executor(self._executor, self._extract_sync, req)
            self._usage_tracker.clear_cache()
            await self._circuit_breaker.record_success()
            logger.info("Extract complete", success=len(result.results), failed=len(result.failed_results), user_id=user_id)
            return result
        except Exception as e:
            await self._circuit_breaker.record_failure()
            logger.error("Extract failed", error=str(e), user_id=user_id, session_id=session_id)
            raise ResearchToolError(f"Extract failed: {e}") from e

    async def get_context(
        self,
        query: str,
        max_tokens: int = 4000,
        user_id: str = "anonymous",
        session_id: str = "default",
    ) -> str:
        if not query or not query.strip():
            raise ResearchToolError("query cannot be empty")
        await self._check_limits(user_id)
        logger.info("Get context", query=query[:50], user_id=user_id)
        loop = asyncio.get_running_loop()
        try:
            result = await loop.run_in_executor(
                self._executor,
                lambda: self._client.get_search_context(query=query, max_tokens=max_tokens),
            )
            self._usage_tracker.clear_cache()
            await self._circuit_breaker.record_success()
            return result
        except Exception as e:
            await self._circuit_breaker.record_failure()
            logger.error("Get context failed", error=str(e), user_id=user_id)
            raise ResearchToolError(f"Get context failed: {e}") from e

    async def qna(
        self,
        query: str,
        user_id: str = "anonymous",
        session_id: str = "default",
    ) -> str:
        if not query or not query.strip():
            raise ResearchToolError("query cannot be empty")
        await self._check_limits(user_id)
        logger.info("QnA", query=query[:50], user_id=user_id)
        loop = asyncio.get_running_loop()
        try:
            result = await loop.run_in_executor(
                self._executor,
                lambda: self._client.qna_search(query=query),
            )
            self._usage_tracker.clear_cache()
            await self._circuit_breaker.record_success()
            return result
        except Exception as e:
            await self._circuit_breaker.record_failure()
            logger.error("QnA failed", error=str(e), user_id=user_id)
            raise ResearchToolError(f"QnA failed: {e}") from e


_instance: ResearchTool | None = None


def get_research_tool() -> ResearchTool:
    global _instance
    if _instance is None:
        _instance = ResearchTool()
    return _instance
