#!/usr/bin/env python3
"""Refresh the Stripe fee data README with live statistics."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

STATS_START = "<!-- STATS_START -->"
STATS_END = "<!-- STATS_END -->"


def _load_json(path: Path) -> dict | list:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _format_dt(value: str | None) -> str:
    if not value:
        return "—"
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M UTC")
    except Exception:
        return value


def _git_latest_update(data_dir: Path) -> datetime | None:
    """Return the latest relevant timestamp from git or the current time.

    If the data directory has uncommitted changes, the data is being updated
    right now, so use the current UTC time. Otherwise, fall back to the last
    commit that touched the json/ or meta/ directories.
    """
    try:
        status = subprocess.run(
            ["git", "status", "--porcelain", "--", "json/", "meta/"],
            cwd=data_dir,
            capture_output=True,
            text=True,
            check=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None

    if status.stdout.strip():
        return datetime.now(timezone.utc)

    try:
        log = subprocess.run(
            ["git", "log", "-1", "--format=%cI", "--", "json/", "meta/"],
            cwd=data_dir,
            capture_output=True,
            text=True,
            check=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None

    commit_date = log.stdout.strip()
    if not commit_date:
        return None

    try:
        return datetime.fromisoformat(commit_date.replace("Z", "+00:00"))
    except Exception:
        return None


def _derive_stats(data_dir: Path) -> dict:
    index = _load_json(data_dir / "json" / "index.json")
    core_fees = _load_json(data_dir / "json" / "core-fees.json")
    payment_methods_catalog = _load_json(data_dir / "json" / "payment-methods.json")
    markets_meta = _load_json(data_dir / "meta" / "markets.json")
    unsupported = _load_json(data_dir / "meta" / "unsupported-markets.json")
    transient_failures = _load_json(data_dir / "meta" / "transient-failures.json")

    markets = index.get("markets", [])
    total_markets = len(markets)
    status_counts: dict[str, int] = {}
    for market in markets:
        status = market.get("derivation_status") or "unknown"
        status_counts[status] = status_counts.get(status, 0) + 1

    total_rules = 0
    for market in core_fees.get("markets", []):
        for rule in market.get("rules", []):
            total_rules += 1

    payment_methods: set[str] = set()
    for method in payment_methods_catalog.get("methods", []):
        method_id = method.get("method_id")
        if method_id:
            payment_methods.add(method_id)

    regions: set[str] = set()
    for market in markets_meta.get("markets", []):
        region = market.get("region")
        if region:
            regions.add(region)

    latest_update = None
    for market in markets:
        updated = market.get("source_updated_at") or market.get("generated_at")
        if updated:
            try:
                candidate = datetime.fromisoformat(updated.replace("Z", "+00:00"))
                if latest_update is None or candidate > latest_update:
                    latest_update = candidate
            except Exception:
                pass

    generated_at = (
        index.get("generated_at")
        or core_fees.get("generated_at")
        or payment_methods_catalog.get("generated_at")
        or markets_meta.get("generated_at")
    )
    if generated_at and latest_update is None:
        try:
            latest_update = datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
        except Exception:
            pass

    if latest_update is None:
        latest_update = _git_latest_update(data_dir)

    return {
        "total_markets": total_markets,
        "status_counts": status_counts,
        "total_rules": total_rules,
        "payment_methods": sorted(payment_methods),
        "regions": sorted(regions),
        "unsupported_count": len(unsupported) if isinstance(unsupported, list) else 0,
        "transient_count": len(transient_failures) if isinstance(transient_failures, list) else 0,
        "latest_update": latest_update,
    }


def _render_stats(stats: dict) -> str:
    status_order = ["complete", "partial", "unclassified", "failed"]
    status_parts = []
    for status in status_order:
        count = stats["status_counts"].get(status, 0)
        if count:
            status_parts.append(f"{count} {status}")
    for status, count in sorted(stats["status_counts"].items()):
        if status not in status_order:
            status_parts.append(f"{count} {status}")
    status_str = ", ".join(status_parts) if status_parts else "—"

    lines = [
        "| Metric | Value |",
        "|--------|------:|",
        f"| Markets | **{stats['total_markets']}** |",
        f"| Derivation status | {status_str} |",
        f"| Core fee rules | **{stats['total_rules']:,}** |",
        f"| Payment methods | {len(stats['payment_methods'])} ({', '.join(stats['payment_methods']) or '—'}) |",
        f"| Regions | {len(stats['regions'])} ({', '.join(stats['regions']) or '—'}) |",
        f"| Unsupported markets | {stats['unsupported_count']} |",
        f"| Transient failures | {stats['transient_count']} |",
        f"| Last crawled | {_format_dt(stats['latest_update'].isoformat().replace('+00:00', 'Z') if stats['latest_update'] else None)} |",
        "",
    ]
    return "\n".join(lines)


def _replace_section(content: str, start_marker: str, end_marker: str, body: str) -> str:
    pattern = re.compile(re.escape(start_marker) + r".*?" + re.escape(end_marker), re.DOTALL)
    replacement = f"{start_marker}\n{body}{end_marker}"
    if pattern.search(content):
        return pattern.sub(replacement, content)
    print(f"WARNING: markers '{start_marker}' / '{end_marker}' not found", file=sys.stderr)
    return content


def main() -> int:
    data_dir = Path(__file__).parent.parent
    readme_path = data_dir / "README.md"
    if not readme_path.exists():
        print(f"ERROR: README not found: {readme_path}", file=sys.stderr)
        return 1

    stats = _derive_stats(data_dir)
    body = _render_stats(stats)

    content = readme_path.read_text(encoding="utf-8")
    content = _replace_section(content, STATS_START, STATS_END, body)
    readme_path.write_text(content, encoding="utf-8")
    print(f"README updated: {readme_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
