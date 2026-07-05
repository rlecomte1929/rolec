# backend/app/services/vendor_discovery/vendor_ranker.py
"""
Vendor quality gate and ranking (VEN-06).
Score = rating × log10(review_count + 1) + accreditation_bonus
Example: 4.5★ × 100 reviews → score 9.0; 4.5★ × 10 reviews → score 4.5

Reads thresholds from the VEN-01 config. Review count is read from either
`review_count` or the maps_discovery `user_ratings_total` key (reconciliation:
one fetcher, two historical field names).
"""
import logging
import math

from ...config.vendor_discovery import VENDOR_QUALITY_THRESHOLDS

logger = logging.getLogger(__name__)

_ACCREDITATION_BONUS = 0.5


def _reviews(vendor: dict) -> int:
    return int(vendor.get("review_count") or vendor.get("user_ratings_total") or 0)


def _score(vendor: dict) -> float:
    rating = vendor.get("rating") or 0.0
    bonus = _ACCREDITATION_BONUS if vendor.get("accreditation_tags") else 0.0
    return rating * math.log10(_reviews(vendor) + 1) + bonus


def filter_and_rank_vendors(candidates: list) -> list:
    """Apply quality gates then return top-N vendors by score.

    Quality gates (ALL must pass):
      - business_status == VENDOR_QUALITY_THRESHOLDS['required_business_status']
      - rating >= VENDOR_QUALITY_THRESHOLDS['min_rating']
      - review_count >= VENDOR_QUALITY_THRESHOLDS['min_review_count']
    Returns list sorted best-first, capped at top_n_vendors.
    """
    t = VENDOR_QUALITY_THRESHOLDS
    required_status = t["required_business_status"]
    min_rating = t["min_rating"]
    min_reviews = t["min_review_count"]
    top_n = t["top_n_vendors"]

    eligible = []
    for v in candidates:
        status = v.get("business_status", "UNKNOWN")
        rating = v.get("rating") or 0.0
        if status != required_status:
            logger.debug("Filtered %s: status=%s", v.get("name"), status)
            continue
        if rating < min_rating:
            logger.debug("Filtered %s: rating=%s", v.get("name"), rating)
            continue
        if _reviews(v) < min_reviews:
            logger.debug("Filtered %s: reviews=%s", v.get("name"), _reviews(v))
            continue
        eligible.append(v)

    ranked = sorted(eligible, key=_score, reverse=True)[:top_n]
    logger.info("Ranking: %d candidates → %d eligible → %d selected",
                len(candidates), len(eligible), len(ranked))
    return ranked
