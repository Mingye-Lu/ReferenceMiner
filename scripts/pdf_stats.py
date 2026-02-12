from __future__ import annotations

import argparse
import asyncio
import logging
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from refminer.crawler.base import BaseCrawler
from refminer.crawler.manager import CrawlerManager
from refminer.crawler.models import SearchQuery, SearchResult


async def _run(
    query: str,
    max_results: int,
    engines: list[str],
    include_all: bool,
    strict: bool,
    debug_snippet: bool,
) -> int:
    async with CrawlerManager() as manager:
        available = manager.list_engines()
        enabled = manager.list_enabled_engines()

        if engines:
            selected = _normalize_engine_list(engines)
        elif include_all:
            selected = available
        else:
            selected = enabled

        if not selected:
            print("No engines selected.")
            return 1

        unknown = [name for name in selected if name not in available]
        if unknown:
            print("Unknown engines: {names}".format(names=", ".join(sorted(unknown))))
            return 1

        search_query = SearchQuery(
            query=query,
            engines=[],
            max_results=max_results,
            year_from=None,
            year_to=None,
            include_abstract=False,
            fields=None,
        )
        tasks = []
        for engine_name in selected:
            engine = manager.get_engine(engine_name)
            if engine is None:
                continue
            tasks.append(_search_engine(engine_name, engine, search_query))

        results_by_engine = await asyncio.gather(*tasks)

    overall_total = 0
    overall_pdf = 0
    had_error = False
    for engine_name, results, error in results_by_engine:
        if error is not None:
            had_error = True
            print(
                "engine={engine} error={error}".format(engine=engine_name, error=error)
            )
            continue
        pdf_count = sum(1 for result in results if result.pdf_url)
        total = len(results)
        ratio = (pdf_count / total) if total else 0
        overall_total += total
        overall_pdf += pdf_count
        print(
            "engine={engine} query={query} total={total} pdf_count={pdf_count} pdf_ratio={ratio:.2%}".format(
                engine=engine_name,
                query=query,
                total=total,
                pdf_count=pdf_count,
                ratio=ratio,
            )
        )
        if debug_snippet and total == 0:
            snippet = await _build_zero_result_debug_snippet(
                manager.get_engine(engine_name), search_query
            )
            if snippet:
                print(
                    "engine={engine} debug_snippet={snippet}".format(
                        engine=engine_name, snippet=snippet
                    )
                )

    if len(results_by_engine) > 1:
        overall_ratio = (overall_pdf / overall_total) if overall_total else 0
        print(
            "overall total={total} pdf_count={pdf_count} pdf_ratio={ratio:.2%}".format(
                total=overall_total, pdf_count=overall_pdf, ratio=overall_ratio
            )
        )
    if strict and had_error:
        return 1
    return 0


def _sanitize_snippet(raw_text: str, limit: int = 160) -> str:
    text = re.sub(r"<[^>]+>", " ", raw_text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > limit:
        return f"{text[:limit]}..."
    return text


async def _build_zero_result_debug_snippet(
    engine: BaseCrawler | None, query: SearchQuery
) -> str | None:
    if engine is None:
        return None

    target_url: str | None = None
    build_search_url = getattr(engine, "_build_search_url", None)
    if callable(build_search_url):
        try:
            url_value = build_search_url(query, 1)
            if isinstance(url_value, str) and url_value.strip():
                target_url = url_value
        except Exception:
            target_url = None

    if target_url is None:
        base_url = getattr(engine, "base_url", None)
        if isinstance(base_url, str) and base_url.strip():
            target_url = base_url

    if target_url is None:
        return None

    try:
        response = await engine._fetch(target_url)
    except Exception as exc:
        return _sanitize_snippet(f"fetch_error: {exc}")

    decode_fn = getattr(engine, "_decode_response", None)
    html_text: str
    if callable(decode_fn):
        try:
            decoded = decode_fn(response)
            html_text = decoded if isinstance(decoded, str) else ""
        except Exception:
            html_text = response.text
    else:
        html_text = response.text

    title_match = re.search(
        r"<title[^>]*>(.*?)</title>", html_text, flags=re.IGNORECASE | re.DOTALL
    )
    if title_match:
        title_text = _sanitize_snippet(title_match.group(1))
        if title_text:
            return title_text

    body_match = re.search(
        r"<body[^>]*>(.*?)</body>", html_text, flags=re.IGNORECASE | re.DOTALL
    )
    body_text = body_match.group(1) if body_match else html_text
    snippet = _sanitize_snippet(body_text)
    return snippet or None


def _normalize_engine_list(raw_engines: list[str]) -> list[str]:
    engines: list[str] = []
    for value in raw_engines:
        engines.extend([item.strip() for item in value.split(",") if item.strip()])
    return engines


async def _search_engine(
    engine_name: str, engine: BaseCrawler, query: SearchQuery
) -> tuple[str, list[SearchResult], Exception | None]:
    try:
        results = await engine.search(query)
        return engine_name, results, None
    except Exception as exc:
        return engine_name, [], exc


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Crawl search engines and print PDF coverage stats."
    )
    parser.add_argument("--query", default="Distill", help="Search query string")
    parser.add_argument(
        "--max-results",
        type=int,
        default=50,
        help="Maximum results to fetch",
    )
    parser.add_argument(
        "--engine",
        action="append",
        help="Engine name to run (repeatable or comma-separated)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Run against all available engines",
    )
    parser.add_argument(
        "--list-engines",
        action="store_true",
        help="List available engines and exit",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero if any selected engine errors",
    )
    parser.add_argument(
        "--debug-snippet",
        action="store_true",
        help="Print short sanitized snippet when an engine returns total=0",
    )
    return parser


def main() -> int:
    logging.basicConfig(
        level=logging.DEBUG, format="%(levelname)s:%(name)s:%(message)s"
    )
    parser = _build_parser()
    args = parser.parse_args()
    if args.list_engines:
        manager = CrawlerManager()
        print(
            "Available engines: {names}".format(names=", ".join(manager.list_engines()))
        )
        print(
            "Enabled engines: {names}".format(
                names=", ".join(manager.list_enabled_engines())
            )
        )
        return 0
    return asyncio.run(
        _run(
            args.query,
            args.max_results,
            args.engine or [],
            args.all,
            args.strict,
            args.debug_snippet,
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
