import asyncio
import httpx
from dataclasses import dataclass
from typing import Optional
from src.utils import logger


@dataclass
class KeyUsage:
    usage: int
    limit: int
    search_usage: int
    extract_usage: int
    crawl_usage: int
    map_usage: int
    research_usage: int

    @property
    def remaining(self) -> int:
        return max(0, self.limit - self.usage)

    @property
    def usage_percent(self) -> float:
        return (self.usage / self.limit * 100) if self.limit > 0 else 0.0


@dataclass
class AccountUsage:
    current_plan: str
    plan_usage: int
    plan_limit: int
    paygo_usage: int
    paygo_limit: int
    search_usage: int
    extract_usage: int
    crawl_usage: int
    map_usage: int
    research_usage: int

    @property
    def plan_remaining(self) -> int:
        return max(0, self.plan_limit - self.plan_usage)

    @property
    def paygo_remaining(self) -> int:
        return max(0, self.paygo_limit - self.paygo_usage)

    @property
    def plan_usage_percent(self) -> float:
        return (self.plan_usage / self.plan_limit * 100) if self.plan_limit > 0 else 0.0


@dataclass
class TavilyUsage:
    key: KeyUsage
    account: AccountUsage


class UsageTracker:
    BASE_URL = "https://api.tavily.com/usage"

    def __init__(self, api_key: str):
        self._api_key = api_key
        self._cached: Optional[TavilyUsage] = None
        self._lock = asyncio.Lock()

    async def fetch(self, force: bool = False) -> TavilyUsage:
        async with self._lock:
            if self._cached and not force:
                return self._cached

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    self.BASE_URL,
                    headers={"Authorization": f"Bearer {self._api_key}"},
                    timeout=10.0,
                )
                response.raise_for_status()
                data = response.json()

            key_data = data.get("key", {})
            account_data = data.get("account", {})

            self._cached = TavilyUsage(
                key=KeyUsage(
                    usage=key_data.get("usage", 0),
                    limit=key_data.get("limit", 0),
                    search_usage=key_data.get("search_usage", 0),
                    extract_usage=key_data.get("extract_usage", 0),
                    crawl_usage=key_data.get("crawl_usage", 0),
                    map_usage=key_data.get("map_usage", 0),
                    research_usage=key_data.get("research_usage", 0),
                ),
                account=AccountUsage(
                    current_plan=account_data.get("current_plan", "unknown"),
                    plan_usage=account_data.get("plan_usage", 0),
                    plan_limit=account_data.get("plan_limit", 0),
                    paygo_usage=account_data.get("paygo_usage", 0),
                    paygo_limit=account_data.get("paygo_limit", 0),
                    search_usage=account_data.get("search_usage", 0),
                    extract_usage=account_data.get("extract_usage", 0),
                    crawl_usage=account_data.get("crawl_usage", 0),
                    map_usage=account_data.get("map_usage", 0),
                    research_usage=account_data.get("research_usage", 0),
                ),
            )
            logger.info(
                "Tavily usage fetched",
                key_remaining=self._cached.key.remaining,
                plan_remaining=self._cached.account.plan_remaining,
                plan=self._cached.account.current_plan,
            )
            return self._cached

    async def get_remaining(self) -> dict[str, int]:
        usage = await self.fetch()
        return {
            "key_remaining": usage.key.remaining,
            "plan_remaining": usage.account.plan_remaining,
            "paygo_remaining": usage.account.paygo_remaining,
        }

    async def get_breakdown(self) -> dict[str, dict[str, int]]:
        usage = await self.fetch()
        return {
            "key": {
                "search": usage.key.search_usage,
                "extract": usage.key.extract_usage,
                "crawl": usage.key.crawl_usage,
                "map": usage.key.map_usage,
                "research": usage.key.research_usage,
            },
            "account": {
                "search": usage.account.search_usage,
                "extract": usage.account.extract_usage,
                "crawl": usage.account.crawl_usage,
                "map": usage.account.map_usage,
                "research": usage.account.research_usage,
            },
        }

    async def can_use(self, operation: str, count: int = 1) -> bool:
        usage = await self.fetch()
        remaining = usage.key.remaining
        if remaining < count:
            logger.warning("Insufficient credits", operation=operation, remaining=remaining, requested=count)
            return False
        return True

    def clear_cache(self):
        self._cached = None


_usage_tracker: Optional[UsageTracker] = None


def get_usage_tracker(api_key: str) -> UsageTracker:
    global _usage_tracker
    if _usage_tracker is None:
        _usage_tracker = UsageTracker(api_key)
    return _usage_tracker
