"""Collect Guild Wars Wiki ``Contains ...`` category members for salvage review.

This tool is deliberately separate from the runtime salvage map. A wiki category
proves that an item can yield a material, but does not state the game's common
versus rare salvage selection. It reports exact, ambiguous, and unresolved
name-to-model candidates so that the runtime mapping stays an explicit review
decision.

The category HTML is parsed with Beautiful Soup. Requests are cached outside
the repository and throttled to one every two seconds by default.
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import re
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from urllib.parse import quote
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


WIKI_ROOT = "https://wiki.guildwars.com"
USER_AGENT = "Py4GW-Reforged salvage research (local maintenance; contact repository maintainer)"
DEFAULT_DELAY_SECONDS = 2.0
EXCLUDED_CATEGORIES = {
    "Contains common crafting material",
    "Contains rare crafting material",
    "Contains Zaishen Coin",
}
WIKI_CATEGORY_TARGETS: dict[str, int] = {
    "Contains Iron Ingot": 948,
    "Contains amber": 6532,
    "Contains bone": 921,
    "Contains charcoal": 922,
    "Contains chitin": 954,
    "Contains cloth": 925,
    "Contains damask": 927,
    "Contains deldrimor steel": 950,
    "Contains diamond": 935,
    "Contains dust": 929,
    "Contains ectoplasm": 930,
    "Contains feather": 933,
    "Contains fiber": 934,
    "Contains fur": 941,
    "Contains granite": 955,
    "Contains hide": 940,
    "Contains ink": 944,
    "Contains iron": 948,
    "Contains jadeite": 6533,
    "Contains leather": 942,
    "Contains linen": 926,
    "Contains monstrous claw": 923,
    "Contains monstrous eye": 931,
    "Contains monstrous fang": 932,
    "Contains obsidian shard": 945,
    "Contains onyx": 936,
    "Contains parchment": 951,
    "Contains ruby": 937,
    "Contains sapphire": 938,
    "Contains scale": 953,
    "Contains silk": 928,
    "Contains spiritwood": 956,
    "Contains steel": 949,
    "Contains tempered glass": 939,
    "Contains vellum": 952,
    "Contains wood": 946,
}


@dataclass(frozen=True)
class ModelCandidate:
    """One known model id and the local source that supplied its display name."""

    model_id: int
    source: str


def normalize_name(name: str) -> str:
    """Normalize a wiki title and local display name for conservative exact matching."""
    return re.sub(r"[^a-z0-9]", "", name.lower())


def repository_root() -> Path:
    return Path(__file__).resolve().parents[4]


def catalog_name_index(path: Path) -> dict[str, set[ModelCandidate]]:
    """Read ``CatalogEntry`` literals without importing the embedded Py4GW package."""
    index: dict[str, set[ModelCandidate]] = {}
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
            continue
        if node.func.id != "CatalogEntry" or len(node.args) < 2:
            continue
        name, model_id = node.args[:2]
        if not isinstance(name, ast.Constant) or not isinstance(name.value, str):
            continue
        if not isinstance(model_id, ast.Constant) or not isinstance(model_id.value, int):
            continue
        index.setdefault(normalize_name(name.value), set()).add(ModelCandidate(model_id.value, "catalog"))
    return index


def model_enum_name_index(path: Path) -> dict[str, set[ModelCandidate]]:
    """Read ``ModelID`` member names without loading dependencies from ``Py4GWCoreLib``."""
    index: dict[str, set[ModelCandidate]] = {}
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    model_enum = next(
        (node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "ModelID"),
        None,
    )
    if model_enum is None:
        return index
    for node in model_enum.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name) or not isinstance(node.value, ast.Constant):
            continue
        if not isinstance(node.value.value, int) or node.value.value >= 1_000_000:
            continue
        value_suffix = "_%d" % node.value.value
        member_name = target.id[: -len(value_suffix)] if target.id.endswith(value_suffix) else target.id
        member_name = member_name.replace("_", " ")
        index.setdefault(normalize_name(member_name), set()).add(
            ModelCandidate(node.value.value, "ModelID enum")
        )
    return index


def merge_indexes(indexes: Iterable[dict[str, set[ModelCandidate]]]) -> dict[str, set[ModelCandidate]]:
    merged: dict[str, set[ModelCandidate]] = {}
    for index in indexes:
        for name, candidates in index.items():
            merged.setdefault(name, set()).update(candidates)
    return merged


def canonical_names_by_model(index: dict[str, set[ModelCandidate]]) -> dict[int, set[str]]:
    """Return current-project names keyed by model id."""
    names: dict[int, set[str]] = {}
    for normalized, candidates in index.items():
        for candidate in candidates:
            names.setdefault(candidate.model_id, set()).add(normalized)
    return names


class WikiClient:
    """Cache-first, deliberately slow requester for the public Guild Wars Wiki."""

    def __init__(self, cache_dir: Path, delay_seconds: float, refresh: bool) -> None:
        self.cache_dir = cache_dir
        self.delay_seconds = delay_seconds
        self.refresh = refresh
        self.next_request_at = 0.0
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})

    def get_html(self, url: str, cache_name: str) -> str:
        cache_file = self.cache_dir / cache_name
        if cache_file.exists() and not self.refresh:
            return cache_file.read_text(encoding="utf-8")

        delay = self.next_request_at - time.monotonic()
        if delay > 0:
            time.sleep(delay)
        response = self.session.get(url, timeout=30)
        self.next_request_at = time.monotonic() + self.delay_seconds
        response.raise_for_status()
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(response.text, encoding="utf-8")
        return response.text


def contains_categories(client: WikiClient) -> list[str]:
    """Discover category labels once through MediaWiki, excluding the two broad buckets."""
    url = (
        f"{WIKI_ROOT}/api.php?action=query&list=allcategories&acprefix=Contains%20"
        "&aclimit=max&format=json&formatversion=2&maxlag=5"
    )
    html = client.get_html(url, "contains_categories.json")
    data = json.loads(html)
    categories = [entry["category"] for entry in data["query"]["allcategories"]]
    return [name for name in categories if name not in EXCLUDED_CATEGORIES]


def category_members(client: WikiClient, category: str) -> list[str]:
    """Read all page members from one category, following the rendered next-page link."""
    members: list[str] = []
    url = f"{WIKI_ROOT}/wiki/Category:{quote(category.replace(' ', '_'))}"
    page = 1
    while url:
        cache_name = "%s-%03d.html" % (re.sub(r"[^a-z0-9]+", "_", category.lower()).strip("_"), page)
        soup = BeautifulSoup(client.get_html(url, cache_name), "html.parser")
        pages = soup.find(id="mw-pages")
        if pages is None:
            # Empty categories render no member container. That is evidence of no listed sources,
            # not a request failure or a reason to manufacture a mapping.
            return []
        for entry in pages.select("li > a[title]"):
            title = entry.get("title")
            if isinstance(title, str) and not title.startswith("Category:"):
                members.append(title)
        next_link = next((link for link in pages.find_all("a") if link.get_text(" ", strip=True) == "next page"), None)
        href = next_link.get("href") if next_link else None
        url = urljoin(WIKI_ROOT, href) if isinstance(href, str) else ""
        page += 1
    return sorted(set(members), key=str.casefold)


def format_candidates(candidates: set[ModelCandidate]) -> str:
    grouped: dict[int, set[str]] = {}
    for candidate in candidates:
        grouped.setdefault(candidate.model_id, set()).add(candidate.source)
    return "; ".join(
        "%d (%s)" % (model_id, ", ".join(sorted(sources)))
        for model_id, sources in sorted(grouped.items())
    )


def collect_targets(
    categories: list[str],
    index: dict[str, set[ModelCandidate]],
    client: WikiClient,
) -> tuple[str, dict[int, tuple[int, ...]]]:
    """Join authoritative wiki categories to model ids, rejecting known local-name conflicts."""
    unknown_categories = set(categories) - set(WIKI_CATEGORY_TARGETS)
    missing_categories = set(WIKI_CATEGORY_TARGETS) - set(categories)
    if unknown_categories or missing_categories:
        raise RuntimeError(
            "Wiki category vocabulary changed; review target mapping. unknown=%s missing=%s"
            % (sorted(unknown_categories), sorted(missing_categories))
        )

    canonical_names = canonical_names_by_model(index)
    targets_by_model: dict[int, set[int]] = {}
    lines = ["# Guild Wars Wiki salvage-category collection", "", "Status: collected for review", ""]
    exact = 0
    ambiguous = 0
    unresolved = 0
    rejected = 0
    for category in categories:
        members = category_members(client, category)
        target = WIKI_CATEGORY_TARGETS[category]
        lines.extend(["## %s" % category, "", "Target material model: %d" % target, "", "Members: %d" % len(members), ""])
        for title in members:
            candidates = index.get(normalize_name(title), set())
            distinct_ids = {
                candidate.model_id
                for candidate in candidates
                if not canonical_names.get(candidate.model_id)
                or normalize_name(title) in canonical_names[candidate.model_id]
            }
            rejected += len({candidate.model_id for candidate in candidates} - distinct_ids)
            if len(distinct_ids) == 1:
                exact += 1
                lines.append("- exact: %s -> %s" % (title, format_candidates(candidates)))
            elif len(distinct_ids) > 1:
                ambiguous += 1
                lines.append("- ambiguous: %s -> %s" % (title, format_candidates(candidates)))
            else:
                unresolved += 1
                lines.append("- unresolved: %s" % title)
            for model_id in distinct_ids:
                targets_by_model.setdefault(model_id, set()).add(target)
        lines.append("")
    lines.extend(
        [
            "## Summary",
            "",
            "- exact model matches: %d" % exact,
            "- ambiguous model matches: %d" % ambiguous,
            "- unresolved titles: %d" % unresolved,
            "- rejected local-name conflicts: %d" % rejected,
            "- extracted model-to-target relations: %d" % len(targets_by_model),
            "",
            "Category membership establishes a salvage target relation only. It does not establish common or rare salvage selection.",
        ]
    )
    return "\n".join(lines) + "\n", {
        model_id: tuple(sorted(targets)) for model_id, targets in sorted(targets_by_model.items())
    }


def write_python_targets(path: Path, targets: dict[int, tuple[int, ...]]) -> None:
    """Write generated source data for review."""
    lines = [
        '"""Guild Wars Wiki salvage targets, generated for the item catalog.',
        "",
        "Source: Guild Wars Wiki `Category:Contains ...` pages.",
        "Model IDs were resolved from the current catalog and ModelID enum during generation.",
        "The runtime imports this static result only; it never performs name resolution.",
        '"""',
        "",
        "WIKI_SALVAGE_TARGETS: dict[int, tuple[int, ...]] = {",
    ]
    lines.extend("    %d: %r," % (model_id, target_ids) for model_id, target_ids in targets.items())
    lines.extend(["}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=Path(os.environ.get("LOCALAPPDATA", tempfile.gettempdir())) / "Py4GW_Reforged" / "wiki_salvage_cache",
        help="External cache directory; never defaults inside the repository.",
    )
    parser.add_argument("--delay", type=float, default=DEFAULT_DELAY_SECONDS, help="Seconds between uncached requests (minimum 0.5).")
    parser.add_argument("--refresh", action="store_true", help="Ignore cached responses and request pages again.")
    parser.add_argument("--report", type=Path, required=True, help="Markdown report path outside docs.")
    parser.add_argument("--emit-python", type=Path, help="Write extracted model-to-target source data for review.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.delay < 0.5:
        raise SystemExit("--delay must be at least 0.5 seconds (two requests per second at most).")

    root = repository_root()
    index = merge_indexes(
        (
            catalog_name_index(root / "Py4GWCoreLib" / "py4gwcorelib_src" / "system_settings" / "loot_filters" / "catalog.py"),
            model_enum_name_index(root / "Py4GWCoreLib" / "enums_src" / "Model_enums.py"),
        )
    )
    client = WikiClient(args.cache_dir, args.delay, args.refresh)
    categories = contains_categories(client)
    report, targets = collect_targets(categories, index, client)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(report, encoding="utf-8")
    if args.emit_python is not None:
        write_python_targets(args.emit_python, targets)
    print("Collected %d categories into %s" % (len(categories), args.report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
