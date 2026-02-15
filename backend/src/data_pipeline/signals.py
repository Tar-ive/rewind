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
    parse_daily_goals,
    parse_github,
    parse_linkedin,
    parse_reflections,
    parse_resume,
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
    _classify_daily_goals(explicit, implicit)
    _classify_reflections(explicit, implicit)
    _classify_resume(explicit, implicit)

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


# ---------------------------------------------------------------------------
# Daily Goals
# ---------------------------------------------------------------------------

def _classify_daily_goals(
    explicit: list[ExplicitSignal],
    implicit: list[ImplicitSignal],
) -> None:
    entries = parse_daily_goals()
    if not entries:
        return

    # Explicit: individual goal entries with completion status
    for entry in entries:
        for task in entry["tasks"]:
            status = "completed" if task["completed"] else "incomplete"
            explicit.append(ExplicitSignal(
                source="daily_goals",
                category="goal",
                text=(
                    f"Daily goal ({entry['day_id']}): [{status}] {task['text']}"
                    + (f" — {task['note']}" if task["note"] else "")
                ),
                metadata={
                    "day_id": entry["day_id"],
                    "completed": task["completed"],
                    "category": task["category"],
                    "note": task["note"],
                },
            ))

    # Implicit: completion rate trends
    completion_rates = [e["completion_rate"] for e in entries]
    avg_completion = sum(completion_rates) / len(completion_rates) if completion_rates else 0

    implicit.append(ImplicitSignal(
        source="daily_goals",
        pattern_type="schedule_adherence",
        description=(
            f"Daily goal completion across {len(entries)} days: "
            f"average {avg_completion:.1%} completion rate. "
            f"Range: {min(completion_rates):.1%} to {max(completion_rates):.1%}."
        ),
        metadata={
            "avg_completion_rate": round(avg_completion, 4),
            "daily_rates": {e["day_id"]: e["completion_rate"] for e in entries},
            "num_days_tracked": len(entries),
        },
    ))

    # Implicit: procrastination / consistency pattern
    import statistics
    if len(completion_rates) >= 2:
        stddev = statistics.stdev(completion_rates)
    else:
        stddev = 0.0

    consistency_label = "high" if stddev < 0.15 else ("moderate" if stddev < 0.3 else "low")
    implicit.append(ImplicitSignal(
        source="daily_goals",
        pattern_type="consistency",
        description=(
            f"Goal completion consistency: {consistency_label} "
            f"(stddev={stddev:.3f}). "
            f"{'Steady performer' if consistency_label == 'high' else 'Variable output — possible sporadic work pattern'}."
        ),
        metadata={
            "consistency": consistency_label,
            "stddev": round(stddev, 4),
        },
    ))

    # Implicit: category distribution across all days
    total_cats: dict[str, int] = {}
    for entry in entries:
        for cat, count in entry["category_distribution"].items():
            total_cats[cat] = total_cats.get(cat, 0) + count
    if total_cats:
        dominant = max(total_cats, key=lambda c: total_cats[c])
        implicit.append(ImplicitSignal(
            source="daily_goals",
            pattern_type="interests",
            description=(
                f"Task category distribution: "
                + ", ".join(f"{c}={n}" for c, n in sorted(total_cats.items(), key=lambda x: -x[1]))
                + f". Dominant focus area: {dominant}."
            ),
            metadata={"category_distribution": total_cats, "dominant": dominant},
        ))

    # Implicit: reflection sentiment trend
    sentiments = [
        (e["day_id"], e["reflection_sentiment"], e["reflection_sentiment_score"])
        for e in entries if e["has_reflection"]
    ]
    if sentiments:
        avg_sent = sum(s[2] for s in sentiments) / len(sentiments)
        implicit.append(ImplicitSignal(
            source="daily_goals",
            pattern_type="sentiment",
            description=(
                f"Reflection sentiment across {len(sentiments)} entries: "
                f"average score {avg_sent:.3f} "
                f"({'positive trend' if avg_sent > 0.1 else 'negative trend' if avg_sent < -0.1 else 'neutral'}). "
                f"Self-reflection present in {len(sentiments)}/{len(entries)} days."
            ),
            metadata={
                "avg_sentiment": round(avg_sent, 4),
                "reflection_count": len(sentiments),
                "sentiments": {s[0]: {"label": s[1], "score": s[2]} for s in sentiments},
            },
        ))

    # Implicit: growth trend (is completion rate improving over time?)
    if len(completion_rates) >= 3:
        first_half = completion_rates[: len(completion_rates) // 2]
        second_half = completion_rates[len(completion_rates) // 2:]
        first_avg = sum(first_half) / len(first_half)
        second_avg = sum(second_half) / len(second_half)
        trend = "improving" if second_avg > first_avg + 0.05 else (
            "declining" if second_avg < first_avg - 0.05 else "stable"
        )
        implicit.append(ImplicitSignal(
            source="daily_goals",
            pattern_type="growth_trend",
            description=(
                f"Completion rate trend: {trend}. "
                f"First half avg: {first_avg:.1%}, second half avg: {second_avg:.1%}."
            ),
            metadata={
                "trend": trend,
                "first_half_avg": round(first_avg, 4),
                "second_half_avg": round(second_avg, 4),
            },
        ))


# ---------------------------------------------------------------------------
# Reflections
# ---------------------------------------------------------------------------

def _classify_reflections(
    explicit: list[ExplicitSignal],
    implicit: list[ImplicitSignal],
) -> None:
    data = parse_reflections()
    if not data["documents"]:
        return

    # Explicit: stated goals and progress markers
    for doc in data["documents"]:
        for section_name, bullets in doc["sections"].items():
            for bullet in bullets:
                explicit.append(ExplicitSignal(
                    source="reflections",
                    category="goal" if doc["type"] == "goals" else "reflection",
                    text=(
                        f"[{section_name}] {bullet['title']}"
                        + (f": {bullet['detail']}" if bullet["detail"] else "")
                    ),
                    metadata={
                        "filename": doc["filename"],
                        "section": section_name,
                        "type": doc["type"],
                    },
                ))

    # Implicit: self-awareness and growth velocity
    gi = data["growth_indicators"]
    implicit.append(ImplicitSignal(
        source="reflections",
        pattern_type="self_awareness",
        description=(
            f"Self-awareness score: {gi['self_awareness_score']:.2f}/1.0. "
            f"Continue: {gi['continue_count']}, Stop: {gi['stop_count']}, "
            f"Start: {gi['start_count']}. "
            f"Mitigated: {gi['mitigated_count']}, Needs development: {gi['needs_development_count']}."
        ),
        metadata=gi,
    ))

    implicit.append(ImplicitSignal(
        source="reflections",
        pattern_type="growth_velocity",
        description=(
            f"Growth velocity: {gi['growth_velocity']:.2f} "
            f"({gi['mitigated_count']} issues resolved out of "
            f"{gi['mitigated_count'] + gi['needs_development_count']} total). "
            f"{'Strong follow-through' if gi['growth_velocity'] > 0.6 else 'Room for improvement in execution'}."
        ),
        metadata={
            "velocity": gi["growth_velocity"],
            "mitigated": gi["mitigated_count"],
            "pending": gi["needs_development_count"],
        },
    ))


# ---------------------------------------------------------------------------
# Resume / CV
# ---------------------------------------------------------------------------

def _classify_resume(
    explicit: list[ExplicitSignal],
    implicit: list[ImplicitSignal],
) -> None:
    data = parse_resume()
    if not data["experiences"] and not data["skills"]:
        return

    # Explicit: skills
    if data["skills"]:
        explicit.append(ExplicitSignal(
            source="resume",
            category="skill",
            text=f"Technical skills: {', '.join(data['skills'])}.",
            metadata={"skills": data["skills"]},
        ))

    # Explicit: experiences
    for exp in data["experiences"]:
        explicit.append(ExplicitSignal(
            source="resume",
            category="experience",
            text=f"Experience: {exp['organization']} ({exp['dates']}).",
            metadata=exp,
        ))

    # Explicit: quantified achievements
    for q in data["quantifications"][:30]:  # cap to avoid excessive signals
        explicit.append(ExplicitSignal(
            source="resume",
            category="achievement",
            text=f"Achievement: {q['value']}{q['unit']} — {q['context'][:150]}",
            metadata=q,
        ))

    # Explicit: awards
    for award in data["awards"]:
        explicit.append(ExplicitSignal(
            source="resume",
            category="award",
            text=f"Award: {award['title']} ({award['year']}).",
            metadata=award,
        ))

    # Explicit: scholarships
    for schol in data["scholarships"]:
        explicit.append(ExplicitSignal(
            source="resume",
            category="scholarship",
            text=f"Scholarship: {schol['title']} ({schol['year']}).",
            metadata=schol,
        ))

    # Implicit: ambition level (number of quantified achievements + publications + awards)
    ambition_score = min(
        (len(data["quantifications"]) * 0.3
         + data["publications_count"] * 1.5
         + len(data["awards"]) * 1.0
         + len(data["scholarships"]) * 0.5)
        / 15.0,
        1.0,
    )
    implicit.append(ImplicitSignal(
        source="resume",
        pattern_type="ambition",
        description=(
            f"Ambition signal: {ambition_score:.2f}/1.0. "
            f"{len(data['quantifications'])} quantified achievements, "
            f"{data['publications_count']} publications, "
            f"{len(data['awards'])} awards, {len(data['scholarships'])} scholarships."
        ),
        metadata={
            "ambition_score": round(ambition_score, 4),
            "quant_count": len(data["quantifications"]),
            "pub_count": data["publications_count"],
            "award_count": len(data["awards"]),
            "scholarship_count": len(data["scholarships"]),
        },
    ))

    # Implicit: domain focus
    exp_orgs = [e["organization"].lower() for e in data["experiences"]]
    is_research = any("research" in o or "center" in o for o in exp_orgs)
    is_industry = any("google" in o or "intern" in o for o in exp_orgs)
    domain = "research-industry hybrid" if is_research and is_industry else (
        "research-focused" if is_research else (
            "industry-focused" if is_industry else "general"
        )
    )
    implicit.append(ImplicitSignal(
        source="resume",
        pattern_type="domain_focus",
        description=(
            f"Career domain: {domain}. "
            f"{len(data['experiences'])} professional experiences spanning "
            f"{'research and industry' if domain == 'research-industry hybrid' else domain}."
        ),
        metadata={"domain": domain, "experience_count": len(data["experiences"])},
    ))
