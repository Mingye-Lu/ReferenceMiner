from __future__ import annotations

import argparse
from pathlib import Path

from refminer.analyze.workflow import analyze
from refminer.ingest.manifest import load_manifest
from refminer.ingest.pipeline import ingest_all
from refminer.render.answer import render_answer
from refminer.retrieve.search import retrieve
from refminer.utils.paths import get_index_dir


def cmd_ingest(args: argparse.Namespace) -> int:
    result = ingest_all(build_vectors_index=not args.no_vectors)
    print("Ingest completed.")
    for key, value in result.items():
        print(f"{key}: {value}")
    return 0


def cmd_list(_: argparse.Namespace) -> int:
    index_dir = get_index_dir()
    manifest_path = index_dir / "manifest.json"
    if not manifest_path.exists():
        print("No manifest found. Run 'referenceminer ingest' first.")
        return 1
    manifest = load_manifest()
    for entry in manifest:
        title = entry.title or ""
        print(f"{entry.rel_path} [{entry.file_type}] {title}")
    return 0


def cmd_ask(args: argparse.Namespace) -> int:
    index_dir = get_index_dir()
    if not (index_dir / "bm25.pkl").exists():
        print("Indexes not found. Run 'referenceminer ingest' first.")
        return 1
    evidence = retrieve(args.question, k=args.top_k)
    analysis = analyze(args.question, evidence)
    print(render_answer(analysis))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="referenceminer")
    subparsers = parser.add_subparsers(dest="command", required=True)

    ingest_parser = subparsers.add_parser("ingest", help="Build manifest and indexes")
    ingest_parser.add_argument(
        "--no-vectors", action="store_true", help="Skip vector index"
    )
    ingest_parser.set_defaults(func=cmd_ingest)

    list_parser = subparsers.add_parser("list", help="List reference files")
    list_parser.set_defaults(func=cmd_list)

    ask_parser = subparsers.add_parser(
        "ask", help="Ask a question against indexed references"
    )
    ask_parser.add_argument("question")
    ask_parser.add_argument("--top-k", type=int, default=5)
    ask_parser.set_defaults(func=cmd_ask)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)
