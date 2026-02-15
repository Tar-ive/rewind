"""
Parsers for each raw data source.

Each parser reads a file from DATA_DIR and returns structured Python dicts
that the signal classifier can categorise into explicit / implicit signals.
"""

from __future__ import annotations

import csv
import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from src.config.settings import (
    CERTS_FILE,
    DATA_DIR,
    GITHUB_FILE,
    LINKEDIN_FILE,
    TWITTER_FILE,
)


# ---------------------------------------------------------------------------
# LinkedIn JSON
# ---------------------------------------------------------------------------

def parse_linkedin(path: Path | None = None) -> dict[str, Any]:
    """Return structured profile + post data from the LinkedIn export JSON.

    Returns
    -------
    dict with keys:
        profile  – dict of top-level profile fields
        posts    – list[dict] per-post data
        stats    – aggregate engagement / activity statistics (implicit)
    """
    path = path or DATA_DIR / LINKEDIN_FILE
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)

    # --- Profile (explicit) ---
    profile_raw = raw.get("profiles", [{}])[0]
    profile = {
        "first_name": profile_raw.get("first_name", ""),
        "last_name": profile_raw.get("last_name", ""),
        "occupation": profile_raw.get("occupation", ""),
        "public_identifier": profile_raw.get("public_identifier", ""),
    }

    # --- Posts (explicit per-post + implicit aggregate) ---
    items: list[dict] = raw.get("items", [])
    posts: list[dict[str, Any]] = []
    hour_counter: Counter[int] = Counter()
    total_reactions = 0
    total_comments = 0
    total_impressions = 0
    engagement_rates: list[float] = []

    for item in items:
        text: str = item.get("text", "") or ""
        if not text.strip():
            continue

        created_at = item.get("post_created_at") or item.get("normalized_post_date")
        dt = _parse_iso(created_at)
        if dt:
            hour_counter[dt.hour] += 1

        reaction_count = item.get("reaction_count", 0) or 0
        comment_count = item.get("comment_count", 0) or 0
        impression_count = item.get("impression_count", 0) or 0
        eng_rate = item.get("engagement_rate", 0.0) or 0.0

        total_reactions += reaction_count
        total_comments += comment_count
        total_impressions += impression_count
        if eng_rate:
            engagement_rates.append(eng_rate)

        posts.append({
            "urn": item.get("urn", ""),
            "text": text,
            "content_type": item.get("content_type", ""),
            "hashtags": item.get("hashtags") or [],
            "reaction_count": reaction_count,
            "comment_count": comment_count,
            "impression_count": impression_count,
            "engagement_rate": eng_rate,
            "created_at": created_at or "",
        })

    # Implicit: aggregate stats
    num_posts = len(posts)
    avg_engagement = (
        sum(engagement_rates) / len(engagement_rates) if engagement_rates else 0.0
    )
    peak_posting_hours = [
        h for h, _ in hour_counter.most_common(4)
    ]  # top-4 hours

    stats = {
        "num_posts": num_posts,
        "total_reactions": total_reactions,
        "total_comments": total_comments,
        "total_impressions": total_impressions,
        "avg_engagement_rate": round(avg_engagement, 4),
        "peak_posting_hours": sorted(peak_posting_hours),
        "posting_hour_distribution": dict(hour_counter),
    }

    return {"profile": profile, "posts": posts, "stats": stats}


# ---------------------------------------------------------------------------
# Twitter / X CSV
# ---------------------------------------------------------------------------

def parse_twitter(path: Path | None = None) -> dict[str, Any]:
    """Parse the X (Twitter) post export CSV.

    Returns
    -------
    dict with keys:
        tweets  – list[dict] per-tweet data (explicit)
        stats   – aggregate behavioural statistics (implicit)
    """
    path = path or DATA_DIR / TWITTER_FILE
    df = pd.read_csv(path, dtype=str).fillna("")

    tweets: list[dict[str, Any]] = []
    hour_counter: Counter[int] = Counter()
    total_favorites = 0
    total_retweets = 0
    total_views = 0
    rt_count = 0
    original_count = 0

    for _, row in df.iterrows():
        full_text: str = row.get("Full Text", "")
        if not full_text.strip():
            continue

        is_retweet = full_text.startswith("RT @")
        if is_retweet:
            rt_count += 1
        else:
            original_count += 1

        created_at = row.get("Created At", "")
        dt = _parse_twitter_date(created_at)
        if dt:
            hour_counter[dt.hour] += 1

        fav = _safe_int(row.get("Favorite Count", "0"))
        rtc = _safe_int(row.get("Retweet Count", "0"))
        views = _safe_int(row.get("View Count", "0"))
        total_favorites += fav
        total_retweets += rtc
        total_views += views

        tweets.append({
            "tweet_id": row.get("Tweet Id", ""),
            "text": full_text,
            "is_retweet": is_retweet,
            "hashtags": row.get("Hashtags", ""),
            "user_mentions": row.get("User Mentions", ""),
            "favorite_count": fav,
            "retweet_count": rtc,
            "view_count": views,
            "language": row.get("Language", ""),
            "created_at": created_at,
        })

    num_tweets = len(tweets)
    rt_ratio = rt_count / num_tweets if num_tweets else 0.0
    peak_hours = [h for h, _ in hour_counter.most_common(4)]

    stats = {
        "num_tweets": num_tweets,
        "original_count": original_count,
        "rt_count": rt_count,
        "rt_ratio": round(rt_ratio, 4),
        "total_favorites": total_favorites,
        "total_retweets": total_retweets,
        "total_views": total_views,
        "peak_activity_hours": sorted(peak_hours),
        "activity_hour_distribution": dict(hour_counter),
    }

    return {"tweets": tweets, "stats": stats}


