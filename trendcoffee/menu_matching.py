"""Conservative catalog matching for spoken menu queries, using only the stdlib."""

import re
import unicodedata
from difflib import SequenceMatcher

# These words identify a drink family, but are not evidence for a particular flavor.
_GENERIC = {"tra", "ca", "phe", "nuoc", "banh"}
_FILLER = re.compile(
    r"\b(?:cho|minh|toi|tao|muon|dat|goi|lay|mua|ly|coc|phan|chai|voi|them|tim|"
    r"menu|xem|nhe|nha|giup|gia|bao|nhieu|co|khong|"
    # Words that describe a search rather than name a drink ("những món có hoa").
    r"mon|nhung|cac|cai|loai|nao|gi)\b|\b\d+\b"
)
_QUANTITY = re.compile(r"^(?:mot|hai|ba|bon|nam|sau|bay|tam|chin|muoi)\s+")


def _normalize(value):
    value = unicodedata.normalize("NFD", value.lower().replace("đ", "d"))
    value = "".join(c for c in value if unicodedata.category(c) != "Mn")
    value = re.sub(r"\bcafe\b", "ca phe", value)
    return " ".join(re.findall(r"[a-z0-9]+", value))


def _clean(value):
    value = " ".join(_FILLER.sub(" ", _normalize(value)).split())
    return _QUANTITY.sub("", value).strip()


def _family(words):
    return set(words) & {"tra", "phe", "nuoc", "banh"}


def _token_similarity(a, b):
    # A one-letter substitution is credible; shared subsequences alone can
    # misleadingly make unrelated short flavors such as "sao" and "sua" close.
    previous = list(range(len(b) + 1))
    for i, left in enumerate(a, 1):
        current = [i]
        for j, right in enumerate(b, 1):
            current.append(min(current[-1] + 1, previous[j] + 1, previous[j - 1] + (left != right)))
        previous = current
    return 1 - previous[-1] / max(len(a), len(b))


def _rank(term, catalog):
    words = term.split()
    core = [word for word in words if word not in _GENERIC]
    if not core:
        return []
    ranked = []
    for item, name in catalog:
        tokens = name.split()
        if _family(words) and not _family(words) & _family(tokens):
            continue
        distinctive = [word for word in tokens if word not in _GENERIC]
        if not distinctive:
            continue
        # Pair tokens once: a repeated recognition cannot count as several flavors.
        pairs = sorted(
            (
                (_token_similarity(a, b), i, j)
                for i, a in enumerate(core)
                for j, b in enumerate(distinctive)
                if a == b or min(len(a), len(b)) >= 3
            ),
            reverse=True,
        )
        used_query, used_name, weight = set(), set(), 0.0
        for similarity, i, j in pairs:
            if similarity < 2 / 3 or i in used_query or j in used_name:
                continue
            used_query.add(i)
            used_name.add(j)
            weight += similarity
        coverage, precision = weight / len(distinctive), weight / len(core)
        # Sharing only "trà"/"cà phê", or one word of an unrelated longer
        # flavor, cannot turn an unknown drink into a catalog candidate.
        if coverage < 0.65 or precision < (0.2 if _family(words) else 0.65):
            continue
        similarity = SequenceMatcher(None, term, name, autojunk=False).ratio()
        score = 0.5 * coverage + 0.25 * precision + 0.25 * similarity
        ranked.append((score, coverage, precision, similarity, item))
    return sorted(ranked, key=lambda row: (-row[0], row[4]["id"]))


def _suggestions(ranked):
    if not ranked:
        return []
    return [
        {"item_id": item["id"], "name": item["name"], "score": round(score, 3)}
        for score, _, _, _, item in ranked[:3]
        if score >= ranked[0][0] - 0.16
    ]


