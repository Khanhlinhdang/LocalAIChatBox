"""
Multi-Engine Search System for LocalAIChatBox.
Provides multiple search engine backends with intelligent query routing,
parallel search, result deduplication, and ranking.

Inspired by local-deep-research's 28+ engine architecture.
Self-contained implementation - no external dependencies beyond requests.
"""

import hashlib
import json
import logging
import os
import re
import time
import xml.etree.ElementTree as ET
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from urllib.parse import quote_plus, urljoin

import requests

logger = logging.getLogger(__name__)


# ==================== DATA MODELS ====================

@dataclass
class SearchResult:
    """Unified search result from any engine."""
    title: str
    url: str
    snippet: str
    source_engine: str
    rank: int = 0
    score: float = 0.0
    published_date: Optional[str] = None
    authors: Optional[List[str]] = None
    metadata: Dict = field(default_factory=dict)
    content: str = ""  # Full content if available

    def content_hash(self) -> str:
        """Hash for deduplication."""
        text = f"{self.title.lower().strip()}{self.url.lower().strip()}"
        return hashlib.md5(text.encode()).hexdigest()

    def to_dict(self) -> Dict:
        return {
            "title": self.title,
            "url": self.url,
            "snippet": self.snippet,
            "source_engine": self.source_engine,
            "rank": self.rank,
            "score": self.score,
            "published_date": self.published_date,
            "authors": self.authors,
            "content": self.content,
            "metadata": self.metadata,
        }


# ==================== BASE ENGINE ====================

class BaseSearchEngine(ABC):
    """Abstract base class for all search engines."""

    name: str = "base"
    is_available: bool = True
    is_academic: bool = False
    is_news: bool = False
    is_knowledge: bool = False
    is_code: bool = False
    is_general: bool = True

    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": "LocalAIChatBox/5.0 Research Agent"
        })

    @abstractmethod
    def search(self, query: str, max_results: int = 10) -> List[SearchResult]:
        """Execute a search and return results."""
        pass

    def is_healthy(self) -> bool:
        """Check if the engine is available."""
        return self.is_available

    def get_full_content(self, url: str) -> str:
        """Fetch full content from a URL."""
        try:
            resp = self._session.get(url, timeout=self.timeout)
            resp.raise_for_status()
            # Simple HTML-to-text extraction
            from html.parser import HTMLParser

            class TextExtractor(HTMLParser):
                def __init__(self):
                    super().__init__()
                    self.texts = []
                    self._skip = False

                def handle_starttag(self, tag, attrs):
                    if tag in ('script', 'style', 'nav', 'header', 'footer'):
                        self._skip = True

                def handle_endtag(self, tag):
                    if tag in ('script', 'style', 'nav', 'header', 'footer'):
                        self._skip = False

                def handle_data(self, data):
                    if not self._skip:
                        text = data.strip()
                        if text:
                            self.texts.append(text)

            extractor = TextExtractor()
            extractor.feed(resp.text)
            return " ".join(extractor.texts)[:5000]  # Limit content length
        except Exception as e:
            logger.debug(f"Failed to fetch content from {url}: {e}")
            return ""


# ==================== SEARXNG ENGINE ====================

class SearXNGEngine(BaseSearchEngine):
    """SearXNG meta-search engine (primary engine)."""

    name = "searxng"
    is_general = True

    def __init__(self, base_url: str = None, timeout: int = 30):
        super().__init__(timeout)
        self.base_url = base_url or os.getenv("SEARXNG_URL", "http://searxng:8080")

    def search(self, query: str, max_results: int = 10) -> List[SearchResult]:
        try:
            resp = self._session.get(
                f"{self.base_url}/search",
                params={
                    "q": query,
                    "format": "json",
                    "categories": "general",
                    "engines": "google,bing,duckduckgo,brave",
                    "pageno": 1,
                },
                timeout=self.timeout,
            )
            resp.raise_for_status()
            data = resp.json()

            results = []
            for i, item in enumerate(data.get("results", [])[:max_results]):
                results.append(SearchResult(
                    title=item.get("title", ""),
                    url=item.get("url", ""),
                    snippet=item.get("content", ""),
                    source_engine=self.name,
                    rank=i + 1,
                    score=1.0 - (i * 0.05),
                    published_date=item.get("publishedDate"),
                    metadata={"engine": item.get("engine", "")},
                ))
            return results

        except Exception as e:
            logger.warning(f"SearXNG search failed: {e}")
            return []

    def is_healthy(self) -> bool:
        try:
            resp = self._session.get(f"{self.base_url}/", timeout=5)
            return resp.status_code == 200
        except Exception:
            return False