# ---------------------------------------------------------------------------
# GitHub Markdown Profile
# ---------------------------------------------------------------------------

def parse_github(path: Path | None = None) -> dict[str, Any]:
    """Parse the GitHub skills/profile markdown.

    Returns
    -------
    dict with keys:
        bio             – str (explicit)
        technical_skills – list[dict] (explicit)
        domain_skills    – list[dict] (explicit)
        behavioral_skills – list[dict] (implicit)
        languages        – dict[str, float] (implicit)
        working_style    – dict (implicit)
        contributions    – list[str] (explicit)
    """
    path = path or DATA_DIR / GITHUB_FILE
    content = path.read_text(encoding="utf-8")

    # Bio – first paragraph before ## sections
    bio_match = re.search(
        r"^## Saksham Adhikari\n\n(.+?)(?=\n\n)", content, re.DOTALL
    )
    bio = bio_match.group(1).strip() if bio_match else ""

    # Skills blocks
    technical_skills = _extract_skill_block(content, "technical")
    domain_skills = _extract_skill_block(content, "domain")
    behavioral_skills = _extract_skill_block(content, "behavioral")

    # Languages
    languages: dict[str, float] = {}
    lang_section = re.search(r"## Languages\n(.*?)(?=\n##|\Z)", content, re.DOTALL)
    if lang_section:
        for m in re.finditer(r"- (.+?):\s*([\d.]+)%", lang_section.group(1)):
            languages[m.group(1).strip()] = float(m.group(2))

    # Working style
    working_style: dict[str, Any] = {}
    ws_section = re.search(r"## Working Style\n(.*?)(?=\n##|\n</profile>|\Z)", content, re.DOTALL)
    if ws_section:
        archetype_m = re.search(r"Archetype:\s*(.+)", ws_section.group(1))
        exec_m = re.search(r"Execution vs Exploration:\s*([\d.]+)%", ws_section.group(1))
        spec_m = re.search(r"Broad vs Specialized:\s*([\d.]+)%", ws_section.group(1))
        working_style = {
            "archetype": archetype_m.group(1).strip() if archetype_m else "",
            "execution_pct": float(exec_m.group(1)) if exec_m else 0,
            "specialized_pct": float(spec_m.group(1)) if spec_m else 0,
        }

    # External contributions
    contributions: list[str] = []
    contrib_section = re.search(
        r"## External Contributions\n(.*?)(?=\n##|\Z)", content, re.DOTALL
    )
    if contrib_section:
        contributions = re.findall(r"- (.+)", contrib_section.group(1))

    return {
        "bio": bio,
        "technical_skills": technical_skills,
        "domain_skills": domain_skills,
        "behavioral_skills": behavioral_skills,
        "languages": languages,
        "working_style": working_style,
        "contributions": contributions,
    }


# ---------------------------------------------------------------------------
# Certifications CSV
# ---------------------------------------------------------------------------

def parse_certs(path: Path | None = None) -> list[dict[str, str]]:
    """Parse the Certifications CSV.

    Returns a list of dicts, one per certification row (all explicit).
    """
    path = path or DATA_DIR / CERTS_FILE
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        certs = []
        for row in reader:
            certs.append({
                "name": row.get("Name", "").strip(),
                "url": row.get("Url", "").strip(),
                "authority": row.get("Authority", "").strip(),
                "started_on": row.get("Started On", "").strip(),
                "finished_on": row.get("Finished On", "").strip(),
                "license_number": row.get("License Number", "").strip(),
            })
    return certs


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_iso(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def _parse_twitter_date(s: str) -> datetime | None:
    """Parse Twitter-style date: 'Thu Nov 06 23:01:27 +0000 2025'."""
    if not s:
        return None
    try:
        return datetime.strptime(s, "%a %b %d %H:%M:%S %z %Y")
    except (ValueError, TypeError):
        return None


def _safe_int(v: str) -> int:
    try:
        return int(v)
    except (ValueError, TypeError):
        return 0


def _extract_skill_block(md: str, skill_type: str) -> list[dict[str, str]]:
    """Extract skills from a <skills type="..."> block in the markdown."""
    pattern = rf'<skills type="{skill_type}">(.*?)</skills>'
    match = re.search(pattern, md, re.DOTALL)
    if not match:
        return []

    block = match.group(1)
    skills: list[dict[str, str]] = []
    current_name = ""
    current_indicators = ""
    current_evidence = ""
    current_tech = ""

    for line in block.strip().splitlines():
        line = line.strip()
        if line.startswith("- ") and not line.startswith("- Indicators:") and not line.startswith("- Evidence:") and not line.startswith("- Technologies:"):
            # Save previous if exists
            if current_name:
                skills.append({
                    "name": current_name,
                    "indicators": current_indicators,
                    "evidence": current_evidence,
                    "technologies": current_tech,
                })
            current_name = line[2:].strip()
            current_indicators = ""
            current_evidence = ""
            current_tech = ""
        elif line.startswith("- Indicators:"):
            current_indicators = line.replace("- Indicators:", "").strip()
        elif line.startswith("- Evidence:"):
            current_evidence = line.replace("- Evidence:", "").strip()
        elif line.startswith("- Technologies:"):
            current_tech = line.replace("- Technologies:", "").strip()

    # Don't forget the last one
    if current_name:
        skills.append({
            "name": current_name,
            "indicators": current_indicators,
            "evidence": current_evidence,
            "technologies": current_tech,
        })

    return skills
