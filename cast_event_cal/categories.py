from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any

CATEGORY_ONTOLOGY_PATH = Path("config/category_ontology.json")


@dataclass(frozen=True, slots=True)
class CategoryDecision:
    category: str
    label: str
    subcategory: str | None
    score: int
    confidence: float
    source: str
    evidence: tuple[str, ...]
    event_mode: str
    ambiguous_with: tuple[str, ...] = ()


def load_category_ontology(path: Path = CATEGORY_ONTOLOGY_PATH) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or not isinstance(value.get("categories"), list):
        raise ValueError("category ontology must contain a categories array")
    return value


def normalized(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).casefold()
    return re.sub(r"[^0-9a-zぁ-んァ-ヶ一-龠]+", "", text)


def organizer_key(event: dict[str, Any]) -> str | None:
    value = normalized(event.get("official_x_url") or event.get("organizer"))
    return value or None


def event_fields(event: dict[str, Any]) -> list[tuple[str, str, int]]:
    tags = " ".join(str(value) for value in event.get("tags", []) if str(value).strip())
    return [
        ("title", str(event.get("title") or ""), 4),
        ("canonical_name", str(event.get("canonical_name") or ""), 4),
        ("event_format", str(event.get("event_format") or ""), 3),
        ("tags", tags, 3),
        ("organizer", str(event.get("organizer") or ""), 2),
        ("location", str(event.get("location") or ""), 2),
        ("description", str(event.get("description") or ""), 1),
    ]


def best_term_match(
    fields: list[tuple[str, str, int]], terms: list[Any], *, base_weight: int
) -> tuple[int, list[str]]:
    score = 0
    evidence: list[str] = []
    seen: set[str] = set()
    for raw_term in terms:
        term = str(raw_term).strip()
        needle = normalized(term)
        if not needle or needle in seen:
            continue
        seen.add(needle)
        matches = [(field_name, field_weight) for field_name, text, field_weight in fields if needle in normalized(text)]
        if not matches:
            continue
        field_name, field_weight = max(matches, key=lambda item: item[1])
        score += base_weight + field_weight
        evidence.append(f"keyword:{field_name}:{term}")
    return score, evidence


def modality(event: dict[str, Any], ontology: dict[str, Any], category: str) -> str:
    if category == "recruitment_deadline":
        return "deadline"
    text = " ".join(value for _, value, _ in event_fields(event))
    folded = normalized(text)
    rules = ontology.get("modalities", {})

    def matched(name: str) -> bool:
        return any(normalized(term) in folded for term in rules.get(name, []) if normalized(term))

    if matched("hybrid"):
        return "hybrid"
    is_offline = matched("offline")
    is_stream = matched("stream")
    is_in_world = matched("in_world")
    if is_offline:
        return "offline" if not is_stream else "hybrid"
    if is_stream and is_in_world:
        return "hybrid"
    if is_stream:
        return "stream"
    if is_in_world:
        return "in_world"
    return "unknown"


def direct_decision(event: dict[str, Any], ontology: dict[str, Any]) -> CategoryDecision:
    categories = [row for row in ontology.get("categories", []) if isinstance(row, dict)]
    by_id = {str(row.get("id")): row for row in categories if row.get("id")}
    default_id = str(ontology.get("default_category") or "other")
    minimum_score = int(ontology.get("minimum_keyword_score") or 3)
    fields = event_fields(event)
    scores: dict[str, int] = {}
    evidence_by_id: dict[str, list[str]] = defaultdict(list)

    explicit = str(event.get("ontology_category") or "").strip()
    if explicit in by_id:
        scores[explicit] = 100
        evidence_by_id[explicit].append(f"curated_ontology:{event.get('ontology_id') or 'entry'}")

    raw_category = str(event.get("category") or "").strip()
    mapped = ontology.get("legacy_category_map", {}).get(raw_category)
    if mapped in by_id:
        scores[str(mapped)] = scores.get(str(mapped), 0) + 6
        evidence_by_id[str(mapped)].append(f"legacy_category:{raw_category}")

    for row in categories:
        category_id = str(row.get("id") or "")
        if not category_id or category_id == default_id:
            continue
        strong_score, strong_evidence = best_term_match(fields, list(row.get("strong_keywords", [])), base_weight=4)
        keyword_score, keyword_evidence = best_term_match(fields, list(row.get("keywords", [])), base_weight=1)
        total = strong_score + keyword_score
        if total:
            scores[category_id] = scores.get(category_id, 0) + total
            evidence_by_id[category_id].extend(strong_evidence + keyword_evidence)

    ranked = sorted(
        (
            (score, int(by_id[category_id].get("priority") or 0), category_id)
            for category_id, score in scores.items()
            if category_id in by_id
        ),
        key=lambda item: (-item[0], -item[1], item[2]),
    )
    if not ranked or ranked[0][0] < minimum_score:
        category_id = default_id
        score = ranked[0][0] if ranked else 0
        source = "fallback"
        evidence: list[str] = []
        ambiguous: tuple[str, ...] = ()
    else:
        score, _, category_id = ranked[0]
        tied = tuple(item[2] for item in ranked[1:] if item[0] == score)
        ambiguous = tied
        evidence = evidence_by_id[category_id][:12]
        if explicit == category_id:
            source = "curated_ontology"
        elif any(item.startswith("legacy_category:") for item in evidence):
            source = "legacy_and_keywords" if len(evidence) > 1 else "legacy_category"
        else:
            source = "keyword_rules"

    row = by_id.get(category_id, {"id": default_id, "label": "その他", "subcategories": {}})
    subcategory = None
    best_sub_score = 0
    for sub_id, terms in row.get("subcategories", {}).items():
        sub_score, _ = best_term_match(fields, list(terms), base_weight=1)
        if sub_score > best_sub_score:
            best_sub_score = sub_score
            subcategory = str(sub_id)

    if category_id == default_id:
        confidence = 0.35 if score else 0.25
    elif score >= 100:
        confidence = 0.99
    else:
        confidence = min(0.96, 0.48 + score * 0.035)
        if ambiguous:
            confidence = min(confidence, 0.58)
    return CategoryDecision(
        category=category_id,
        label=str(row.get("label") or category_id),
        subcategory=subcategory,
        score=score,
        confidence=round(confidence, 3),
        source=source,
        evidence=tuple(evidence),
        event_mode=modality(event, ontology, category_id),
        ambiguous_with=ambiguous,
    )


