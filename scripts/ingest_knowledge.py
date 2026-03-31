#!/usr/bin/env python3
"""
Ingest ``src/ai_team/knowledge/**/*.md`` into the ChromaDB RAG collection.

Requires ``OPENROUTER_API_KEY`` for embeddings (same as memory settings).

Usage::

    poetry run python scripts/ingest_knowledge.py
    RAG_ENABLED=true poetry run python scripts/ingest_knowledge.py --reset
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import structlog

logger = structlog.get_logger(__name__)

_ROOT = Path(__file__).resolve().parents[1]
_KNOWLEDGE = _ROOT / "src" / "ai_team" / "knowledge"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Ingest markdown knowledge into RAG ChromaDB."
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Delete existing collection before ingest.",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=_KNOWLEDGE,
        help=f"Knowledge root (default: {_KNOWLEDGE})",
    )
    args = parser.parse_args()
    if not args.root.is_dir():
        logger.error("knowledge_root_missing", path=str(args.root))
        return 1

    from ai_team.rag.pipeline import get_rag_pipeline

    pipe = get_rag_pipeline()
    if args.reset:
        pipe.reset_collection()
    n = pipe.ingest_directory(args.root, glob_pattern="**/*.md")
    logger.info("ingest_knowledge_complete", chunks=n, root=str(args.root.resolve()))
    print(f"Ingested {n} chunk(s) from {args.root}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
