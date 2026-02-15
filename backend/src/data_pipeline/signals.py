"""
Signal classification layer.

Takes raw parsed data and produces typed ExplicitSignal / ImplicitSignal
objects ready for embedding and storage in Redis.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from typing import Any

from src.data_pipeline.parsers import (
    parse_certs,
    parse_github,
    parse_linkedin,
    parse_twitter,
)


@dataclass
class ExplicitSignal:
    """A directly-stated factual data point."""

    signal_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source: str = ""        # linkedin | twitter | github | certs
    category: str = ""      # profile | post | tweet | cert | skill | contribution
    text: str = ""          # human-readable text for embedding
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ImplicitSignal:
    """An inferred behavioural pattern."""

    signal_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source: str = ""        # linkedin | twitter | github
    pattern_type: str = ""  # peak_hours | engagement | style | interests | language_affinity | working_style
    description: str = ""   # human-readable summary for embedding
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_all_signals() -> tuple[list[ExplicitSignal], list[ImplicitSignal]]:
    """Parse all data sources and return classified signals."""
    explicit: list[ExplicitSignal] = []
    implicit: list[ImplicitSignal] = []

    _classify_linkedin(explicit, implicit)
    _classify_twitter(explicit, implicit)
    _classify_github(explicit, implicit)
    _classify_certs(explicit)

    return explicit, implicit


# ---------------------------------------------------------------------------
# LinkedIn
# ---------------------------------------------------------------------------

def _classify_linkedin(
    explicit: list[ExplicitSignal],
    implicit: list[ImplicitSignal],
) -> None:
    data = parse_linkedin()

    # Explicit: profile
    profile = data["profile"]
    explicit.append(ExplicitSignal(
        source="linkedin",
        category="profile",
        text=(
            f"{profile['first_name']} {profile['last_name']} — "
            f"{profile['occupation']}"
        ),
        metadata=profile,
    ))

    # Explicit: individual posts
    for post in data["posts"]:
        text = post["text"]
        if len(text) < 10:
            continue  # skip trivial reshares
        explicit.append(ExplicitSignal(
            source="linkedin",
            category="post",
            text=text[:2000],  # cap for embedding
            metadata={
                "urn": post["urn"],
                "content_type": post["content_type"],
                "reaction_count": post["reaction_count"],
                "comment_count": post["comment_count"],
                "created_at": post["created_at"],
            },
        ))

    # Implicit: posting cadence / peak hours
    stats = data["stats"]
    implicit.append(ImplicitSignal(
        source="linkedin",
        pattern_type="peak_hours",
        description=(
            f"LinkedIn posting peaks at hours {stats['peak_posting_hours']} UTC. "
            f"Total {stats['num_posts']} posts with average engagement rate "
            f"{stats['avg_engagement_rate']}%."
        ),
        metadata={
            "peak_posting_hours": stats["peak_posting_hours"],
            "posting_hour_distribution": stats["posting_hour_distribution"],
        },
    ))

    # Implicit: engagement style
    implicit.append(ImplicitSignal(
        source="linkedin",
        pattern_type="engagement",
        description=(
            f"LinkedIn engagement profile: {stats['total_reactions']} total reactions, "
            f"{stats['total_comments']} comments, {stats['total_impressions']} impressions "
            f"across {stats['num_posts']} posts. Average engagement rate {stats['avg_engagement_rate']}%."
        ),
        metadata={
            "total_reactions": stats["total_reactions"],
            "total_comments": stats["total_comments"],
            "total_impressions": stats["total_impressions"],
            "avg_engagement_rate": stats["avg_engagement_rate"],
        },
    ))


# ---------------------------------------------------------------------------
# Twitter / X
# ---------------------------------------------------------------------------

def _classify_twitter(
    explicit: list[ExplicitSignal],
    implicit: list[ImplicitSignal],
) -> None:
    data = parse_twitter()

    # Explicit: individual tweets
    for tweet in data["tweets"]:
        text = tweet["text"]
        if len(text) < 10:
            continue
        explicit.append(ExplicitSignal(
            source="twitter",
            category="tweet",
            text=text[:2000],
            metadata={
                "tweet_id": tweet["tweet_id"],
                "is_retweet": tweet["is_retweet"],
                "favorite_count": tweet["favorite_count"],
                "view_count": tweet["view_count"],
                "created_at": tweet["created_at"],
            },
        ))

    # Implicit: activity patterns
    stats = data["stats"]
    implicit.append(ImplicitSignal(
        source="twitter",
        pattern_type="peak_hours",
        description=(
            f"Twitter/X activity peaks at hours {stats['peak_activity_hours']} UTC. "
            f"{stats['num_tweets']} total tweets, RT ratio {stats['rt_ratio']}."
        ),
        metadata={
            "peak_activity_hours": stats["peak_activity_hours"],
            "activity_hour_distribution": stats["activity_hour_distribution"],
        },
    ))

    # Implicit: engagement velocity
    implicit.append(ImplicitSignal(
        source="twitter",
        pattern_type="engagement",
        description=(
            f"Twitter engagement: {stats['total_favorites']} favorites, "
            f"{stats['total_views']} views across {stats['num_tweets']} tweets. "
            f"Retweet ratio: {stats['rt_ratio']} ({stats['rt_count']} RTs vs "
            f"{stats['original_count']} originals)."
        ),
        metadata={
            "total_favorites": stats["total_favorites"],
            "total_views": stats["total_views"],
            "rt_ratio": stats["rt_ratio"],
        },
    ))

    # Implicit: interest clusters from mentions
    mention_counter: dict[str, int] = {}
    for tweet in data["tweets"]:
        mentions = tweet.get("user_mentions", "")
        if mentions:
            for m in mentions.split(","):
                m = m.strip()
                if m:
                    mention_counter[m] = mention_counter.get(m, 0) + 1
    if mention_counter:
        top_mentions = sorted(mention_counter.items(), key=lambda x: -x[1])[:10]
        implicit.append(ImplicitSignal(
            source="twitter",
            pattern_type="interests",
            description=(
                f"Top Twitter mention clusters: "
                + ", ".join(f"@{m} ({c}x)" for m, c in top_mentions)
                + ". These reflect engagement interests and professional network."
            ),
            metadata={"top_mentions": dict(top_mentions)},
        ))


# ---------------------------------------------------------------------------
# GitHub
# ---------------------------------------------------------------------------

def _classify_github(
    explicit: list[ExplicitSignal],
    implicit: list[ImplicitSignal],
) -> None:
    data = parse_github()

    # Explicit: bio
    if data["bio"]:
        explicit.append(ExplicitSignal(
            source="github",
            category="profile",
            text=data["bio"],
            metadata={"source_section": "bio"},
        ))

    # Explicit: technical skills
    for skill in data["technical_skills"]:
        explicit.append(ExplicitSignal(
            source="github",
            category="skill",
            text=(
                f"Technical skill: {skill['name']}. "
                f"{skill['indicators']} "
                f"Technologies: {skill['technologies']}."
            ),
            metadata=skill,
        ))

    # Explicit: domain skills
    for skill in data["domain_skills"]:
        explicit.append(ExplicitSignal(
            source="github",
            category="skill",
            text=(
                f"Domain skill: {skill['name']}. "
                f"{skill['indicators']} "
                f"Technologies: {skill['technologies']}."
            ),
            metadata=skill,
        ))

    # Explicit: external contributions
    for contrib in data["contributions"]:
        explicit.append(ExplicitSignal(
            source="github",
            category="contribution",
            text=f"Open-source contribution to {contrib}.",
            metadata={"repo": contrib},
        ))

    # Implicit: language affinity
    languages = data["languages"]
    if languages:
        lang_desc = ", ".join(f"{lang} ({pct}%)" for lang, pct in languages.items())
        implicit.append(ImplicitSignal(
            source="github",
            pattern_type="language_affinity",
            description=(
                f"Programming language distribution on GitHub: {lang_desc}. "
                f"Indicates technology preferences and expertise areas."
            ),
            metadata={"languages": languages},
        ))

    # Implicit: working style
    ws = data["working_style"]
    if ws:
        implicit.append(ImplicitSignal(
            source="github",
            pattern_type="working_style",
            description=(
                f"Working style archetype: {ws.get('archetype', 'unknown')}. "
                f"Execution focus: {ws.get('execution_pct', 0)}%, "
                f"Specialization: {ws.get('specialized_pct', 0)}%. "
                f"Indicates a preference for deep, focused work on specific domains."
            ),
            metadata=ws,
        ))

    # Implicit: behavioral skills (these are inferred patterns)
    for skill in data["behavioral_skills"]:
        implicit.append(ImplicitSignal(
            source="github",
            pattern_type="style",
            description=(
                f"Behavioral pattern: {skill['name']}. {skill['indicators']}"
            ),
            metadata=skill,
        ))


# ---------------------------------------------------------------------------
# Certifications
# ---------------------------------------------------------------------------

def _classify_certs(explicit: list[ExplicitSignal]) -> None:
    certs = parse_certs()
    for cert in certs:
        explicit.append(ExplicitSignal(
            source="certs",
            category="cert",
            text=(
                f"Certification: {cert['name']} from {cert['authority']}. "
                f"Started {cert['started_on']}."
            ),
            metadata=cert,
        ))
