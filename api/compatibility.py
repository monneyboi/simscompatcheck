"""
Compatibility scoring algorithm for The Sims 1 sims.

Scores are based on shared interests (70% weight) and compatible
personality traits (30% weight).
"""

from __future__ import annotations

from dataclasses import dataclass

from .iff_parser import Interests, Sim

# The 8 interest category names, matching Interests field names
INTEREST_CATEGORIES = [
    "travel", "violence", "politics", "sixties",
    "weather", "sports", "music", "outdoors",
]

# Personality traits that affect compatibility
# Sims with Outgoing >= 400, Playful >= 400, Nice >= 400 are easier to befriend
FRIENDLY_TRAITS = ["outgoing", "playful", "nice"]
FRIENDLY_THRESHOLD = 400


@dataclass
class CompatibilityResult:
    sim: Sim
    score: int  # 0-1000 final score
    common_interests: list[str]
    risky_topics: list[str]
    personality_match: int  # 0-1000
    relationship_daily: int | None = None   # -100 to 100, None if never met
    relationship_lifetime: int | None = None
    is_friend: bool = False


def _get_interest_value(interests: Interests, name: str) -> int:
    """Get an interest value by category name."""
    return getattr(interests, name)


def compute_interest_score(
    sim_a: Sim, sim_b: Sim
) -> tuple[int, list[str], list[str]]:
    """
    Compute interest compatibility between two sims.

    Returns (score, common_interests, risky_topics) where score is 0-1000.

    - common_interest: both sims have >= 700 in a category
    - risky_topic: one sim has >= 700 and the other has <= 300
    - score = min(1000, common_count * 125) - min(score, risky_count * 200),
      floored at 0
    """
    common_interests: list[str] = []
    risky_topics: list[str] = []

    for category in INTEREST_CATEGORIES:
        val_a = _get_interest_value(sim_a.interests, category)
        val_b = _get_interest_value(sim_b.interests, category)

        # Check for common interest: both >= 700
        if val_a >= 700 and val_b >= 700:
            common_interests.append(category)

        # Check for risky topic: one >= 700 and the other <= 300
        if (val_a >= 700 and val_b <= 300) or (val_b >= 700 and val_a <= 300):
            risky_topics.append(category)

    score = min(1000, len(common_interests) * 125)
    penalty = min(score, len(risky_topics) * 200)
    score = max(0, score - penalty)

    return score, common_interests, risky_topics


def compute_personality_score(other_sim: Sim) -> int:
    """
    Compute personality compatibility score for the OTHER sim.

    Counts how many of Outgoing >= 400, Playful >= 400, Nice >= 400
    the other sim meets. Each threshold met is worth 333 points.

    Returns 0-999 (3 * 333 = 999, capped at 1000).
    """
    count = 0
    for trait in FRIENDLY_TRAITS:
        value = getattr(other_sim.personality, trait)
        if value >= FRIENDLY_THRESHOLD:
            count += 1

    return min(1000, count * 333)


def compute_compatibility(sim: Sim, other: Sim) -> CompatibilityResult:
    """
    Compute full compatibility between *sim* and *other*.

    Final score = interest_score * 0.7 + personality_score * 0.3
    """
    interest_score, common_interests, risky_topics = compute_interest_score(
        sim, other
    )
    personality_score = compute_personality_score(other)

    final = interest_score * 0.7 + personality_score * 0.3

    # Look up existing relationship from sim -> other
    rel = sim.relationships.get(other.id)

    return CompatibilityResult(
        sim=other,
        score=int(final),
        common_interests=common_interests,
        risky_topics=risky_topics,
        personality_match=personality_score,
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
