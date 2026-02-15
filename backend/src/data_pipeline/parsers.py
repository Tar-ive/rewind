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
    DAILY_GOALS_DIR,
    GITHUB_FILE,
    LINKEDIN_FILE,
    REFLECTIONS_DIR,
    RESUME_FILE,
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
# Daily Goals Markdown
# ---------------------------------------------------------------------------

# Task category keywords for heuristic classification
_CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "academic": [
        "assignment", "exam", "class", "lecture", "study", "homework",
        "research", "paper", "thesis", "professor", "dr.", "chapter",
        "algorithm", "practice", "book", "discussion", "history",
        "geology", "english", "python", "datathon",
    ],
    "professional": [
        "pr", "work", "meeting", "email", "project", "intern", "job",
        "ebay", "ml", "ai", "deploy", "code", "engineering", "submit",
        "challenge", "hackathon", "linkedin", "position", "resume",
        "call", "client", "startup", "grant", "index",
    ],
    "social": [
        "meet", "call", "message", "text", "dinner", "lunch",
        "friend", "blessing", "dhruvil", "raghav", "tanya", "rick",
        "nani", "kusum", "girlfriend", "avi",
    ],
    "personal": [
        "shower", "laundry", "gym", "water", "sleep", "cook",
        "groceries", "clean", "yoga", "meditate", "temple",
        "sanatan", "taxes", "pay", "buy", "return", "maintenance",
        "tiramisu",
    ],
}

# Sentiment keywords for reflection text
_POSITIVE_WORDS = {
    "great", "good", "better", "improving", "learning", "progress",
    "productive", "focused", "accomplished", "succeeded", "motivated",
    "disciplined", "excellent", "achieved", "interesting", "dopamine",
    "love", "excited", "proud", "strong", "confident",
}
_NEGATIVE_WORDS = {
    "wasted", "distracted", "lazy", "failed", "bad", "low",
    "procrastinated", "didn't", "forgot", "missed", "stressed",
    "anxious", "overwhelmed", "tired", "burnout", "unfocused",
    "comfortable", "discipline", "waste",
}


def _classify_task_category(task_text: str) -> str:
    """Classify a task into a category using keyword heuristics."""
    lower = task_text.lower()
    scores: dict[str, int] = {cat: 0 for cat in _CATEGORY_KEYWORDS}
    for cat, keywords in _CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if kw in lower:
                scores[cat] += 1
    best = max(scores, key=lambda c: scores[c])
    return best if scores[best] > 0 else "uncategorized"


def _simple_sentiment(text: str) -> tuple[str, float]:
    """Return (label, score) for a text using keyword counting.

    Score ranges from -1.0 (very negative) to 1.0 (very positive).
    """
    words = set(re.findall(r"[a-z']+", text.lower()))
    pos = len(words & _POSITIVE_WORDS)
    neg = len(words & _NEGATIVE_WORDS)
    total = pos + neg
    if total == 0:
        return "neutral", 0.0
    score = (pos - neg) / total
    if score > 0.2:
        label = "positive"
    elif score < -0.2:
        label = "negative"
    else:
        label = "neutral"
    return label, round(score, 3)


