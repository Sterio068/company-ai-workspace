"""
Central retention registry.

Mongo TTL indexes are operational policy, not one-off startup code.  Keep the
authoritative policy here, then let startup apply/drop stale TTL definitions.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable


DAY = 24 * 60 * 60


@dataclass(frozen=True)
class RetentionPolicy:
    collection: str
    field: str
    index_name: str
    expire_after_seconds: int
    reason: str

    def to_dict(self) -> dict:
        return asdict(self)


RETENTION_POLICIES: tuple[RetentionPolicy, ...] = (
    RetentionPolicy("knowledge_audit", "created_at", "ttl_90d", 90 * DAY, "knowledge read audit trail"),
    RetentionPolicy("meetings", "created_at", "ttl_365d", 365 * DAY, "meeting transcript yearly review"),
    RetentionPolicy("site_surveys", "created_at", "ttl_2y", 2 * 365 * DAY, "site survey event-cycle archive"),
    RetentionPolicy("design_jobs", "created_at", "ttl_180d", 180 * DAY, "design generation job log"),
    RetentionPolicy("workflow_runs", "started_at", "ttl_365d", 365 * DAY, "workflow execution audit"),
    RetentionPolicy("vision_extractions", "extracted_at", "ttl_180d", 180 * DAY, "OCR/vision extraction cache"),
    RetentionPolicy("frontend_errors", "created_at", "ttl_30d", 30 * DAY, "frontend error telemetry"),
    RetentionPolicy("social_oauth_states", "expires_at", "state_ttl", 0, "OAuth state replay window"),
    RetentionPolicy("ai_dismissed", "until", "dismiss_ttl", 0, "dismissed AI suggestions"),
)


def _index_key(info: dict) -> list[tuple[str, int]]:
    return [(k, int(v)) for k, v in info.get("key", [])]


def apply_retention_indexes(db, logger=None,
                            policies: Iterable[RetentionPolicy] = RETENTION_POLICIES) -> list[dict]:
    """Ensure TTL indexes match RETENTION_POLICIES.

    If an index with the managed name exists but has stale TTL seconds or key,
    drop and recreate it.  This makes retention changes explicit and testable.
    """
    results: list[dict] = []
    for policy in policies:
        collection = getattr(db, policy.collection)
        existing = collection.index_information().get(policy.index_name)
        expected_key = [(policy.field, 1)]
        stale = bool(existing) and (
            existing.get("expireAfterSeconds") != policy.expire_after_seconds
            or _index_key(existing) != expected_key
        )
        if stale:
            collection.drop_index(policy.index_name)
            if logger:
                logger.info("[retention] dropped stale TTL %s.%s", policy.collection, policy.index_name)
        collection.create_index(
            [(policy.field, 1)],
            expireAfterSeconds=policy.expire_after_seconds,
            name=policy.index_name,
        )
        results.append(policy.to_dict() | {"status": "recreated" if stale else "ensured"})
    return results


def retention_manifest() -> list[dict]:
    return [p.to_dict() for p in RETENTION_POLICIES]