def _phrase(term, catalog):
    term = _normalize(term)
    if not term:
        return [], [], "unmatched", True
    by_name = {}
    for item, name in catalog:
        by_name.setdefault(name, []).append(item)
    exact, ambiguous, occupied = [], [], []
    for name in sorted(by_name, key=len, reverse=True):
        for found in re.finditer(r"(?<!\w)" + re.escape(name) + r"(?!\w)", term):
            if any(found.start() < end and found.end() > start for start, end in occupied):
                continue
            occupied.append(found.span())
            if len(by_name[name]) == 1:
                exact.append(by_name[name][0]["id"])
            else:
                ambiguous.extend(
                    {"item_id": item["id"], "name": item["name"], "score": 1.0}
                    for item in by_name[name]
                )
    if occupied:
        remainder = term
        for start, end in sorted(occupied, reverse=True):
            remainder = remainder[:start] + " " * (end - start) + remainder[end:]
        remainder = _clean(re.sub(r"\bva\b", " ", remainder))
        if not remainder:
            return exact, ambiguous, "exact", False
        # Retain complete drinks in a mixed spoken list. A trailing unknown
        # modifier instead downgrades the whole name to a suggestion.
        if _family(remainder.split()):
            resolved, suggestions, kind, unknown = _phrase(remainder, catalog)
            return exact + resolved, ambiguous + suggestions, "mixed", unknown
    else:
        # Keyword searches still work, but partial names need confirmation
        # before the customer is given a more specific flavor.
        term = _clean(term)
        partial = [
            item for item, name in catalog if term and set(term.split()) <= set(name.split())
        ]
        if partial:
            return (
                [],
                [
                    {"item_id": item["id"], "name": item["name"], "score": 1.0}
                    for item in partial[:3]
                ],
                "partial",
                False,
            )
    ranked = _rank(_clean(term), catalog)
    if not ranked:
        return [], [], "unmatched", True
    best = ranked[0]
    margin = best[0] - ranked[1][0] if len(ranked) > 1 else 1
    if min(best[1:3]) >= 0.8 and best[3] >= 0.85 and margin >= 0.12:
        return [best[4]["id"]], [], "fuzzy", False
    return [], _suggestions(ranked), "fuzzy", False


def match_menu(items, terms):
    """Return resolved catalog IDs and at most three uncertain candidates per query.

    ``items`` includes candidates for display. Only ``resolved_item_ids`` are
    confident selections; ``suggestions`` require the customer's clarification.
    Original queries (and their quantities) are retained verbatim in ``matches``.
    The caller owns query validation and catalog freshness/stock annotations.
    """
    catalog = [(item, _normalize(item["name"])) for item in items]
    matches, selected, unmatched = [], set(), []
    for original in terms:
        resolved, suggestions, kinds, missing = [], [], [], False
        # Keep complete names together; split only explicit list separators.
        parts = (
            [original]
            if any(_clean(original) == name for _, name in catalog)
            else re.split(r"[,;+&\n]|\bva\b", _normalize_separators(original))
        )
        for part in filter(str.strip, parts):
            ids, candidates, kind, unknown = _phrase(part, catalog)
            resolved.extend(ids)
            suggestions.extend(candidates)
            kinds.append(kind)
            missing |= unknown
        suggestions = list({s["item_id"]: s for s in suggestions}.values())[:3]
        resolved = list(dict.fromkeys(resolved))
        ids = list(dict.fromkeys(resolved + [s["item_id"] for s in suggestions]))
        if missing or not kinds:
            unmatched.append(original)
        selected.update(ids)
        matches.append(
            {
                "query": original,
                "item_ids": ids,
                "resolved_item_ids": resolved,
                "suggestions": suggestions,
                "match_type": kinds[0] if len(set(kinds)) == 1 else "mixed",
                "requires_clarification": bool(suggestions) or missing or not kinds,
            }
        )
    return {
        "items": [item for item in items if item["id"] in selected] if terms else items,
        "matches": matches,
        "unmatched": unmatched,
        "live_stock": False,
        "requires_clarification": any(match["requires_clarification"] for match in matches),
    }


def _normalize_separators(value):
    # Normalize each list member separately so punctuation still separates drinks.
    return re.sub(r"[^,;+&\n]+", lambda match: _normalize(match[0]), value)


# Words guests wrap around a category name ("các món trà", "đồ uống cà phê") and the
# English names guests use; both map onto the published category names.
_CATEGORY_FILLER = {"mon", "cac", "nhung", "loai", "do", "uong", "nuoc"}
_CATEGORY_ALIASES = {
    "tea": "tra",
    "coffee": "ca phe",
    "cake": "banh",
    "cakes": "banh",
    "pastry": "banh",
    "bakery": "banh",
    "smoothie": "sinh to",
    "smoothies": "sinh to",
}
SORTS = ("price_asc", "price_desc")


def _category_key(value):
    words = [word for word in _normalize(value).split() if word not in _CATEGORY_FILLER]
    key = " ".join(words)
    return _CATEGORY_ALIASES.get(key, key)


def resolve_category(name, categories):
    """The published category a guest's wording names, or None. Accent and case free."""
    for category in categories:
        if name.strip() == category.get("id"):
            return category
    key = _category_key(name)
    if not key:
        return None
    return next((c for c in categories if _category_key(c.get("name", "")) == key), None)


def in_category(item, category):
    if item.get("category_id") and category.get("id"):
        return item["category_id"] == category["id"]
    return _category_key(item.get("category", "")) == _category_key(category.get("name", ""))
