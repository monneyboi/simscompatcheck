"""
Compatibility scoring algorithm for The Sims 1 sims.

Based on actual game mechanics decoded from BHAV behavior scripts and BCON
tuning constants. Conversation is 100% interest-based — personality does not
affect talk outcomes (it modulates specific interactions like Joke/Hug/Insult).

Game interest brackets (BCON 4112, 0-10 scale):
  value < 4  -> relationship delta -3
  value >= 4 -> relationship delta +3

On the 0-1000 normalized scale the threshold is 400.

The game picks one random topic per conversation. Both sims react based on
their interest level. For compatibility scoring, we measure per-topic
AGREEMENT: do both sims feel the same way about this topic?

Topics where both sims are interested (>= 400) are "common interests" —
weighted by the weaker sim's value (stronger shared passion = better).
Topics where they disagree are "risky" — penalized by the size of the gap.
Topics where neither cares don't affect the score.
"""

from __future__ import annotations

from dataclasses import dataclass

from .iff_parser import Interests, Sim, INTEREST_NAMES

# Threshold on the 0-1000 scale: below is negative, at or above is positive
INTEREST_THRESHOLD = 400

# Normalization range: max bonus is 15 topics * 1000 (all common at max),
# max penalty is 15 topics * 1000 (all risky with max gap).
_MAX_RAW = len(INTEREST_NAMES) * 1000


@dataclass
class CompatibilityResult:
    sim: Sim
    score: int  # 0-1000 final score
    common_interests: list[str]
    risky_topics: list[str]
    relationship_daily: int | None = None   # -100 to 100, None if never met
    relationship_lifetime: int | None = None
    is_friend: bool = False


def compute_interest_score(
    sim_a: Sim, sim_b: Sim,
) -> tuple[int, list[str], list[str]]:
    """
    Compute interest compatibility between two sims.

    For each of the 15 topics:
    - Common interest (both >= 400): bonus = min(va, vb)
      Higher shared values mean stronger agreement.
    - Risky topic (one >= 400, other < 400): penalty = |va - vb|
      Bigger gap means more friction.
    - Mutual disinterest (both < 400): no effect.
      Neither sim cares, so the topic is irrelevant.

    Returns (score, common_interests, risky_topics).
    """
    common_interests: list[str] = []
    risky_topics: list[str] = []
    raw = 0

    for name in INTEREST_NAMES:
        val_a = getattr(sim_a.interests, name)
        val_b = getattr(sim_b.interests, name)

        a_pos = val_a >= INTEREST_THRESHOLD
        b_pos = val_b >= INTEREST_THRESHOLD

        if a_pos and b_pos:
            common_interests.append(name)
            raw += min(val_a, val_b)
        elif a_pos != b_pos:
            risky_topics.append(name)
            raw -= abs(val_a - val_b)
        # both below threshold: no contribution

    # Normalize from [-_MAX_RAW, +_MAX_RAW] to [0, 1000]
    score = int((raw + _MAX_RAW) / (2 * _MAX_RAW) * 1000)
    score = max(0, min(1000, score))

    return score, common_interests, risky_topics


def compute_compatibility(sim: Sim, other: Sim) -> CompatibilityResult:
    """
    Compute full compatibility between *sim* and *other*.

    Final score is 100% interest-based (matching actual game mechanics).
    """
    score, common_interests, risky_topics = compute_interest_score(sim, other)

    # Look up existing relationship from sim -> other
    rel = sim.relationships.get(other.id)

    return CompatibilityResult(
        sim=other,
        score=score,
        common_interests=common_interests,
        risky_topics=risky_topics,
        relationship_daily=rel.daily if rel else None,
        relationship_lifetime=rel.lifetime if rel else None,
        is_friend=rel.is_friend if rel else False,
    )


def rank_compatibility(sim: Sim, all_sims: list[Sim]) -> list[CompatibilityResult]:
    """
    Rank all other sims by compatibility with *sim*, descending by score.
    The source sim is excluded from the results.
    """
    results: list[CompatibilityResult] = []

    for other in all_sims:
        if other.id == sim.id:
            continue
        results.append(compute_compatibility(sim, other))

    results.sort(key=lambda r: r.score, reverse=True)
    return results
