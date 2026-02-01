"""Simple web crawler script.

Usage:
    python simple_crawler.py <target_name>
    python simple_crawler.py "machine learning papers"
    python simple_crawler.py "machine learning" --download
"""

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from refminer.crawler import CrawlerManager, DeepCrawler, PDFDownloader, SearchQuery

# Fix encoding for Windows
if sys.platform == "win32":
    import io

    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")


async def crawl_target(
    target: str,
    max_results: int = 10,
    download: bool = False,
    deep: bool = False,
    max_papers: int = 50,
):
    """Crawl web for target."""
    print(f"🔍 Searching for: {target}")
    print(f"📊 Max results per engine: {max_results}")
    if deep:
        print(f"🔬 Deep crawl: ENABLED (max {max_papers} papers)")
    if download:
        print(f"📥 Auto Download: ENABLED")
    print()

    manager = CrawlerManager()

    print(f"🔧 Available engines: {', '.join(manager.list_engines())}")
    print(f"✅ Enabled engines: {', '.join(manager.list_enabled_engines())}\n")

    query = SearchQuery(
        query=target,
        max_results=max_results,
        include_abstract=True,
    )

    try:
        async with manager:
            results = await manager.search(query)

        print(f"\n{'='*60}")
        print(f"📚 Found {len(results)} total results")
        print(f"{'='*60}\n")

        for i, result in enumerate(results, 1):
            print(f"\n{i}. {result.title}")
            print(f"   {'─'*58}")

            if result.authors:
                authors_text = ", ".join(result.authors[:5])
                if len(result.authors) > 5:
                    authors_text += f" ... ({len(result.authors)} total)"
                print(f"   👤 Authors: {authors_text}")

            if result.year:
                print(f"   📅 Year: {result.year}")

            if result.journal:
                print(f"   📖 Journal: {result.journal}")

            print(f"   🔗 Source: {result.source}")

            if result.doi:
                print(f"   🆔 DOI: {result.doi}")

            if result.url:
                print(f"   🌐 URL: {result.url}")

            if result.pdf_url:
                print(f"   📄 PDF: {result.pdf_url}")

            if result.abstract:
                abstract_preview = result.abstract[:200]
                if len(result.abstract) > 200:
                    abstract_preview += "..."
                print(f"   📝 Abstract: {abstract_preview}")

            if result.citation_count:
                print(f"   📊 Citations: {result.citation_count}")

        print(f"\n{'='*60}")

        if download and results:
            print(f"📥 Downloading PDFs to references/ directory...")
            print(f"{'='*60}\n")

            references_dir = Path("references")
            references_dir.mkdir(exist_ok=True)

            downloader = PDFDownloader(references_dir)

            async with downloader:
                downloads = await downloader.download_batch(results, overwrite=False)

            success_count = sum(1 for path in downloads.values() if path is not None)
            failed_count = len(results) - success_count

            print(f"\n✅ Download complete!")
            print(f"   📥 Success: {success_count}")
            print(f"   ❌ Failed: {failed_count}")

            if success_count > 0:
                print(f"\n📁 Downloaded files:")
                for result_hash, path in downloads.items():
                    if path:
                        print(f"   ✓ {path.name}")

        print(f"\n{'='*60}")

        if deep and results:
            print(f"🔬 Starting deep crawl (citation expansion)...")
            print(f"{'='*60}\n")

            deep_crawler = DeepCrawler(max_papers=max_papers)

            expanded = await deep_crawler.expand_by_citations(
                results,
                fetch_references=True,
                fetch_citations=True,
            )

            new_papers = len(expanded) - len(results)
            print(f"\n{'='*60}")
            print(f"🔬 Deep crawl complete!")
            print(f"   📚 Total papers: {len(expanded)}")
            print(f"   ➕ New papers: {new_papers}")
            print(f"{'='*60}\n")

            results = expanded

            for i, result in enumerate(
                results[len(results) - new_papers :], len(results) - new_papers + 1
            ):
                print(f"\n{i}. {result.title}")
                print(f"   {'─'*58}")

                if result.authors:
                    authors_text = ", ".join(result.authors[:3])
                    if len(result.authors) > 3:
                        authors_text += f" ... ({len(result.authors)} total)"
                    print(f"   👤 Authors: {authors_text}")

                if result.year:
                    print(f"   📅 Year: {result.year}")

                print(f"   🔗 Source: {result.source}")

                if result.doi:
                    print(f"   🆔 DOI: {result.doi}")

                if result.pdf_url:
                    print(f"   📄 PDF: {result.pdf_url}")

        print(f"\n{'='*60}")
        print(f"✅ Search complete!")
        print(f"{'='*60}")

        return results

    except KeyboardInterrupt:
        print("\n\n⚠️  Search interrupted by user")
        return []
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback

        traceback.print_exc()
        return []


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Simple web crawler for academic papers",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python simple_crawler.py "machine learning"
  python simple_crawler.py "quantum computing" --max-results 20
  python simple_crawler.py "climate change" --engines pubmed semantic_scholar
  python simple_crawler.py "deep learning" --download
  python simple_crawler.py "transformers" --deep --max-papers 100
  python simple_crawler.py "attention mechanism" --deep --download
        """,
    )

    parser.add_argument("target", help="Search query (e.g., 'machine learning papers')")

    parser.add_argument(
        "--max-results",
        type=int,
        default=10,
        help="Maximum results per engine (default: 10)",
    )

    parser.add_argument(
        "--engines",
        nargs="+",
        choices=["google_scholar", "pubmed", "semantic_scholar"],
        help="Specific engines to use (default: all enabled)",
    )

    parser.add_argument("--year-from", type=int, help="Minimum publication year")

    parser.add_argument("--year-to", type=int, help="Maximum publication year")

    parser.add_argument(
        "--download", action="store_true", help="Download PDFs to references/ directory"
    )

    parser.add_argument(
        "--deep", action="store_true", help="Enable deep crawl (citation expansion)"
    )

    parser.add_argument(
        "--max-papers",
        type=int,
        default=50,
        help="Maximum total papers for deep crawl (default: 50)",
    )

    args = parser.parse_args()

    asyncio.run(
        crawl_target(
            args.target,
            max_results=args.max_results,
            download=args.download,
            deep=args.deep,
            max_papers=args.max_papers,
        )
    )


if __name__ == "__main__":
    main()