def parse_daily_goals(directory: Path | None = None) -> list[dict[str, Any]]:
    """Parse all daily-goal markdown files.

    Each file uses checkbox syntax:
        - [x] completed task -> optional note
        - [ ] incomplete task

    Non-checkbox lines at the bottom are treated as reflection text.

    Returns a list of dicts (one per file / day), sorted by filename.
    """
    directory = directory or DATA_DIR / DAILY_GOALS_DIR
    if not directory.exists():
        return []

    entries: list[dict[str, Any]] = []
    for md_file in sorted(directory.glob("*.md")):
        content = md_file.read_text(encoding="utf-8")
        lines = content.splitlines()

        tasks: list[dict[str, Any]] = []
        reflection_lines: list[str] = []
        in_tasks = True  # track transition from tasks to reflection

        for line in lines:
            stripped = line.strip()
            if not stripped:
                if tasks:  # blank line after tasks signals reflection zone
                    in_tasks = False
                continue

            # Match checkbox pattern: - [x] or - [ ]
            chk = re.match(r"^-\s*\[([ xX])\]\s*(.+)", stripped)
            if chk:
                in_tasks = True
                completed = chk.group(1).lower() == "x"
                raw_text = chk.group(2).strip()

                # Split on -> for annotation
                note = ""
                task_text = raw_text
                if "->" in raw_text:
                    parts = raw_text.split("->", 1)
                    task_text = parts[0].strip()
                    note = parts[1].strip()

                category = _classify_task_category(task_text)
                tasks.append({
                    "text": task_text,
                    "completed": completed,
                    "note": note,
                    "category": category,
                })
            elif not in_tasks or (not stripped.startswith("- ") and not stripped.startswith("http")):
                # Non-checkbox, non-URL line -> reflection
                if not stripped.startswith("http"):
                    reflection_lines.append(stripped)

        if not tasks:
            continue  # skip files with no task data (e.g. code files)

        total = len(tasks)
        completed_count = sum(1 for t in tasks if t["completed"])
        completion_rate = completed_count / total if total else 0.0

        # Category distribution
        cat_dist: dict[str, int] = {}
        for t in tasks:
            cat_dist[t["category"]] = cat_dist.get(t["category"], 0) + 1

        reflection_text = " ".join(reflection_lines).strip()
        sentiment_label, sentiment_score = _simple_sentiment(reflection_text)

        entries.append({
            "day_id": md_file.stem,  # e.g. "287"
            "filename": md_file.name,
            "tasks": tasks,
            "total_tasks": total,
            "completed_count": completed_count,
            "completion_rate": round(completion_rate, 4),
            "category_distribution": cat_dist,
            "reflection_text": reflection_text,
            "reflection_sentiment": sentiment_label,
            "reflection_sentiment_score": sentiment_score,
            "has_reflection": bool(reflection_text),
        })

    return entries


# ---------------------------------------------------------------------------
# Internship Reflections
# ---------------------------------------------------------------------------

def parse_reflections(directory: Path | None = None) -> dict[str, Any]:
    """Parse structured reflection markdown files.

    Expected sections: Continue Doing, Stop Doing, Start Doing,
    Progress Assessment (with sub-sections).

    Returns a dict with:
        documents  – list of parsed reflection documents
        growth_indicators – aggregated growth signals
    """
    directory = directory or DATA_DIR / REFLECTIONS_DIR
    if not directory.exists():
        return {"documents": [], "growth_indicators": {}}

    documents: list[dict[str, Any]] = []
    all_continue: list[str] = []
    all_stop: list[str] = []
    all_start: list[str] = []
    all_mitigated: list[str] = []
    all_progress: list[str] = []
    all_needs_dev: list[str] = []

    for md_file in sorted(directory.glob("*.md")):
        content = md_file.read_text(encoding="utf-8")

        doc: dict[str, Any] = {
            "filename": md_file.name,
            "type": "reflection" if "reflection" in md_file.stem.lower() else "goals",
            "sections": {},
            "bullet_count": 0,
        }

        # Extract sections by ## headers
        current_section = "intro"
        section_lines: dict[str, list[str]] = {"intro": []}

        for line in content.splitlines():
            header = re.match(r"^##\s*(?:\(\d+\)\s*)?(.+)", line)
            if header:
                current_section = header.group(1).strip().lower()
                section_lines.setdefault(current_section, [])
                continue
            section_lines.setdefault(current_section, []).append(line)

        # Extract bullet points per section
        for section, lines in section_lines.items():
            bullets = []
            for line in lines:
                bm = re.match(r"^-\s+\*\*(.+?)\*\*[:\s]*(.+)?", line)
                if bm:
                    bullets.append({
                        "title": bm.group(1).strip(),
                        "detail": (bm.group(2) or "").strip(),
                    })
                elif re.match(r"^-\s+", line):
                    bullets.append({"title": line.lstrip("- ").strip(), "detail": ""})
            if bullets:
                doc["sections"][section] = bullets
                doc["bullet_count"] += len(bullets)

        # Aggregate for growth indicators
        for s_key, store in [
            ("continue doing", all_continue),
            ("stop doing", all_stop),
            ("start doing", all_start),
            ("successfully mitigated", all_mitigated),
            ("progress", all_progress),
            ("requires further development", all_needs_dev),
        ]:
            for b in doc["sections"].get(s_key, []):
                store.append(b["title"])

        # For goals-type files, extract Q&A structure
        if doc["type"] == "goals":
            for section, lines in section_lines.items():
                if "learn" in section or "avoid" in section or "communicate" in section or "obstacle" in section:
                    doc["sections"][section] = [
                        {"title": line.lstrip("- ").strip(), "detail": ""}
                        for line in lines
                        if line.strip().startswith("-")
                    ]

        documents.append(doc)

    # Growth indicators
    growth_indicators = {
        "continue_count": len(all_continue),
        "stop_count": len(all_stop),
        "start_count": len(all_start),
        "mitigated_count": len(all_mitigated),
        "in_progress_count": len(all_progress),
        "needs_development_count": len(all_needs_dev),
        "self_awareness_score": _compute_self_awareness(
            all_continue, all_stop, all_start, all_mitigated, all_needs_dev,
        ),
        "growth_velocity": _compute_growth_velocity(all_mitigated, all_needs_dev),
    }

    return {"documents": documents, "growth_indicators": growth_indicators}


