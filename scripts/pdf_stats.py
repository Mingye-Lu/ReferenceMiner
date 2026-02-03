from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from refminer.crawler.base import BaseCrawler
from refminer.crawler.manager import CrawlerManager
from refminer.crawler.models import SearchQuery, SearchResult


async def _run(
    query: str, max_results: int, engines: list[str], include_all: bool
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
            query=query, max_results=max_results, include_abstract=False
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
    for engine_name, results, error in results_by_engine:
        if error is not None:
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

    if len(results_by_engine) > 1:
        overall_ratio = (overall_pdf / overall_total) if overall_total else 0
        print(
            "overall total={total} pdf_count={pdf_count} pdf_ratio={ratio:.2%}".format(
                total=overall_total, pdf_count=overall_pdf, ratio=overall_ratio
            )
        )
    return 0


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
    return asyncio.run(_run(args.query, args.max_results, args.engine or [], args.all))


if __name__ == "__main__":
    raise SystemExit(main())