# ==================== WIKIPEDIA ENGINE ====================

class WikipediaEngine(BaseSearchEngine):
    """Wikipedia search engine using MediaWiki API."""

    name = "wikipedia"
    is_general = False
    is_knowledge = True
    is_academic = False

    def __init__(self, language: str = "en", timeout: int = 15):
        super().__init__(timeout)
        self.api_url = f"https://{language}.wikipedia.org/w/api.php"

    def search(self, query: str, max_results: int = 5) -> List[SearchResult]:
        try:
            # Search for pages
            resp = self._session.get(self.api_url, params={
                "action": "query",
                "list": "search",
                "srsearch": query,
                "srlimit": max_results,
                "format": "json",
                "srprop": "snippet|timestamp",
            }, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()

            results = []
            for i, item in enumerate(data.get("query", {}).get("search", [])):
                title = item.get("title", "")
                # Clean HTML from snippet
                snippet = re.sub(r'<[^>]+>', '', item.get("snippet", ""))
                url = f"https://en.wikipedia.org/wiki/{quote_plus(title.replace(' ', '_'))}"

                results.append(SearchResult(
                    title=title,
                    url=url,
                    snippet=snippet,
                    source_engine=self.name,
                    rank=i + 1,
                    score=0.9 - (i * 0.05),
                    published_date=item.get("timestamp"),
                    metadata={"wordcount": item.get("wordcount", 0)},
                ))

            # Fetch extracts for top results
            if results:
                page_titles = "|".join([r.title for r in results[:3]])
                try:
                    ext_resp = self._session.get(self.api_url, params={
                        "action": "query",
                        "titles": page_titles,
                        "prop": "extracts",
                        "exintro": True,
                        "explaintext": True,
                        "exlimit": 3,
                        "format": "json",
                    }, timeout=self.timeout)
                    ext_data = ext_resp.json()
                    pages = ext_data.get("query", {}).get("pages", {})
                    for page_id, page in pages.items():
                        extract = page.get("extract", "")
                        if extract:
                            for r in results:
                                if r.title == page.get("title"):
                                    r.content = extract[:3000]
                                    break
                except Exception:
                    pass

            return results

        except Exception as e:
            logger.warning(f"Wikipedia search failed: {e}")
            return []


# ==================== ARXIV ENGINE ====================

class ArxivEngine(BaseSearchEngine):
    """arXiv academic paper search engine."""

    name = "arxiv"
    is_general = False
    is_academic = True
    is_knowledge = False

    def __init__(self, timeout: int = 20):
        super().__init__(timeout)
        self.api_url = "http://export.arxiv.org/api/query"

    def search(self, query: str, max_results: int = 5) -> List[SearchResult]:
        try:
            resp = self._session.get(self.api_url, params={
                "search_query": f"all:{query}",
                "start": 0,
                "max_results": max_results,
                "sortBy": "relevance",
                "sortOrder": "descending",
            }, timeout=self.timeout)
            resp.raise_for_status()

            # Parse XML
            root = ET.fromstring(resp.text)
            ns = {"atom": "http://www.w3.org/2005/Atom"}

            results = []
            for i, entry in enumerate(root.findall("atom:entry", ns)):
                title = entry.find("atom:title", ns)
                summary = entry.find("atom:summary", ns)
                published = entry.find("atom:published", ns)

                # Get authors
                authors = []
                for author in entry.findall("atom:author", ns):
                    name = author.find("atom:name", ns)
                    if name is not None:
                        authors.append(name.text)

                # Get URL
                url = ""
                for link in entry.findall("atom:link", ns):
                    if link.get("type") == "text/html":
                        url = link.get("href", "")
                        break
                if not url:
                    id_elem = entry.find("atom:id", ns)
                    url = id_elem.text if id_elem is not None else ""

                # Get categories
                categories = []
                for cat in entry.findall("atom:category", ns):
                    term = cat.get("term", "")
                    if term:
                        categories.append(term)

                results.append(SearchResult(
                    title=(title.text or "").strip().replace("\n", " "),
                    url=url.replace("http://", "https://"),
                    snippet=(summary.text or "").strip().replace("\n", " ")[:500],
                    source_engine=self.name,
                    rank=i + 1,
                    score=0.85 - (i * 0.05),
                    published_date=(published.text or "")[:10] if published is not None else None,
                    authors=authors[:5],
                    content=(summary.text or "").strip()[:3000],
                    metadata={"categories": categories},
                ))

            return results

        except Exception as e:
            logger.warning(f"arXiv search failed: {e}")
            return []


# ==================== DUCKDUCKGO ENGINE ====================

class DuckDuckGoEngine(BaseSearchEngine):
    """DuckDuckGo search using the Instant Answer API + HTML scraping fallback."""

    name = "duckduckgo"
    is_general = True

    def search(self, query: str, max_results: int = 10) -> List[SearchResult]:
        try:
            # Use DuckDuckGo Instant Answer API
            resp = self._session.get(
                "https://api.duckduckgo.com/",
                params={"q": query, "format": "json", "no_html": 1, "skip_disambig": 1},
                timeout=self.timeout,
            )
            resp.raise_for_status()
            data = resp.json()

            results = []

            # Abstract (main result)
            if data.get("Abstract"):
                results.append(SearchResult(
                    title=data.get("Heading", query),
                    url=data.get("AbstractURL", ""),
                    snippet=data.get("Abstract", ""),
                    source_engine=self.name,
                    rank=1,
                    score=0.95,
                    content=data.get("Abstract", ""),
                    metadata={"source": data.get("AbstractSource", "")},
                ))

            # Related topics
            for i, topic in enumerate(data.get("RelatedTopics", [])[:max_results - len(results)]):
                if isinstance(topic, dict) and topic.get("Text"):
                    results.append(SearchResult(
                        title=topic.get("Text", "")[:100],
                        url=topic.get("FirstURL", ""),
                        snippet=topic.get("Text", ""),
                        source_engine=self.name,
                        rank=len(results) + 1,
                        score=0.8 - (i * 0.05),
                    ))
                elif isinstance(topic, dict) and "Topics" in topic:
                    # Nested topics
                    for sub in topic.get("Topics", [])[:3]:
                        if sub.get("Text"):
                            results.append(SearchResult(
                                title=sub.get("Text", "")[:100],
                                url=sub.get("FirstURL", ""),
                                snippet=sub.get("Text", ""),
                                source_engine=self.name,
                                rank=len(results) + 1,
                                score=0.7,
                            ))

            # Results (from DuckDuckGo search results)
            for i, result in enumerate(data.get("Results", [])[:max_results - len(results)]):
                results.append(SearchResult(
                    title=result.get("Text", "")[:100],
                    url=result.get("FirstURL", ""),
                    snippet=result.get("Text", ""),
                    source_engine=self.name,
                    rank=len(results) + 1,
                    score=0.75 - (i * 0.05),
                ))

            return results[:max_results]

        except Exception as e:
            logger.warning(f"DuckDuckGo search failed: {e}")
            return []


# ==================== BRAVE SEARCH ENGINE ====================

class BraveSearchEngine(BaseSearchEngine):
    """Brave Search API (requires API key)."""

    name = "brave"
    is_general = True

    def __init__(self, api_key: str = None, timeout: int = 15):
        super().__init__(timeout)
        self.api_key = api_key or os.getenv("BRAVE_SEARCH_API_KEY", "")
        self.is_available = bool(self.api_key)

    def search(self, query: str, max_results: int = 10) -> List[SearchResult]:
        if not self.api_key:
            return []

        try:
            resp = self._session.get(
                "https://api.search.brave.com/res/v1/web/search",
                params={"q": query, "count": max_results},
                headers={"X-Subscription-Token": self.api_key, "Accept": "application/json"},
                timeout=self.timeout,
            )
            resp.raise_for_status()
            data = resp.json()

            results = []
            for i, item in enumerate(data.get("web", {}).get("results", [])[:max_results]):
                results.append(SearchResult(
                    title=item.get("title", ""),
                    url=item.get("url", ""),
                    snippet=item.get("description", ""),
                    source_engine=self.name,
                    rank=i + 1,
                    score=0.9 - (i * 0.04),
                    published_date=item.get("page_age"),
                    metadata={"language": item.get("language", "")},
                ))

            return results

        except Exception as e:
            logger.warning(f"Brave search failed: {e}")
            return []


# ==================== DOMAIN CLASSIFIER ====================

class DomainClassifier:
    """Classify query type to route to appropriate search engines."""

    ACADEMIC_KEYWORDS = {
        "research", "paper", "study", "journal", "publication", "thesis",
        "experiment", "hypothesis", "methodology", "peer-reviewed",
        "arxiv", "pubmed", "scientific", "academic", "phd",
        "algorithm", "theorem", "proof", "equation", "neural network",
        "machine learning", "deep learning", "quantum", "biology",
        "chemistry", "physics", "mathematics", "statistics",
    }

    KNOWLEDGE_KEYWORDS = {
        "what is", "who is", "define", "definition", "history of",
        "explain", "how does", "meaning of", "overview", "introduction",
        "concept", "theory", "biography", "wikipedia", "encyclopedia",
    }

    CODE_KEYWORDS = {
        "code", "programming", "github", "repository", "function",
        "library", "api", "sdk", "implementation", "bug", "error",
        "python", "javascript", "java", "c++", "rust", "golang",
        "docker", "kubernetes", "deploy", "devops", "framework",
    }

    NEWS_KEYWORDS = {
        "news", "latest", "today", "yesterday", "breaking",
        "announcement", "update", "release", "launch", "event",
        "2025", "2026", "current", "recent",
    }

    @classmethod
    def classify(cls, query: str) -> List[str]:
        """Classify a query and return recommended engine types.
        Returns list of: 'general', 'academic', 'knowledge', 'code', 'news'
        """
        query_lower = query.lower()
        words = set(query_lower.split())
        types = []

        # Check academic
        academic_score = len(words & cls.ACADEMIC_KEYWORDS)
        if academic_score >= 2 or any(kw in query_lower for kw in ["arxiv", "research paper", "scientific study"]):
            types.append("academic")

        # Check knowledge
        if any(kw in query_lower for kw in cls.KNOWLEDGE_KEYWORDS):
            types.append("knowledge")

        # Check code
        code_score = len(words & cls.CODE_KEYWORDS)
        if code_score >= 2:
            types.append("code")

        # Check news
        if any(kw in query_lower for kw in cls.NEWS_KEYWORDS):
            types.append("news")

        # Always include general as fallback
        if not types or "general" not in types:
            types.append("general")

        return types


# ==================== META SEARCH ENGINE ====================

class MetaSearchEngine:
    """Combines multiple search engines with intelligent routing,
    parallel execution, and result deduplication/ranking."""

    def __init__(self):
        self.engines: Dict[str, BaseSearchEngine] = {}
        self._executor = ThreadPoolExecutor(max_workers=5)
        self._classifier = DomainClassifier()
        self._initialize_engines()

    def _initialize_engines(self):
        """Initialize all available search engines."""
        # SearXNG (primary)
        try:
            searxng = SearXNGEngine()
            self.engines["searxng"] = searxng
        except Exception as e:
            logger.warning(f"SearXNG init failed: {e}")

        # Wikipedia (knowledge)
        try:
            self.engines["wikipedia"] = WikipediaEngine()
        except Exception as e:
            logger.warning(f"Wikipedia init failed: {e}")

        # arXiv (academic)
        try:
            self.engines["arxiv"] = ArxivEngine()
        except Exception as e:
            logger.warning(f"arXiv init failed: {e}")

        # DuckDuckGo (fallback)
        try:
            self.engines["duckduckgo"] = DuckDuckGoEngine()
        except Exception as e:
            logger.warning(f"DuckDuckGo init failed: {e}")

        # Brave (if API key available)
        try:
            brave = BraveSearchEngine()
            if brave.is_available:
                self.engines["brave"] = brave
        except Exception as e:
            logger.warning(f"Brave init failed: {e}")

        logger.info(f"MetaSearchEngine initialized with engines: {list(self.engines.keys())}")

    def search(self, query: str, max_results: int = 15,
               engines: List[str] = None, auto_route: bool = True,
               fetch_content: bool = False) -> List[SearchResult]:
        """
        Execute a search across multiple engines.

        Args:
            query: Search query
            max_results: Maximum total results
            engines: Specific engines to use (None = auto-select)
            auto_route: Use domain classification to select engines
            fetch_content: Whether to fetch full content for top results
        """
        # Determine which engines to use
        selected_engines = self._select_engines(query, engines, auto_route)

        if not selected_engines:
            logger.warning("No search engines available")
            return []

        # Execute searches in parallel
        all_results = []
        futures = {}

        for engine_name in selected_engines:
            engine = self.engines.get(engine_name)
            if engine:
                per_engine = max(5, max_results // len(selected_engines))
                future = self._executor.submit(
                    self._safe_search, engine, query, per_engine
                )
                futures[future] = engine_name

        for future in as_completed(futures, timeout=45):
            engine_name = futures[future]
            try:
                results = future.result()
                all_results.extend(results)
                logger.info(f"Engine {engine_name}: {len(results)} results")
            except Exception as e:
                logger.warning(f"Engine {engine_name} failed: {e}")

        # Deduplicate and rank
        deduped = self._deduplicate(all_results)
        ranked = self._rank_results(deduped, query)

        # Limit results
        final_results = ranked[:max_results]

        # Optionally fetch full content
        if fetch_content and final_results:
            self._fetch_contents(final_results[:5])

        return final_results

    def search_single(self, query: str, engine_name: str,
                      max_results: int = 10) -> List[SearchResult]:
        """Search using a single specific engine."""
        engine = self.engines.get(engine_name)
        if not engine:
            return []
        return self._safe_search(engine, query, max_results)

    def get_available_engines(self) -> List[Dict]:
        """Get list of available search engines with their properties."""
        result = []
        for name, engine in self.engines.items():
            result.append({
                "name": name,
                "is_available": engine.is_available,
                "is_academic": engine.is_academic,
                "is_knowledge": engine.is_knowledge,
                "is_general": engine.is_general,
                "is_code": getattr(engine, "is_code", False),
                "is_news": getattr(engine, "is_news", False),
            })
        return result

    def _select_engines(self, query: str, engines: List[str] = None,
                        auto_route: bool = True) -> List[str]:
        """Select engines based on query classification."""
        if engines:
            return [e for e in engines if e in self.engines]

        if not auto_route:
            return list(self.engines.keys())

        # Use domain classifier
        query_types = self._classifier.classify(query)
        selected = set()

        for qtype in query_types:
            if qtype == "academic":
                if "arxiv" in self.engines:
                    selected.add("arxiv")
            if qtype == "knowledge":
                if "wikipedia" in self.engines:
                    selected.add("wikipedia")
            if qtype == "general":
                if "searxng" in self.engines:
                    selected.add("searxng")
                elif "duckduckgo" in self.engines:
                    selected.add("duckduckgo")
                elif "brave" in self.engines:
                    selected.add("brave")

        # Always include at least one general engine
        if not any(self.engines.get(e, None) and self.engines[e].is_general for e in selected):
            for name in ["searxng", "duckduckgo", "brave"]:
                if name in self.engines:
                    selected.add(name)
                    break

        return list(selected)

    def _safe_search(self, engine: BaseSearchEngine, query: str,
                     max_results: int) -> List[SearchResult]:
        """Execute search with error handling."""
        try:
            return engine.search(query, max_results)
        except Exception as e:
            logger.warning(f"{engine.name} search error: {e}")
            return []

    def _deduplicate(self, results: List[SearchResult]) -> List[SearchResult]:
        """Remove duplicate results based on URL/title similarity."""
        seen_hashes = set()
        seen_urls = set()
        unique = []

        for r in results:
            content_hash = r.content_hash()
            url_normalized = r.url.lower().rstrip("/")

            if content_hash in seen_hashes or url_normalized in seen_urls:
                continue

            seen_hashes.add(content_hash)
            seen_urls.add(url_normalized)
            unique.append(r)

        return unique

    def _rank_results(self, results: List[SearchResult],
                      query: str) -> List[SearchResult]:
        """Rank results by relevance using a simple scoring algorithm."""
        query_terms = set(query.lower().split())

        for r in results:
            score = r.score

            # Boost for query terms in title
            title_lower = r.title.lower()
            title_matches = sum(1 for term in query_terms if term in title_lower)
            score += title_matches * 0.1

            # Boost for content availability
            if r.content:
                score += 0.1

            # Boost for snippet relevance
            snippet_lower = r.snippet.lower()
            snippet_matches = sum(1 for term in query_terms if term in snippet_lower)
            score += snippet_matches * 0.05

            # Boost for academic sources
            if r.source_engine in ("arxiv", "semantic_scholar", "pubmed"):
                score += 0.05

            # Boost for Wikipedia (reliable knowledge)
            if r.source_engine == "wikipedia":
                score += 0.08

            r.score = min(score, 1.0)

        # Sort by score descending
        results.sort(key=lambda x: x.score, reverse=True)

        # Update ranks
        for i, r in enumerate(results):
            r.rank = i + 1

        return results

    def _fetch_contents(self, results: List[SearchResult]):
        """Fetch full content for top results (async-ish)."""
        futures = {}
        for r in results:
            if not r.content and r.url:
                # Use any general engine for content fetching
                engine = next(iter(self.engines.values()), None)
                if engine:
                    future = self._executor.submit(engine.get_full_content, r.url)
                    futures[future] = r

        for future in as_completed(futures, timeout=15):
            result = futures[future]
            try:
                content = future.result()
                if content:
                    result.content = content
            except Exception:
                pass


# ==================== SINGLETON ====================

_meta_search_engine: Optional[MetaSearchEngine] = None


def get_meta_search_engine() -> MetaSearchEngine:
    """Get the singleton meta search engine instance."""
    global _meta_search_engine
    if _meta_search_engine is None:
        _meta_search_engine = MetaSearchEngine()
    return _meta_search_engine