def _compute_self_awareness(
    cont: list, stop: list, start: list, mitigated: list, needs: list,
) -> float:
    """Score 0-1 for depth of self-reflection.

    Based on: diversity of categories, acknowledgement of weaknesses,
    and evidence of follow-through (mitigated items).
    """
    # Having items in all categories indicates high self-awareness
    category_coverage = sum(1 for lst in [cont, stop, start, mitigated, needs] if lst) / 5.0
    # Acknowledging weaknesses (stop + needs) is a strong signal
    weakness_signal = min(len(stop) + len(needs), 6) / 6.0
    # Follow-through (mitigated items) shows action on reflection
    followthrough = min(len(mitigated), 5) / 5.0
    return round(0.4 * category_coverage + 0.3 * weakness_signal + 0.3 * followthrough, 4)


def _compute_growth_velocity(mitigated: list, needs: list) -> float:
    """Ratio of mitigated to total improvement areas (0-1).

    Higher means more issues have been addressed over time.
    """
    total = len(mitigated) + len(needs)
    if total == 0:
        return 0.5  # neutral
    return round(len(mitigated) / total, 4)


# ---------------------------------------------------------------------------
# Resume / CV
# ---------------------------------------------------------------------------

def parse_resume(path: Path | None = None) -> dict[str, Any]:
    """Parse resume markdown to extract structured professional data.

    Returns dict with:
        quantifications – list of numeric achievements with context
        experiences – list of role entries
        skills – list of skill strings
        publications – int count
        awards – list of award entries
        scholarships – list of scholarship entries
    """
    path = path or DATA_DIR / RESUME_FILE
    if not path.exists():
        return {
            "quantifications": [],
            "experiences": [],
            "skills": [],
            "publications_count": 0,
            "awards": [],
            "scholarships": [],
        }
    content = path.read_text(encoding="utf-8")

    # --- Quantified achievements ---
    # Match patterns like: 40%, $5,000, 17M, 30,000, 619, 2,454 etc.
    quant_pattern = re.compile(
        r'(\d[\d,]*(?:\.\d+)?(?:[MBK])?)\s*'      # number
        r'(%|(?:\s*(?:customers|users|downloads|interactions|sequences|'
        r'papers|stars|forks|members|person|students|families|'
        r'samples/second|data points|patient|hours|grants|'
        r'minutes|seconds|ms|KB|MB|GB))?)',
        re.IGNORECASE,
    )
    quantifications: list[dict[str, str]] = []
    for line in content.splitlines():
        line_clean = line.strip().lstrip("•").strip()
        if not line_clean:
            continue
        for m in quant_pattern.finditer(line_clean):
            number = m.group(1)
            unit = (m.group(2) or "").strip()
            # Get surrounding context (the full bullet point)
            context = line_clean[:200]
            quantifications.append({
                "value": number,
                "unit": unit,
                "context": context,
            })

    # Deduplicate by (value, context)
    seen: set[tuple[str, str]] = set()
    unique_quants: list[dict[str, str]] = []
    for q in quantifications:
        key = (q["value"], q["context"][:80])
        if key not in seen:
            seen.add(key)
            unique_quants.append(q)
    quantifications = unique_quants

    # --- Experience entries ---
    experiences: list[dict[str, str]] = []
    exp_pattern = re.compile(
        r"\*\*(.+?)\s+(\w+\s+\d{4}\s*[-–]\s*(?:\w+\s+\d{4}|Current))\*\*"
    )
    for m in exp_pattern.finditer(content):
        experiences.append({
            "organization": m.group(1).strip().rstrip("*"),
            "dates": m.group(2).strip(),
        })

    # Fallback: match bold lines that look like company + date
    if not experiences:
        for line in content.splitlines():
            org_match = re.match(
                r"\*\*(.+?)\*\*.*?(\w+\s+\d{4}\s*[-–—]\s*(?:\w+\s+\d{4}|Current))",
                line,
            )
            if org_match:
                experiences.append({
                    "organization": org_match.group(1).strip(),
                    "dates": org_match.group(2).strip(),
                })

    # --- Skills ---
    skills: list[str] = []
    skills_match = re.search(
        r"\*\*Skills\*\*.*?\n(.+?)(?:\n\n|\n\[|\Z)",
        content,
        re.DOTALL | re.IGNORECASE,
    )
    if skills_match:
        raw = skills_match.group(1).strip()
        skills = [s.strip() for s in re.split(r"[|,]", raw) if s.strip()]
    # Fallback: look for a skills line
    if not skills:
        for line in content.splitlines():
            if "Skills" in line and "|" in line:
                skills = [s.strip() for s in line.split("|") if s.strip() and "Skills" not in s]
                break

    # --- Publications count ---
    pub_section = re.search(
        r"Publications?\s*(?:&|and)?\s*Research.*?\n(.*?)(?=\n\*\*(?:Extracurricular|Projects|Awards)|\Z)",
        content,
        re.DOTALL | re.IGNORECASE,
    )
    pub_count = 0
    if pub_section:
        # Count distinct publication entries (lines starting with bold author/title)
        pub_count = len(re.findall(
            r"(?:Co-Author|Lead-Author|Author)",
            pub_section.group(1),
            re.IGNORECASE,
        ))

    # --- Awards ---
    awards: list[dict[str, str]] = []
    awards_section = re.search(
        r"\*\*Awards\*\*.*?\n(.*?)(?=\n\*\*Scholarships|\Z)",
        content,
        re.DOTALL | re.IGNORECASE,
    )
    if awards_section:
        for m in re.finditer(r"•\s*\*\*(.+?)\*\*\s*\*?\((\d{4})\)\*?", awards_section.group(1)):
            awards.append({"title": m.group(1).strip(), "year": m.group(2)})

    # --- Scholarships ---
    scholarships: list[dict[str, str]] = []
    schol_section = re.search(
        r"Scholarships?\s*(?:&|and)?\s*Grants.*?\n(.*?)(?=\n\*\*Skills|\Z)",
        content,
        re.DOTALL | re.IGNORECASE,
    )
    if schol_section:
        for m in re.finditer(r"•\s*\*\*(.+?)\*\*\s*\*?\((\d{4})\)\*?", schol_section.group(1)):
            scholarships.append({"title": m.group(1).strip(), "year": m.group(2)})

    return {
        "quantifications": quantifications,
        "experiences": experiences,
        "skills": skills,
        "publications_count": pub_count,
        "awards": awards,
        "scholarships": scholarships,
    }


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
