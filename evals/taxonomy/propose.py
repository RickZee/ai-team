"""Axial-coding helpers: propose taxonomy candidates from open-coding tags (R4).

Does NOT auto-add failure modes. Humans review each candidate (task 5.3).
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from evals.annotate import AnnotationRecord, load_annotations
from evals.taxonomy.loader import Taxonomy, load_taxonomy

_DEFAULT_ANNOTATIONS_ROOT = Path("evals/annotations")


class TagCluster(BaseModel):
    """A proposed taxonomy candidate clustered from provisional tags."""

    canonical: str = Field(description="Normalized tag / cluster key")
    count: int = Field(description="How many annotation records used this tag")
    variants: list[str] = Field(description="Raw tag spellings observed")
    example_trace_ids: list[str] = Field(
        default_factory=list,
        description="Up to a few trace ids that carried this tag",
    )
    already_in_taxonomy: bool = Field(
        description="True when canonical matches an existing FM slug or id",
    )


def normalize_tag(tag: str) -> str:
    """Normalize a provisional tag for clustering (lowercase, snake_case)."""
    text = tag.strip().lower()
    text = text.replace("-", "_").replace(" ", "_")
    text = re.sub(r"[^a-z0-9_]+", "", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text or "unnamed"


def _taxonomy_keys(taxonomy: Taxonomy) -> set[str]:
    keys: set[str] = set()
    for fm in taxonomy.failure_modes:
        keys.add(fm.id.lower())
        keys.add(fm.slug.lower())
        keys.add(normalize_tag(fm.slug))
        keys.add(normalize_tag(fm.title))
    return keys


def cluster_tags(
    records: Sequence[AnnotationRecord],
    *,
    taxonomy: Taxonomy | None = None,
) -> list[TagCluster]:
    """Cluster provisional tags from annotations into proposal candidates."""
    tax = taxonomy or load_taxonomy()
    known = _taxonomy_keys(tax)
    counts: Counter[str] = Counter()
    variants: dict[str, set[str]] = {}
    examples: dict[str, list[str]] = {}

    for rec in records:
        for tag in rec.tags:
            key = normalize_tag(tag)
            counts[key] += 1
            variants.setdefault(key, set()).add(tag)
            bucket = examples.setdefault(key, [])
            if rec.trace_id not in bucket and len(bucket) < 5:
                bucket.append(rec.trace_id)

    clusters: list[TagCluster] = []
    for key, n in counts.most_common():
        clusters.append(
            TagCluster(
                canonical=key,
                count=n,
                variants=sorted(variants.get(key, set())),
                example_trace_ids=list(examples.get(key, [])),
                already_in_taxonomy=key in known
                or key.upper() in {fm.id for fm in tax.failure_modes},
            )
        )
    return clusters


def load_all_annotations(*, annotations_root: Path | None = None) -> list[AnnotationRecord]:
    """Load every ``*.jsonl`` under the annotations root."""
    root = Path(annotations_root) if annotations_root is not None else _DEFAULT_ANNOTATIONS_ROOT
    if not root.is_dir():
        return []
    records: list[AnnotationRecord] = []
    for path in sorted(root.glob("*.jsonl")):
        records.extend(load_annotations(path))
    return records


def propose_from_annotations(
    *,
    annotations_root: Path | None = None,
    taxonomy_path: Path | None = None,
) -> list[TagCluster]:
    """Cluster tags from annotation JSONL; return candidates (no YAML writes)."""
    records = load_all_annotations(annotations_root=annotations_root)
    tax = load_taxonomy(taxonomy_path) if taxonomy_path else load_taxonomy()
    return cluster_tags(records, taxonomy=tax)


def format_proposals(clusters: Iterable[TagCluster]) -> str:
    """Human-readable proposal table for the CLI."""
    lines = [
        "Taxonomy proposals from open-coding tags (NOT auto-added).",
        "Review each candidate: accept as FM-011+, merge into an existing FM, or reject.",
        "",
        f"{'canonical':<40} {'n':>5} {'in_tax':>6}  variants",
    ]
    rows = list(clusters)
    if not rows:
        lines.append("(no tags found in annotations)")
        return "\n".join(lines)
    for c in rows:
        flag = "yes" if c.already_in_taxonomy else "no"
        variants = ", ".join(c.variants[:5])
        lines.append(f"{c.canonical:<40} {c.count:>5} {flag:>6}  {variants}")
    return "\n".join(lines)


def proposals_as_dicts(clusters: Sequence[TagCluster]) -> list[dict[str, Any]]:
    """Serialize clusters for JSON output."""
    return [c.model_dump(mode="json") for c in clusters]
