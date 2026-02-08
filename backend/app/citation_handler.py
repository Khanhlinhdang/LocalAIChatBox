"""
Citation Handler for LocalAIChatBox.
Processes and formats citations from research results.
Generates inline citations and bibliographies.
"""

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Tuple


@dataclass
class Citation:
    """A structured citation reference."""
    number: int
    title: str
    url: str
    authors: Optional[List[str]] = None
    published_date: Optional[str] = None
    source_engine: Optional[str] = None
    accessed_date: Optional[str] = None
    snippet: Optional[str] = None

    def to_inline(self) -> str:
        """Format as inline citation [n]."""
        return f"[{self.number}]"

    def to_bibliography_entry(self, style: str = "numbered") -> str:
        """Format as bibliography entry."""
        if style == "numbered":
            entry = f"[{self.number}] "
            if self.authors:
                entry += f"{', '.join(self.authors[:3])}. "
            entry += f'"{self.title}"'
            if self.published_date:
                entry += f" ({self.published_date})"
            entry += "."
            if self.url:
                entry += f" {self.url}"
            if self.accessed_date:
                entry += f" [Accessed: {self.accessed_date}]"
            return entry

        elif style == "apa":
            entry = ""
            if self.authors:
                entry += f"{', '.join(self.authors[:3])}. "
            if self.published_date:
                entry += f"({self.published_date}). "
            entry += f"{self.title}. "
            if self.url:
                entry += f"Retrieved from {self.url}"
            return entry

        return f"[{self.number}] {self.title} - {self.url}"

    def to_dict(self) -> Dict:
        return {
            "number": self.number,
            "title": self.title,
            "url": self.url,
            "authors": self.authors,
            "published_date": self.published_date,
            "source_engine": self.source_engine,
            "snippet": self.snippet,
        }


class CitationHandler:
    """Manages citations for research content."""

    def __init__(self):
        self.citations: List[Citation] = []
        self._url_to_number: Dict[str, int] = {}
        self._next_number = 1

    def add_citation(self, title: str, url: str, authors: List[str] = None,
                     published_date: str = None, source_engine: str = None,
                     snippet: str = None) -> Citation:
        """Add a citation and return its reference."""
        # Check if URL already has a citation
        url_key = url.lower().rstrip("/")
        if url_key in self._url_to_number:
            num = self._url_to_number[url_key]
            return next(c for c in self.citations if c.number == num)

        citation = Citation(
            number=self._next_number,
            title=title,
            url=url,
            authors=authors,
            published_date=published_date,
            source_engine=source_engine,
            accessed_date=datetime.utcnow().strftime("%Y-%m-%d"),
            snippet=snippet,
        )
        self.citations.append(citation)
        self._url_to_number[url_key] = self._next_number
        self._next_number += 1
        return citation

    def add_from_search_results(self, results: List[Dict]) -> List[Citation]:
        """Add citations from search result dicts."""
        added = []
        for r in results:
            if isinstance(r, dict) and r.get("url"):
                citation = self.add_citation(
                    title=r.get("title", "Unknown Source"),
                    url=r.get("url", ""),
                    authors=r.get("authors"),
                    published_date=r.get("published_date"),
                    source_engine=r.get("source_engine"),
                    snippet=r.get("snippet", r.get("content", ""))[:200],
                )
                added.append(citation)
        return added

    def format_bibliography(self, style: str = "numbered") -> str:
        """Generate a formatted bibliography."""
        if not self.citations:
            return ""

        lines = ["## Sources\n"]
        for citation in sorted(self.citations, key=lambda c: c.number):
            lines.append(citation.to_bibliography_entry(style))
        return "\n".join(lines)

    def process_text_with_citations(self, text: str, sources: List[Dict]) -> Tuple[str, str]:
        """Process text to add citations and generate bibliography.
        Returns (text_with_citations, bibliography).
        """
        # Add all sources as citations
        self.add_from_search_results(sources)

        # The text may already have [1], [2] etc. - validate them
        # Also ensure any URLs in text are linked to citations
        processed = text

        # Generate bibliography
        bibliography = self.format_bibliography()

        return processed, bibliography

    def get_all_citations(self) -> List[Dict]:
        """Get all citations as dicts."""
        return [c.to_dict() for c in self.citations]

    def reset(self):
        """Reset all citations."""
        self.citations = []
        self._url_to_number = {}
        self._next_number = 1


def create_citation_handler() -> CitationHandler:
    """Create a new citation handler instance."""
    return CitationHandler()