def organizer_profiles(
    events: list[dict[str, Any]], decisions: list[CategoryDecision], ontology: dict[str, Any]
) -> dict[str, dict[str, Any]]:
    policy = ontology.get("organizer_prior", {})
    minimum_seed_events = int(policy.get("minimum_seed_events") or 2)
    minimum_dominance = float(policy.get("minimum_dominance") or 0.75)
    minimum_score = int(ontology.get("minimum_keyword_score") or 3) + 3
    counts: dict[str, Counter[str]] = defaultdict(Counter)
    for event, decision in zip(events, decisions, strict=True):
        key = organizer_key(event)
        if not key or decision.category == ontology.get("default_category", "other") or decision.score < minimum_score:
            continue
        if decision.ambiguous_with:
            continue
        counts[key][decision.category] += 1

    profiles: dict[str, dict[str, Any]] = {}
    for key, counter in counts.items():
        total = sum(counter.values())
        category, count = counter.most_common(1)[0]
        dominance = count / total if total else 0.0
        if count >= minimum_seed_events and dominance >= minimum_dominance:
            profiles[key] = {
                "category": category,
                "seed_events": count,
                "classified_seed_events": total,
                "dominance": round(dominance, 3),
            }
    return profiles


def attach_decision(event: dict[str, Any], decision: CategoryDecision) -> dict[str, Any]:
    result = dict(event)
    previous = str(result.get("category") or "").strip()
    if previous and previous != decision.category and previous != "event":
        result["legacy_category"] = previous
    result["category"] = decision.category
    result["category_label"] = decision.label
    result["category_detail"] = decision.subcategory
    result["category_score"] = decision.score
    result["category_confidence"] = decision.confidence
    result["category_source"] = decision.source
    result["category_evidence"] = list(decision.evidence)
    result["event_mode"] = decision.event_mode
    if decision.ambiguous_with:
        result["category_ambiguous_with"] = list(decision.ambiguous_with)
        result["review_required"] = True
    return result


def classify_events(
    events: list[dict[str, Any]], ontology: dict[str, Any]
) -> tuple[list[dict[str, Any]], dict[str, Any], list[dict[str, Any]]]:
    direct = [direct_decision(event, ontology) for event in events]
    profiles = organizer_profiles(events, direct, ontology)
    policy = ontology.get("organizer_prior", {})
    maximum_direct_score = int(policy.get("maximum_direct_score") or 2)
    category_rows = {
        str(row.get("id")): row for row in ontology.get("categories", []) if isinstance(row, dict) and row.get("id")
    }
    final: list[CategoryDecision] = []
    for event, decision in zip(events, direct, strict=True):
        profile = profiles.get(organizer_key(event) or "")
        if profile and decision.score <= maximum_direct_score:
            category = str(profile["category"])
            row = category_rows[category]
            decision = replace(
                decision,
                category=category,
                label=str(row.get("label") or category),
                subcategory=None,
                score=max(decision.score, 3),
                confidence=round(min(0.86, 0.58 + float(profile["dominance"]) * 0.28), 3),
                source="organizer_prior",
                evidence=(
                    f"organizer_prior:{organizer_key(event)}",
                    f"dominance:{profile['dominance']}",
                    f"seed_events:{profile['seed_events']}",
                ),
                ambiguous_with=(),
            )
        final.append(decision)

    classified = [attach_decision(event, decision) for event, decision in zip(events, final, strict=True)]
    category_breakdown = Counter(decision.category for decision in final)
    detail_breakdown = Counter(decision.subcategory for decision in final if decision.subcategory)
    mode_breakdown = Counter(decision.event_mode for decision in final)
    source_breakdown = Counter(decision.source for decision in final)
    low_confidence = sum(decision.confidence < 0.6 for decision in final)
    audit = [
        {
            "event_id": event.get("id"),
            "title": event.get("title"),
            **asdict(decision),
        }
        for event, decision in zip(events, final, strict=True)
        if decision.category == ontology.get("default_category", "other")
        or decision.confidence < 0.6
        or decision.ambiguous_with
        or decision.event_mode == "offline"
    ]
    summary = {
        "schema_version": str(ontology.get("schema_version") or "2.0"),
        "event_count": len(events),
        "category_breakdown": dict(sorted(category_breakdown.items())),
        "subcategory_breakdown": dict(sorted(detail_breakdown.items())),
        "event_mode_breakdown": dict(sorted(mode_breakdown.items())),
        "classification_source_breakdown": dict(sorted(source_breakdown.items())),
        "organizer_profile_count": len(profiles),
        "low_confidence_event_count": low_confidence,
        "audit_event_count": len(audit),
        "organizer_profiles": profiles,
    }
    return classified, summary, audit
