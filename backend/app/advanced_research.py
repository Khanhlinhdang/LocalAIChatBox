"""
Advanced Research Engine for LocalAIChatBox.
Self-contained deep research with iterative strategies, sub-question decomposition,
knowledge accumulation, structured report generation, and citation tracking.

Replaces the LDR dependency with a fully built-in engine.
Inspired by local-deep-research's AdvancedSearchSystem architecture.
"""

import json
import logging
import os
import re
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Dict, List, Optional, Tuple

import requests

from app.search_engines import MetaSearchEngine, SearchResult, get_meta_search_engine

logger = logging.getLogger(__name__)

# Ollama settings
OLLAMA_URL = os.getenv("OLLAMA_HOST", "http://ollama:11434")
LLM_MODEL = os.getenv("OLLAMA_LLM_MODEL", "llama3.1")


# ==================== DATA MODELS ====================

@dataclass
class ResearchFinding:
    """A single research finding with source tracking."""
    content: str
    source_title: str = ""
    source_url: str = ""
    source_engine: str = ""
    relevance_score: float = 0.0
    sub_question: str = ""
    iteration: int = 0

    def to_dict(self) -> Dict:
        return {
            "content": self.content,
            "source_title": self.source_title,
            "source_url": self.source_url,
            "source_engine": self.source_engine,
            "relevance_score": self.relevance_score,
            "sub_question": self.sub_question,
            "iteration": self.iteration,
        }


@dataclass
class ResearchState:
    """Tracks the state of an ongoing research task."""
    query: str
    strategy: str
    findings: List[ResearchFinding] = field(default_factory=list)
    sources: List[Dict] = field(default_factory=list)
    sub_questions: List[str] = field(default_factory=list)
    answered_questions: List[str] = field(default_factory=list)
    knowledge_summary: str = ""
    iteration: int = 0
    max_iterations: int = 3
    total_searches: int = 0
    total_tokens_used: int = 0
    start_time: float = 0.0
    progress: float = 0.0
    status: str = "pending"
    progress_message: str = ""


# ==================== LLM INTERFACE ====================

class OllamaLLM:
    """Direct Ollama API interface for research tasks."""

    def __init__(self, model: str = None, temperature: float = 0.7,
                 base_url: str = None, context_length: int = 4096):
        self.model = model or LLM_MODEL
        self.temperature = temperature
        self.base_url = base_url or OLLAMA_URL
        self.context_length = context_length
        self._session = requests.Session()

    def generate(self, prompt: str, system: str = None,
                 temperature: float = None, max_tokens: int = None) -> str:
        """Generate a response from the LLM."""
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature or self.temperature,
                "num_ctx": self.context_length,
            },
        }
        if system:
            payload["system"] = system
        if max_tokens:
            payload["options"]["num_predict"] = max_tokens

        try:
            resp = self._session.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=120,
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("response", "")
        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            return f"Error: LLM generation failed - {str(e)}"

    def chat(self, messages: List[Dict], temperature: float = None) -> str:
        """Chat-style generation."""
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature or self.temperature,
                "num_ctx": self.context_length,
            },
        }

        try:
            resp = self._session.post(
                f"{self.base_url}/api/chat",
                json=payload,
                timeout=120,
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("message", {}).get("content", "")
        except Exception as e:
            logger.error(f"LLM chat failed: {e}")
            return f"Error: LLM chat failed - {str(e)}"


# ==================== RESEARCH STRATEGIES ====================

class BaseStrategy:
    """Base research strategy."""

    name: str = "base"
    description: str = "Base strategy"

    def __init__(self, llm: OllamaLLM, search_engine: MetaSearchEngine,
                 max_iterations: int = 3, questions_per_iteration: int = 3,
                 progress_callback: Callable = None):
        self.llm = llm
        self.search = search_engine
        self.max_iterations = max_iterations
        self.questions_per_iter = questions_per_iteration
        self.progress_cb = progress_callback or (lambda p, m: None)

    def execute(self, query: str) -> ResearchState:
        """Execute the research strategy. Override in subclasses."""
        raise NotImplementedError


class RapidStrategy(BaseStrategy):
    """Speed-optimized single-pass search. Best for quick answers."""

    name = "rapid"
    description = "Single-pass search for quick answers"

    def execute(self, query: str) -> ResearchState:
        state = ResearchState(query=query, strategy=self.name, max_iterations=1)
        state.start_time = time.time()
        state.status = "running"

        self.progress_cb(10, "Searching for information...")

        # Single search pass
        results = self.search.search(query, max_results=10, fetch_content=True)
        state.total_searches += 1

        self.progress_cb(40, f"Found {len(results)} results, analyzing...")

        # Build context from results
        context = self._build_context(results)
        state.sources = [r.to_dict() for r in results]

        # Generate answer
        self.progress_cb(60, "Generating answer...")
        answer = self._generate_answer(query, context)
        state.knowledge_summary = answer

        # Extract findings
        for r in results:
            state.findings.append(ResearchFinding(
                content=r.snippet or r.content[:500],
                source_title=r.title,
                source_url=r.url,
                source_engine=r.source_engine,
                relevance_score=r.score,
                sub_question=query,
                iteration=1,
            ))

        state.progress = 100
        state.status = "completed"
        state.progress_message = "Research completed"
        self.progress_cb(100, "Research completed")
        return state

    def _build_context(self, results: List[SearchResult]) -> str:
        parts = []
        for i, r in enumerate(results[:8], 1):
            content = r.content or r.snippet
            if content:
                parts.append(f"[Source {i}: {r.title}]\n{content[:800]}\nURL: {r.url}\n")
        return "\n---\n".join(parts)

    def _generate_answer(self, query: str, context: str) -> str:
        prompt = f"""Based on the following search results, provide a comprehensive answer to the question.
Include inline citations like [1], [2] etc. referring to the source numbers.

Question: {query}

Search Results:
{context}

Instructions:
- Provide a detailed, well-structured answer
- Use inline citations [1], [2] etc. to reference sources
- If information is insufficient, state what is known and what needs more research
- Be factual and objective

Answer:"""
        return self.llm.generate(prompt, temperature=0.3)


class IterativeStrategy(BaseStrategy):
    """Iterative research with sub-question decomposition and knowledge accumulation."""

    name = "iterative"
    description = "Multi-iteration research with sub-question decomposition"

    def execute(self, query: str) -> ResearchState:
        state = ResearchState(
            query=query, strategy=self.name,
            max_iterations=self.max_iterations,
        )
        state.start_time = time.time()
        state.status = "running"

        # Step 1: Decompose query into sub-questions
        self.progress_cb(5, "Analyzing query and generating sub-questions...")
        sub_questions = self._decompose_query(query)
        state.sub_questions = sub_questions

        progress_per_iter = 70.0 / self.max_iterations

        for iteration in range(1, self.max_iterations + 1):
            state.iteration = iteration
            base_progress = 10 + (iteration - 1) * progress_per_iter

            # Get unanswered questions
            remaining = [q for q in state.sub_questions if q not in state.answered_questions]
            if not remaining:
                # Generate follow-up questions based on gaps
                self.progress_cb(
                    base_progress, f"Iteration {iteration}: Identifying knowledge gaps..."
                )
                new_questions = self._identify_gaps(query, state.knowledge_summary)
                if not new_questions:
                    break
                remaining = new_questions
                state.sub_questions.extend(new_questions)

            # Research each sub-question
            questions_to_research = remaining[:self.questions_per_iter]
            for qi, sub_q in enumerate(questions_to_research):
                sub_progress = base_progress + (qi / len(questions_to_research)) * progress_per_iter
                self.progress_cb(
                    sub_progress,
                    f"Iteration {iteration}/{self.max_iterations}: Researching: {sub_q[:60]}..."
                )

                # Search
                results = self.search.search(sub_q, max_results=8, fetch_content=True)
                state.total_searches += 1

                # Add findings
                for r in results:
                    state.findings.append(ResearchFinding(
                        content=r.content or r.snippet,
                        source_title=r.title,
                        source_url=r.url,
                        source_engine=r.source_engine,
                        relevance_score=r.score,
                        sub_question=sub_q,
                        iteration=iteration,
                    ))
                    # Add source if not duplicate
                    if not any(s.get("url") == r.url for s in state.sources):
                        state.sources.append(r.to_dict())

                state.answered_questions.append(sub_q)

            # Synthesize knowledge after each iteration
            self.progress_cb(
                base_progress + progress_per_iter * 0.9,
                f"Iteration {iteration}: Synthesizing findings..."
            )
            state.knowledge_summary = self._synthesize(query, state)

        # Final synthesis
        self.progress_cb(85, "Generating final comprehensive answer...")
        state.knowledge_summary = self._final_synthesis(query, state)

        state.progress = 100
        state.status = "completed"
        state.progress_message = "Research completed"
        self.progress_cb(100, "Research completed")
        return state

    def _decompose_query(self, query: str) -> List[str]:
        prompt = f"""Break down this research question into {self.questions_per_iter} specific sub-questions
that would help answer the main question comprehensively.

Main question: {query}

Return ONLY the sub-questions, one per line, numbered 1-{self.questions_per_iter}.
Each sub-question should be specific and searchable.

Sub-questions:"""
        response = self.llm.generate(prompt, temperature=0.3)
        questions = []
        for line in response.strip().split("\n"):
            line = re.sub(r'^\d+[\.\)]\s*', '', line.strip())
            if line and len(line) > 10:
                questions.append(line)
        return questions[:self.questions_per_iter] if questions else [query]

    def _identify_gaps(self, query: str, current_knowledge: str) -> List[str]:
        if not current_knowledge:
            return []
        prompt = f"""Based on the original question and the current research findings,
identify 2-3 knowledge gaps or follow-up questions that would improve the answer.

Original question: {query}

Current findings (summary):
{current_knowledge[:2000]}

If the current findings are comprehensive enough, respond with "COMPLETE".
Otherwise, list 2-3 follow-up questions, one per line:"""

        response = self.llm.generate(prompt, temperature=0.3)
        if "COMPLETE" in response.upper():
            return []

        questions = []
        for line in response.strip().split("\n"):
            line = re.sub(r'^\d+[\.\)]\s*', '', line.strip())
            if line and len(line) > 10 and "complete" not in line.lower():
                questions.append(line)
        return questions[:3]

    def _synthesize(self, query: str, state: ResearchState) -> str:
        # Build findings context
        findings_text = ""
        for i, f in enumerate(state.findings[-15:], 1):  # Last 15 findings
            findings_text += f"[{i}] {f.source_title}: {f.content[:300]}\n"

        prompt = f"""Synthesize the following research findings into a coherent summary.

Original question: {query}

Research findings:
{findings_text}

Previous summary:
{state.knowledge_summary[:1000] if state.knowledge_summary else 'None yet'}

Create an updated, comprehensive summary with inline citations [1], [2], etc.
Focus on answering the original question.

Summary:"""
        return self.llm.generate(prompt, temperature=0.3)

    def _final_synthesis(self, query: str, state: ResearchState) -> str:
        # Build source reference list
        sources_text = ""
        for i, s in enumerate(state.sources[:20], 1):
            sources_text += f"[{i}] {s.get('title', 'Unknown')} - {s.get('url', '')}\n"

        prompt = f"""Create a comprehensive, well-structured research answer based on all findings.

Original question: {query}

Research Summary:
{state.knowledge_summary[:3000]}

Sources:
{sources_text}

Instructions:
- Write a detailed, well-organized answer
- Use clear headings and sections (## for main sections, ### for sub-sections)
- Include inline citations [1], [2] etc.
- End with a "## Sources" section listing all referenced sources
- Be thorough but avoid speculation
- Synthesize information from multiple sources

Answer:"""
        return self.llm.generate(prompt, temperature=0.3, max_tokens=4000)


class FocusedIterationStrategy(IterativeStrategy):
    """Focused iteration with adaptive refinement.
    Achieves higher accuracy by focusing search based on initial findings."""

    name = "focused-iteration"
    description = "Adaptive refinement with focused search for highest accuracy"

    def execute(self, query: str) -> ResearchState:
        state = ResearchState(
            query=query, strategy=self.name,
            max_iterations=self.max_iterations,
        )
        state.start_time = time.time()
        state.status = "running"

        # Step 1: Initial broad search
        self.progress_cb(5, "Performing initial broad search...")
        initial_results = self.search.search(query, max_results=12, fetch_content=True)
        state.total_searches += 1

        for r in initial_results:
            state.findings.append(ResearchFinding(
                content=r.content or r.snippet,
                source_title=r.title,
                source_url=r.url,
                source_engine=r.source_engine,
                relevance_score=r.score,
                sub_question=query,
                iteration=0,
            ))
            state.sources.append(r.to_dict())

        # Step 2: Analyze initial results and identify focus areas
        self.progress_cb(15, "Analyzing initial results...")
        focus_areas = self._analyze_and_focus(query, initial_results)

        progress_per_iter = 60.0 / max(self.max_iterations, 1)

        for iteration in range(1, self.max_iterations + 1):
            state.iteration = iteration
            base_progress = 20 + (iteration - 1) * progress_per_iter

            # Search focused areas
            for fi, focus in enumerate(focus_areas[:self.questions_per_iter]):
                sub_progress = base_progress + (fi / len(focus_areas)) * progress_per_iter
                self.progress_cb(
                    sub_progress,
                    f"Iteration {iteration}: Deep-diving into: {focus[:60]}..."
                )

                # Use targeted search terms
                focused_results = self.search.search(
                    focus, max_results=6, fetch_content=True
                )
                state.total_searches += 1

                for r in focused_results:
                    state.findings.append(ResearchFinding(
                        content=r.content or r.snippet,
                        source_title=r.title,
                        source_url=r.url,
                        source_engine=r.source_engine,
                        relevance_score=r.score,
                        sub_question=focus,
                        iteration=iteration,
                    ))
                    if not any(s.get("url") == r.url for s in state.sources):
                        state.sources.append(r.to_dict())

                state.answered_questions.append(focus)

            # Evaluate and refine focus
            self.progress_cb(
                base_progress + progress_per_iter * 0.8,
                f"Iteration {iteration}: Evaluating findings..."
            )
            state.knowledge_summary = self._synthesize(query, state)

            # Check if we have enough information
            if iteration < self.max_iterations:
                confidence = self._evaluate_confidence(query, state.knowledge_summary)
                if confidence > 0.85:
                    self.progress_cb(80, "High confidence achieved, preparing final answer...")
                    break

                # Refine focus areas for next iteration
                focus_areas = self._refine_focus(query, state)

        # Final synthesis with confidence assessment
        self.progress_cb(85, "Generating comprehensive answer...")
        state.knowledge_summary = self._final_synthesis(query, state)

        state.progress = 100
        state.status = "completed"
        state.progress_message = "Research completed"
        self.progress_cb(100, "Research completed")
        return state

    def _analyze_and_focus(self, query: str, results: List[SearchResult]) -> List[str]:
        context = "\n".join([
            f"- {r.title}: {r.snippet[:200]}" for r in results[:8]
        ])
        prompt = f"""Analyze these initial search results and identify {self.questions_per_iter}
specific focus areas that need deeper investigation to fully answer the question.

Question: {query}

Initial results:
{context}

List {self.questions_per_iter} specific, searchable focus queries that would uncover
important details not covered in the initial results. One per line:"""

        response = self.llm.generate(prompt, temperature=0.3)
        focuses = []
        for line in response.strip().split("\n"):
            line = re.sub(r'^\d+[\.\)]\s*', '', line.strip())
            if line and len(line) > 10:
                focuses.append(line)
        return focuses[:self.questions_per_iter + 1]

    def _evaluate_confidence(self, query: str, knowledge: str) -> float:
        prompt = f"""Rate the confidence level of this answer on a scale of 0.0 to 1.0.
Consider completeness, accuracy indicators, and source quality.

Question: {query}

Current answer:
{knowledge[:2000]}

Respond with ONLY a number between 0.0 and 1.0:"""

        response = self.llm.generate(prompt, temperature=0.1, max_tokens=10)
        try:
            score = float(re.search(r'(0\.\d+|1\.0|0|1)', response).group(1))
            return min(max(score, 0.0), 1.0)
        except (AttributeError, ValueError):
            return 0.5

    def _refine_focus(self, query: str, state: ResearchState) -> List[str]:
        return self._identify_gaps(query, state.knowledge_summary)


class ParallelStrategy(BaseStrategy):
    """Parallel multi-query search for thorough coverage."""

    name = "parallel"
    description = "Concurrent multi-query search for comprehensive coverage"

    def execute(self, query: str) -> ResearchState:
        state = ResearchState(
            query=query, strategy=self.name,
            max_iterations=1,
        )
        state.start_time = time.time()
        state.status = "running"

        # Step 1: Generate multiple search queries
        self.progress_cb(5, "Generating search variations...")
        queries = self._generate_query_variations(query)
        state.sub_questions = queries

        # Step 2: Search all queries in parallel
        self.progress_cb(15, f"Searching {len(queries)} queries in parallel...")
        all_results = []
        executor = ThreadPoolExecutor(max_workers=4)
        futures = {}

        for q in queries:
            future = executor.submit(
                self.search.search, q, 8, None, True, True
            )
            futures[future] = q

        completed = 0
        for future in as_completed(futures, timeout=60):
            completed += 1
            q = futures[future]
            progress = 15 + (completed / len(queries)) * 50
            self.progress_cb(progress, f"Processing results ({completed}/{len(queries)})...")

            try:
                results = future.result()
                for r in results:
                    state.findings.append(ResearchFinding(
                        content=r.content or r.snippet,
                        source_title=r.title,
                        source_url=r.url,
                        source_engine=r.source_engine,
                        relevance_score=r.score,
                        sub_question=q,
                        iteration=1,
                    ))
                    if not any(s.get("url") == r.url for s in state.sources):
                        state.sources.append(r.to_dict())
                state.total_searches += 1
                state.answered_questions.append(q)
            except Exception as e:
                logger.warning(f"Parallel query failed for '{q}': {e}")

        executor.shutdown(wait=False)

        # Step 3: Synthesize all results
        self.progress_cb(70, "Synthesizing parallel research results...")
        state.knowledge_summary = self._final_synthesis(query, state)

        state.progress = 100
        state.status = "completed"
        state.progress_message = "Research completed"
        self.progress_cb(100, "Research completed")
        return state

    def _generate_query_variations(self, query: str) -> List[str]:
        prompt = f"""Generate {self.questions_per_iter + 2} different search queries that would help
comprehensively answer this question. Each query should approach the topic from
a different angle or focus on different aspects.

Question: {query}

Generate search queries, one per line:"""

        response = self.llm.generate(prompt, temperature=0.5)
        queries = [query]  # Always include original
        for line in response.strip().split("\n"):
            line = re.sub(r'^\d+[\.\)]\s*', '', line.strip())
            if line and len(line) > 10 and line not in queries:
                queries.append(line)
        return queries[:self.questions_per_iter + 2]

    def _final_synthesis(self, query: str, state: ResearchState) -> str:
        sources_text = ""
        for i, s in enumerate(state.sources[:20], 1):
            sources_text += f"[{i}] {s.get('title', 'Unknown')} - {s.get('url', '')}\n"

        findings_text = ""
        for i, f in enumerate(state.findings[:20], 1):
            findings_text += f"[{i}] ({f.source_engine}) {f.source_title}: {f.content[:300]}\n\n"

        prompt = f"""Create a comprehensive research answer by synthesizing these parallel search results.

Question: {query}

Research Findings:
{findings_text}

Sources:
{sources_text}

Instructions:
- Create a well-structured answer with headings
- Include inline citations [1], [2] etc.
- Cover all aspects found across different search queries
- End with a Sources section

Answer:"""
        return self.llm.generate(prompt, temperature=0.3, max_tokens=4000)


class SourceBasedStrategy(IterativeStrategy):
    """Comprehensive source tracking with detailed citations. Default strategy."""

    name = "source-based"
    description = "Comprehensive research with detailed source tracking and citations"

    def _final_synthesis(self, query: str, state: ResearchState) -> str:
        # Enhanced source tracking
        source_details = []
        for i, s in enumerate(state.sources[:25], 1):
            detail = f"[{i}] Title: {s.get('title', 'Unknown')}\n"
            detail += f"    URL: {s.get('url', '')}\n"
            detail += f"    Engine: {s.get('source_engine', '')}\n"
            if s.get('authors'):
                detail += f"    Authors: {', '.join(s['authors'][:3])}\n"
            if s.get('published_date'):
                detail += f"    Date: {s['published_date']}\n"
            snippet = s.get('snippet', s.get('content', ''))[:200]
            detail += f"    Excerpt: {snippet}\n"
            source_details.append(detail)

        sources_text = "\n".join(source_details)

        findings_by_question = {}
        for f in state.findings:
            q = f.sub_question
            if q not in findings_by_question:
                findings_by_question[q] = []
            findings_by_question[q].append(f)

        findings_text = ""
        for q, findings in findings_by_question.items():
            findings_text += f"\n### Sub-question: {q}\n"
            for f in findings[:5]:
                findings_text += f"- [{f.source_title}]: {f.content[:300]}\n"

        prompt = f"""Create a comprehensive, well-sourced research report.

Original Question: {query}

Research organized by sub-questions:
{findings_text[:4000]}

Detailed Source Information:
{sources_text}

Instructions:
- Write a thorough, academic-style answer
- Use ## headings for main sections, ### for sub-sections
- Include inline citations [1], [2] etc. throughout
- Every major claim must have a citation
- End with:
  ## Sources
  List all sources with numbers, titles, and URLs
- Be comprehensive but factual

Research Report:"""
        return self.llm.generate(prompt, temperature=0.2, max_tokens=4000)


class SmartStrategy(BaseStrategy):
    """Auto-selects the best strategy based on query analysis."""

    name = "smart"
    description = "Automatically selects the best strategy for the query"

    def execute(self, query: str) -> ResearchState:
        self.progress_cb(2, "Analyzing query to select best research strategy...")
        strategy_name = self._select_strategy(query)
        self.progress_cb(5, f"Selected strategy: {strategy_name}")

        strategy = STRATEGY_MAP.get(strategy_name, IterativeStrategy)(
            llm=self.llm,
            search_engine=self.search,
            max_iterations=self.max_iterations,
            questions_per_iteration=self.questions_per_iter,
            progress_callback=self.progress_cb,
        )
        return strategy.execute(query)

    def _select_strategy(self, query: str) -> str:
        prompt = f"""Analyze this research query and determine the best research strategy.

Query: {query}

Available strategies:
1. "rapid" - Quick single-pass search. Best for simple factual questions.
2. "iterative" - Multi-iteration with sub-question decomposition. Best for complex topics.
3. "focused-iteration" - Adaptive refinement. Best for topics needing deep analysis.
4. "parallel" - Concurrent multi-query. Best for broad topics needing multiple perspectives.
5. "source-based" - Comprehensive source tracking. Best for academic or well-cited research.

Respond with ONLY the strategy name (e.g., "iterative"):"""

        response = self.llm.generate(prompt, temperature=0.1, max_tokens=20)
        strategy = response.strip().lower().strip('"\'')

        if strategy in STRATEGY_MAP:
            return strategy
        return "iterative"  # Default


# Strategy registry
STRATEGY_MAP = {
    "rapid": RapidStrategy,
    "iterative": IterativeStrategy,
    "focused-iteration": FocusedIterationStrategy,
    "parallel": ParallelStrategy,
    "source-based": SourceBasedStrategy,
    "smart": SmartStrategy,
}

# Available strategies list (for API)
STRATEGIES = [
    {"id": "source-based", "name": "Source-Based", "description": "Comprehensive source tracking with citations (default)", "best_for": "General research with proper citations"},
    {"id": "rapid", "name": "Rapid", "description": "Speed-optimized single-pass search", "best_for": "Quick factual answers"},
    {"id": "parallel", "name": "Parallel", "description": "Concurrent multi-query search", "best_for": "Broad topics needing multiple perspectives"},
    {"id": "iterative", "name": "Iterative", "description": "Multi-iteration with sub-question decomposition", "best_for": "Complex topics requiring deep analysis"},
    {"id": "focused-iteration", "name": "Focused Iteration", "description": "Adaptive refinement with confidence scoring", "best_for": "High-accuracy deep analysis"},
    {"id": "smart", "name": "Smart", "description": "Auto-selects best strategy for the query", "best_for": "Any topic (automatic selection)"},
]


# ==================== REPORT GENERATOR ====================

class ReportGenerator:
    """Generate structured reports from research findings.
    Inspired by LDR's IntegratedReportGenerator."""

    def __init__(self, llm: OllamaLLM, search_engine: MetaSearchEngine = None):
        self.llm = llm
        self.search = search_engine

    def generate_report(self, query: str, state: ResearchState,
                        searches_per_section: int = 1) -> str:
        """Generate a structured report with sections."""

        # Step 1: Determine report structure
        sections = self._plan_structure(query, state.knowledge_summary)

        # Step 2: Generate each section
        report_parts = []
        report_parts.append(f"# Research Report: {query}\n")
        report_parts.append(f"*Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}*\n")
        report_parts.append(f"*Strategy: {state.strategy} | Sources: {len(state.sources)} | Iterations: {state.iteration}*\n\n")

        # Executive summary
        report_parts.append("## Executive Summary\n\n")
        summary = self._generate_executive_summary(query, state)
        report_parts.append(summary + "\n\n")

        # Table of Contents
        report_parts.append("## Table of Contents\n\n")
        for i, section in enumerate(sections, 1):
            report_parts.append(f"{i}. [{section}](#{section.lower().replace(' ', '-')})\n")
        report_parts.append("\n")

        # Generate sections
        previous_sections = ""
        for i, section_title in enumerate(sections):
            report_parts.append(f"## {section_title}\n\n")

            # Optionally do additional targeted search per section
            additional_context = ""
            if self.search and searches_per_section > 0:
                section_results = self.search.search(
                    f"{query} {section_title}", max_results=5, fetch_content=True
                )
                for r in section_results:
                    additional_context += f"- {r.title}: {r.snippet[:200]}\n"
                    if not any(s.get("url") == r.url for s in state.sources):
                        state.sources.append(r.to_dict())

            section_content = self._generate_section(
                query, section_title, state, previous_sections, additional_context
            )
            report_parts.append(section_content + "\n\n")
            previous_sections += f"\n{section_title}: {section_content[:500]}\n"

        # Sources / Bibliography
        report_parts.append("## Sources\n\n")
        for i, s in enumerate(state.sources[:30], 1):
            title = s.get("title", "Unknown Source")
            url = s.get("url", "")
            engine = s.get("source_engine", "")
            authors = ", ".join(s.get("authors", [])[:3]) if s.get("authors") else ""
            date = s.get("published_date", "")

            entry = f"{i}. **{title}**"
            if authors:
                entry += f" - {authors}"
            if date:
                entry += f" ({date})"
            if url:
                entry += f"\n   {url}"
            if engine:
                entry += f" [{engine}]"
            report_parts.append(entry + "\n\n")

        return "\n".join(report_parts)

    def _plan_structure(self, query: str, knowledge: str) -> List[str]:
        prompt = f"""Plan the structure for a research report on this topic.

Topic: {query}

Available research summary:
{knowledge[:2000]}

Generate 4-6 section titles that would create a comprehensive report.
Return ONLY section titles, one per line. Do NOT include "Introduction",
"Executive Summary", "Conclusion", or "Sources" as those are added automatically.

Section titles:"""

        response = self.llm.generate(prompt, temperature=0.3)
        sections = []
        for line in response.strip().split("\n"):
            line = re.sub(r'^\d+[\.\)]\s*', '', line.strip())
            line = line.strip("- *#")
            if line and len(line) > 3:
                sections.append(line)

        if not sections:
            sections = ["Background", "Key Findings", "Analysis", "Implications"]

        # Always add conclusion
        if not any("conclusion" in s.lower() for s in sections):
            sections.append("Conclusion")

        return sections[:7]

    def _generate_executive_summary(self, query: str, state: ResearchState) -> str:
        prompt = f"""Write a concise executive summary (2-3 paragraphs) for a research report.

Topic: {query}
Key findings: {state.knowledge_summary[:2000]}
Number of sources: {len(state.sources)}

Write a clear, professional executive summary:"""
        return self.llm.generate(prompt, temperature=0.3, max_tokens=500)

    def _generate_section(self, query: str, section_title: str,
                          state: ResearchState, previous_sections: str,
                          additional_context: str) -> str:
        # Find relevant findings for this section
        relevant_findings = ""
        for f in state.findings:
            if any(word in f.content.lower() for word in section_title.lower().split()):
                relevant_findings += f"- {f.source_title}: {f.content[:300]}\n"
        relevant_findings = relevant_findings[:2000]

        prompt = f"""Write the "{section_title}" section of a research report about: {query}

Previous sections covered:
{previous_sections[:1000]}

Relevant research findings:
{relevant_findings}

Additional context:
{additional_context[:1000]}

Overall research summary:
{state.knowledge_summary[:1500]}

Write a detailed section (3-5 paragraphs) with inline citations [n].
Use ### for subsections if appropriate.

{section_title}:"""
        return self.llm.generate(prompt, temperature=0.3, max_tokens=1500)


# ==================== MAIN RESEARCH ENGINE ====================

class AdvancedResearchEngine:
    """Main research engine that coordinates strategies and report generation."""

    def __init__(self):
        self.search_engine = get_meta_search_engine()
        self._default_model = LLM_MODEL
        self._default_url = OLLAMA_URL

    def create_llm(self, settings: Dict = None) -> OllamaLLM:
        """Create an LLM instance from settings."""
        settings = settings or {}
        return OllamaLLM(
            model=settings.get("llm.model", self._default_model),
            temperature=settings.get("llm.temperature", 0.7),
            base_url=settings.get("llm.ollama.url", self._default_url),
            context_length=settings.get("llm.context_length", 4096),
        )

    def run_research(self, query: str, strategy: str = "source-based",
                     settings: Dict = None,
                     progress_callback: Callable = None) -> ResearchState:
        """Execute a research task."""
        settings = settings or {}
        llm = self.create_llm(settings)

        max_iterations = settings.get("search.iterations", 3)
        questions_per_iter = settings.get("search.questions_per_iteration", 3)

        strategy_class = STRATEGY_MAP.get(strategy, SourceBasedStrategy)
        strategy_instance = strategy_class(
            llm=llm,
            search_engine=self.search_engine,
            max_iterations=max_iterations,
            questions_per_iteration=questions_per_iter,
            progress_callback=progress_callback or (lambda p, m: None),
        )

        return strategy_instance.execute(query)

    def generate_report(self, query: str, state: ResearchState,
                        settings: Dict = None) -> str:
        """Generate a detailed report from research findings."""
        settings = settings or {}
        llm = self.create_llm(settings)
        searches_per_section = settings.get("report.searches_per_section", 1)

        generator = ReportGenerator(llm, self.search_engine)
        return generator.generate_report(query, state, searches_per_section)


# ==================== SINGLETON ====================

_engine: Optional[AdvancedResearchEngine] = None


def get_research_engine() -> AdvancedResearchEngine:
    global _engine
    if _engine is None:
        _engine = AdvancedResearchEngine()
    return _engine
