"""Comprehensive tests for the Profiler Agent.

Calibrated against exclusive reference personas:

    Profile              | Archetype           | X (Exec) | Y (Growth)
    Sam Altman / Zuck    | Compounding Builder | 0.95     | 0.93
    Steady Builder       | Reliable Operator   | 0.86     | 0.36
    Sporadic Sprinter    | Emerging Talent     | 0.38     | 0.83
    Stuck Dreamer        | At Risk             | 0.14     | 0.20

The bar is set HIGH. The default is At Risk. No participation trophies.
"""

from __future__ import annotations

import json
import statistics
from pathlib import Path
from typing import Any

import pytest


# ═══════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════

@pytest.fixture
def sample_daily_goals_dir(tmp_path: Path) -> Path:
    """Create a temporary directory with sample daily goal markdown files."""
    d = tmp_path / "daily_goals"
    d.mkdir()

    (d / "001.md").write_text(
        "- [x] finish project report\n"
        "- [x] send email to professor\n"
        "- [x] gym session\n"
        "- [ ] review algorithms chapter\n"
        "\n"
        "Good day overall, felt productive and focused.\n"
    )

    (d / "002.md").write_text(
        "- [ ] geology assignment\n"
        "- [ ] pay taxes\n"
        "- [x] X post\n"
        "- [ ] review and plan ebay work\n"
        "\n"
        "Wasted time, got distracted, low effort.\n"
    )

    (d / "003.md").write_text(
        "- [x] THRC work -> phase 2 complete\n"
        "- [x] Python toolbox.py file\n"
        "- [x] Continue with algorithm analysis book -> chapter 2\n"
        "- [x] send tanya email\n"
        "- [x] submit the evalai dataset\n"
    )

    (d / "004.md").write_text(
        "- [x] meet blessing\n"
        "- [x] ebay ML challenge continue -> did some but just did sth else\n"
        "- [x] communicate with Dr. Ekren\n"
        "- [ ] do DD for NUAI, BURU\n"
        "- [ ] continue algorithm practice\n"
        "\n"
        "Didn't drink water, too comfortable, wasted time.\n"
    )

    (d / "005.md").write_text(
        "- [ ] geology assignment\n"
        "- [ ] pay taxes\n"
        "- [ ] open DAO LLC\n"
    )

    return d


@pytest.fixture
def sample_reflections_dir(tmp_path: Path) -> Path:
    d = tmp_path / "reflections"
    d.mkdir()
    (d / "reflection_1.md").write_text(
        "## (1) Continue Doing\n"
        "- **Deep LLM Research**: Sustaining exploration of transformer architectures\n"
        "- **Daily Output**: Consistent shipping of tangible artifacts\n"
        "\n"
        "## (2) Stop Doing\n"
        "- **Demo-Driven Development**: Eliminate superficial task engagement\n"
        "- **Excessive Context Switching**: Focus on sustained deep work\n"
        "\n"
        "## (3) Start Doing\n"
        "- **System Robustness**: Implement stress testing\n"
        "\n"
        "## Successfully Mitigated\n"
        "- **AI Technical Debt**: Actively minimizing blind abstraction usage\n"
        "- **Fundamentals Grounding**: Maintaining core engineering principles\n"
        "\n"
        "## Requires Further Development\n"
        "- **Testing Competency**: Limited hands-on testing experience\n"
    )
    (d / "goals_1.md").write_text(
        "### 1. What would you like to learn during this internship?\n"
        "- **Scalable Systems**: How to build reliable systems\n"
        "- **Team Dynamics**: Working effectively within a team\n"
    )
    return d


@pytest.fixture
def sample_resume_file(tmp_path: Path) -> Path:
    f = tmp_path / "resume.md"
    f.write_text(
        "# John Doe\n\n"
        "**Professional Experience**\n"
        "**Google August 2023 - Current**\n"
        "**Software Engineer**\n"
        "• Built a system processing 2,454 academic papers\n"
        "• Reduced data processing time by 40%\n"
        "• Delivered the project 200% under budget\n\n"
        "**Publications & Research**\n"
        "**Lead-Author**, \"QuantaFold\"\n"
        "• Achieved 78% training time reduction\n"
        "**Co-Author**, \"Rural Healthcare Access\"\n"
        "• Silhouette Score: 0.93\n\n"
        "**Awards**\n"
        "• **NVIDIA Hackathon Winner** *(2025)*\n"
        "• **TXST Datathon 1st Place** *(2025)*\n\n"
        "**Scholarships & Grants**\n"
        "• **Merit Scholar** *(2023)*\n"
        "• **Launch Scholar** *(2024)*\n\n"
        "**Skills**\n"
        "Python | JavaScript | React | SQL | Terraform\n"
    )
    return f


# ── Reference persona fixtures for exclusive calibration ──

def _make_daily_goals(rate, count: int = 14, tasks_per_day: int = 5) -> list[dict]:
    """Generate daily goal entries.

    Parameters
    ----------
    rate : float or list[float]
        If a single float, every day gets the same completion rate.
        If a list, each element is the per-day rate (``count`` is ignored).
    count : int
        Number of days when *rate* is a scalar.
    tasks_per_day : int
        Tasks generated per day.
    """
    if isinstance(rate, (list, tuple)):
        rates = list(rate)
    else:
        rates = [rate] * count

    entries: list[dict] = []
    for d, r in enumerate(rates):
        completed = round(tasks_per_day * r)
        tasks = (
            [{"text": f"task_{i}", "completed": True, "note": "", "category": "professional"}
             for i in range(completed)]
            + [{"text": f"task_{i}", "completed": False, "note": "", "category": "professional"}
               for i in range(completed, tasks_per_day)]
        )
        entries.append({
            "day_id": f"{d:03d}",
            "tasks": list(tasks),
            "total_tasks": tasks_per_day,
            "completed_count": completed,
            "completion_rate": r,
            "category_distribution": {"professional": tasks_per_day},
            "reflection_text": "",
            "reflection_sentiment": "neutral",
            "reflection_sentiment_score": 0.0,
            "has_reflection": False,
        })
    return entries


@pytest.fixture
def altman_zuck_persona() -> dict:
    """Sam Altman / Zuck: Compounding Builder (X=0.95, Y=0.93)."""
    return {
        "traits": {
            "execution_rate": 0.97,
            "completion_consistency": 0.95,
            "growth_velocity": 0.92,
            "self_awareness": 0.95,
            "ambition_calibration": 0.90,
            "recovery_speed": 0.95,
        },
        "profile": {"adherence_score": 0.96, "estimation_bias": 1.05},
        "sentiment": {"avg_score": 0.45},
        "engagement_growth": 0.40,
    }


@pytest.fixture
def reliable_operator_persona() -> dict:
    """Steady Builder: Reliable Operator (X=0.86, Y=0.36)."""
    return {
        "traits": {
            "execution_rate": 0.90,
            "completion_consistency": 0.85,
            "growth_velocity": 0.35,
            "self_awareness": 0.30,
            "ambition_calibration": 0.40,
            "recovery_speed": 0.40,
        },
        "profile": {"adherence_score": 0.88, "estimation_bias": 1.10},
        "sentiment": {"avg_score": 0.0},
        "engagement_growth": -0.10,
    }


@pytest.fixture
def emerging_talent_persona() -> dict:
    """Sporadic Sprinter: Emerging Talent (X=0.38, Y=0.83)."""
    return {
        "traits": {
            "execution_rate": 0.35,
            "completion_consistency": 0.30,
            "growth_velocity": 0.90,
            "self_awareness": 0.85,
            "ambition_calibration": 0.80,
            "recovery_speed": 0.80,
        },
        "profile": {"adherence_score": 0.30, "estimation_bias": 1.50},
        "sentiment": {"avg_score": 0.25},
        "engagement_growth": 0.20,
    }


@pytest.fixture
def stuck_dreamer_persona() -> dict:
    """Stuck Dreamer: At Risk (X=0.14, Y=0.20)."""
    return {
        "traits": {
            "execution_rate": 0.10,
            "completion_consistency": 0.10,
            "growth_velocity": 0.20,
            "self_awareness": 0.15,
            "ambition_calibration": 0.10,
            "recovery_speed": 0.10,
        },
        "profile": {"adherence_score": 0.10, "estimation_bias": 2.0},
        "sentiment": {"avg_score": -0.25},
        "engagement_growth": -0.20,
    }


@pytest.fixture
def daily_goal_entries() -> list[dict[str, Any]]:
    """Pre-parsed daily goal entries (mixed signal — should be At Risk by default)."""
    return [
        {
            "day_id": "001",
            "tasks": [
                {"text": "finish project", "completed": True, "note": "", "category": "professional"},
                {"text": "send email", "completed": True, "note": "", "category": "professional"},
                {"text": "gym session", "completed": True, "note": "", "category": "personal"},
                {"text": "review algorithms", "completed": False, "note": "", "category": "academic"},
            ],
            "total_tasks": 4, "completed_count": 3, "completion_rate": 0.75,
            "category_distribution": {"professional": 2, "personal": 1, "academic": 1},
            "reflection_text": "Good day overall, felt productive.",
            "reflection_sentiment": "positive", "reflection_sentiment_score": 0.5,
            "has_reflection": True,
        },
        {
            "day_id": "002",
            "tasks": [
                {"text": "geology assignment", "completed": False, "note": "", "category": "academic"},
                {"text": "pay taxes", "completed": False, "note": "", "category": "personal"},
                {"text": "X post", "completed": True, "note": "", "category": "professional"},
                {"text": "review ebay work", "completed": False, "note": "", "category": "professional"},
            ],
            "total_tasks": 4, "completed_count": 1, "completion_rate": 0.25,
            "category_distribution": {"academic": 1, "personal": 1, "professional": 2},
            "reflection_text": "Wasted time, got distracted.",
            "reflection_sentiment": "negative", "reflection_sentiment_score": -0.5,
            "has_reflection": True,
        },
        {
            "day_id": "003",
            "tasks": [
                {"text": "THRC work", "completed": True, "note": "phase 2 complete", "category": "professional"},
                {"text": "Python toolbox", "completed": True, "note": "", "category": "academic"},
                {"text": "algorithm book", "completed": True, "note": "chapter 2", "category": "academic"},
                {"text": "send email", "completed": True, "note": "", "category": "professional"},
                {"text": "submit dataset", "completed": True, "note": "", "category": "professional"},
            ],
            "total_tasks": 5, "completed_count": 5, "completion_rate": 1.0,
            "category_distribution": {"professional": 3, "academic": 2},
            "reflection_text": "", "reflection_sentiment": "neutral",
            "reflection_sentiment_score": 0.0, "has_reflection": False,
        },
        {
            "day_id": "004",
            "tasks": [
                {"text": "meet blessing", "completed": True, "note": "", "category": "social"},
                {"text": "ebay ML challenge", "completed": True, "note": "did some", "category": "professional"},
                {"text": "communicate Dr. Ekren", "completed": True, "note": "", "category": "academic"},
                {"text": "do DD for NUAI", "completed": False, "note": "", "category": "professional"},
                {"text": "algorithm practice", "completed": False, "note": "", "category": "academic"},
            ],
            "total_tasks": 5, "completed_count": 3, "completion_rate": 0.6,
            "category_distribution": {"social": 1, "professional": 2, "academic": 2},
            "reflection_text": "Too comfortable, wasted time.",
            "reflection_sentiment": "negative", "reflection_sentiment_score": -0.333,
            "has_reflection": True,
        },
    ]


# ═══════════════════════════════════════════════════════════════════════════
# Tests: Daily Goals Parser
# ═══════════════════════════════════════════════════════════════════════════

class TestParseDailyGoals:
    def test_parses_all_files(self, sample_daily_goals_dir):
        from src.data_pipeline.parsers import parse_daily_goals
        entries = parse_daily_goals(sample_daily_goals_dir)
        assert len(entries) == 5

    def test_completion_rate(self, sample_daily_goals_dir):
        from src.data_pipeline.parsers import parse_daily_goals
        entries = parse_daily_goals(sample_daily_goals_dir)
        day1 = next(e for e in entries if e["day_id"] == "001")
        assert day1["completion_rate"] == 0.75

    def test_perfect_completion(self, sample_daily_goals_dir):
        from src.data_pipeline.parsers import parse_daily_goals
        entries = parse_daily_goals(sample_daily_goals_dir)
        day3 = next(e for e in entries if e["day_id"] == "003")
        assert day3["completion_rate"] == 1.0

    def test_zero_completion(self, sample_daily_goals_dir):
        from src.data_pipeline.parsers import parse_daily_goals
        entries = parse_daily_goals(sample_daily_goals_dir)
        day5 = next(e for e in entries if e["day_id"] == "005")
        assert day5["completion_rate"] == 0.0

    def test_annotation_parsing(self, sample_daily_goals_dir):
        from src.data_pipeline.parsers import parse_daily_goals
        entries = parse_daily_goals(sample_daily_goals_dir)
        day3 = next(e for e in entries if e["day_id"] == "003")
        annotated = [t for t in day3["tasks"] if t["note"]]
        assert len(annotated) >= 1
        assert "phase 2 complete" in annotated[0]["note"]

    def test_reflection_extraction(self, sample_daily_goals_dir):
        from src.data_pipeline.parsers import parse_daily_goals
        entries = parse_daily_goals(sample_daily_goals_dir)
        day1 = next(e for e in entries if e["day_id"] == "001")
        assert day1["has_reflection"] is True
        assert "productive" in day1["reflection_text"]

    def test_negative_sentiment(self, sample_daily_goals_dir):
        from src.data_pipeline.parsers import parse_daily_goals
        entries = parse_daily_goals(sample_daily_goals_dir)
        day2 = next(e for e in entries if e["day_id"] == "002")
        assert day2["reflection_sentiment"] == "negative"
        assert day2["reflection_sentiment_score"] < 0

    def test_empty_directory(self, tmp_path):
        from src.data_pipeline.parsers import parse_daily_goals
        d = tmp_path / "empty"
        d.mkdir()
        assert parse_daily_goals(d) == []


# ═══════════════════════════════════════════════════════════════════════════
# Tests: Reflections Parser
# ═══════════════════════════════════════════════════════════════════════════

class TestParseReflections:
    def test_parses_documents(self, sample_reflections_dir):
        from src.data_pipeline.parsers import parse_reflections
        data = parse_reflections(sample_reflections_dir)
        assert len(data["documents"]) == 2

    def test_growth_indicators(self, sample_reflections_dir):
        from src.data_pipeline.parsers import parse_reflections
        data = parse_reflections(sample_reflections_dir)
        gi = data["growth_indicators"]
        assert gi["continue_count"] == 2
        assert gi["stop_count"] == 2
        assert gi["start_count"] == 1
        assert gi["mitigated_count"] == 2
        assert gi["needs_development_count"] == 1

    def test_self_awareness_score(self, sample_reflections_dir):
        from src.data_pipeline.parsers import parse_reflections
        data = parse_reflections(sample_reflections_dir)
        score = data["growth_indicators"]["self_awareness_score"]
        assert 0.0 <= score <= 1.0
        assert score > 0.5

    def test_growth_velocity(self, sample_reflections_dir):
        from src.data_pipeline.parsers import parse_reflections
        data = parse_reflections(sample_reflections_dir)
        velocity = data["growth_indicators"]["growth_velocity"]
        assert abs(velocity - 0.6667) < 0.01


# ═══════════════════════════════════════════════════════════════════════════
# Tests: Resume Parser
# ═══════════════════════════════════════════════════════════════════════════

class TestParseResume:
    def test_quantifications(self, sample_resume_file):
        from src.data_pipeline.parsers import parse_resume
        data = parse_resume(sample_resume_file)
        assert len(data["quantifications"]) > 0
        values = [q["value"] for q in data["quantifications"]]
        assert any("40" in v for v in values)

    def test_publications_count(self, sample_resume_file):
        from src.data_pipeline.parsers import parse_resume
        data = parse_resume(sample_resume_file)
        assert data["publications_count"] == 2

    def test_awards(self, sample_resume_file):
        from src.data_pipeline.parsers import parse_resume
        data = parse_resume(sample_resume_file)
        assert len(data["awards"]) == 2

    def test_scholarships(self, sample_resume_file):
        from src.data_pipeline.parsers import parse_resume
        data = parse_resume(sample_resume_file)
        assert len(data["scholarships"]) == 2

    def test_skills(self, sample_resume_file):
        from src.data_pipeline.parsers import parse_resume
        data = parse_resume(sample_resume_file)
        assert "Python" in data["skills"]
        assert "React" in data["skills"]

    def test_missing_file(self, tmp_path):
        from src.data_pipeline.parsers import parse_resume
        data = parse_resume(tmp_path / "nonexistent.md")
        assert data["quantifications"] == []


# ═══════════════════════════════════════════════════════════════════════════
# Tests: Pattern Engine
# ═══════════════════════════════════════════════════════════════════════════

class TestPatternEngine:
    def test_decay_weight(self):
        from src.agents.profiler_agent import PatternEngine
        engine = PatternEngine(decay_factor=0.85)
        assert engine._decay_weight(0) == 1.0
        assert abs(engine._decay_weight(1) - 0.85) < 0.001
        assert abs(engine._decay_weight(2) - 0.7225) < 0.001

    def test_apply_decay_recent_weighted_higher(self):
        from src.agents.profiler_agent import PatternEngine
        engine = PatternEngine(decay_factor=0.85)
        result = engine._apply_decay([0.2, 0.2, 0.2, 0.8, 0.8])
        uniform_mean = sum([0.2, 0.2, 0.2, 0.8, 0.8]) / 5
        assert result > uniform_mean  # recency bias pulls toward 0.8

    def test_peak_hours_with_social_data(self, daily_goal_entries):
        from src.agents.profiler_agent import PatternEngine
        engine = PatternEngine()
        engine.load_signals(
            daily_goals=daily_goal_entries,
            social_posting_hours={"linkedin": [9, 10, 14], "twitter": [10, 15, 16]},
        )
        peaks = engine.compute_peak_hours()
        assert isinstance(peaks, list)
        assert len(peaks) <= 4
        assert all(0 <= h <= 23 for h in peaks)

    def test_estimation_bias_default(self):
        from src.agents.profiler_agent import PatternEngine
        engine = PatternEngine()
        engine.load_signals()
        assert engine.compute_estimation_bias() == 1.2

    def test_estimation_bias_with_data(self):
        from src.agents.profiler_agent import PatternEngine
        engine = PatternEngine()
        engine.load_signals(task_completions=[
            {"estimated_minutes": 30, "actual_minutes": 45},
            {"estimated_minutes": 60, "actual_minutes": 50},
            {"estimated_minutes": 20, "actual_minutes": 30},
        ])
        assert engine.compute_estimation_bias() > 1.0

    def test_adherence_score(self, daily_goal_entries):
        from src.agents.profiler_agent import PatternEngine
        engine = PatternEngine()
        engine.load_signals(daily_goals=daily_goal_entries)
        adherence = engine.compute_adherence_score()
        assert 0.0 <= adherence <= 1.0

    def test_drift_direction(self, daily_goal_entries):
        from src.agents.profiler_agent import PatternEngine
        engine = PatternEngine()
        engine.load_signals(daily_goals=daily_goal_entries)
        assert engine.compute_drift_direction() in ("evening_fade", "distraction", "balanced")

    def test_energy_curve_shape(self, daily_goal_entries):
        from src.agents.profiler_agent import PatternEngine
        engine = PatternEngine()
        engine.load_signals(daily_goals=daily_goal_entries, social_posting_hours={"linkedin": [9, 10]})
        curve = engine.compute_energy_curve()
        assert len(curve) == 24
        assert all(1 <= v <= 5 for v in curve)

    def test_full_profile_keys(self, daily_goal_entries):
        from src.agents.profiler_agent import PatternEngine
        engine = PatternEngine()
        engine.load_signals(
            daily_goals=daily_goal_entries,
            social_posting_hours={"linkedin": [9, 14], "twitter": [10, 15]},
        )
        profile = engine.compute_profile()
        for key in ("peak_hours", "energy_curve", "adherence_score",
                     "estimation_bias", "automation_comfort",
                     "distraction_patterns", "disruption_recovery"):
            assert key in profile


# ═══════════════════════════════════════════════════════════════════════════
# Tests: Sentiment Analyzer
# ═══════════════════════════════════════════════════════════════════════════

class TestSentimentAnalyzer:
    def test_positive_text(self):
        from src.agents.profiler_agent import SentimentAnalyzer
        sa = SentimentAnalyzer()
        result = sa.analyze("Great day, felt productive and motivated!")
        assert result["label"] == "positive"
        assert result["score"] > 0

    def test_negative_text(self):
        from src.agents.profiler_agent import SentimentAnalyzer
        sa = SentimentAnalyzer()
        result = sa.analyze("Wasted time, got distracted, lazy and stressed.")
        assert result["label"] == "negative"
        assert result["score"] < 0

    def test_neutral_text(self):
        from src.agents.profiler_agent import SentimentAnalyzer
        sa = SentimentAnalyzer()
        assert sa.analyze("Completed the task, moved to next one.")["label"] == "neutral"

    def test_empty_text(self):
        from src.agents.profiler_agent import SentimentAnalyzer
        sa = SentimentAnalyzer()
        assert sa.analyze("")["score"] == 0.0

    def test_trend_analysis(self):
        from src.agents.profiler_agent import SentimentAnalyzer
        sa = SentimentAnalyzer()
        texts = [
            "Terrible day, wasted time, stressed and overwhelmed.",
            "Bad day, distracted and frustrated.",
            "Ok day, some progress made.",
            "Good day, feeling productive and motivated.",
            "Great day, accomplished everything, very proud!",
        ]
        assert sa.analyze_trend(texts)["trend"] == "improving"


# ═══════════════════════════════════════════════════════════════════════════
# Tests: Grouping Function — Exclusive Calibration
# ═══════════════════════════════════════════════════════════════════════════

class TestGroupingFunction:
    """The grouping function must be EXCLUSIVE.

    Compounding Builder requires elite execution AND growth.
    Reliable Operator requires strong execution with stagnant growth.
    Emerging Talent requires weak execution with elite growth.
    Everything else is At Risk — the default.
    """

    def test_compounding_builder_requires_elite_on_both_axes(self):
        """Only Sam Altman / Zuck tier gets Compounding Builder.

        The data must show BOTH high execution AND a clear upward slope.
        A constant 0.95 flat-line does NOT qualify because it demonstrates
        zero growth velocity.  The rates below ramp from 0.80 → 1.0,
        proving consistent shipping *and* compounding improvement.
        """
        from src.agents.profiler_agent import GroupingFunction
        gf = GroupingFunction()

        # 14 days of steadily IMPROVING elite performance (0.80 → 1.0)
        improving_rates = [
            0.80, 0.82, 0.85, 0.87, 0.90, 0.92, 0.95,
            0.95, 0.97, 0.97, 1.00, 1.00, 1.00, 1.00,
        ]
        goals = _make_daily_goals(rate=improving_rates)
        reflection = {"growth_indicators": {"self_awareness_score": 0.9}}

        result = gf.classify(goals, reflection, {})
        assert result["archetype"] == "compounding_builder", (
            f"Expected compounding_builder, got {result['archetype']} "
            f"(exec={result['execution_composite']:.3f}, "
            f"growth={result['growth_composite']:.3f})"
        )
        assert result["execution_composite"] >= 0.85
        assert result["growth_composite"] >= 0.80

    def test_reliable_operator_ships_but_stagnant(self):
        """High execution, low growth = Reliable Operator.

        Constant 0.85 completion with near-zero self-awareness.
        The sigmoid normalization crushes the low self_awareness toward 0,
        keeping growth_composite < 0.50 while execution stays high.
        """
        from src.agents.profiler_agent import GroupingFunction
        gf = GroupingFunction()

        # Ships at a solid 85% every single day — but zero slope, zero depth
        goals = _make_daily_goals(rate=0.85, count=14)
        reflection = {"growth_indicators": {"self_awareness_score": 0.1}}

        result = gf.classify(goals, reflection, {})
        assert result["archetype"] == "reliable_operator", (
            f"Expected reliable_operator, got {result['archetype']} "
            f"(exec={result['execution_composite']:.3f}, "
            f"growth={result['growth_composite']:.3f})"
        )
        assert result["execution_composite"] >= 0.70
        assert result["growth_composite"] < 0.50

    def test_emerging_talent_learning_fast_but_not_shipping(self):
        """Low execution, high growth = Emerging Talent.

        Volatile, low-output person showing dramatic improvement.
        The improvement slope must be steep enough that sigmoid-normalized
        growth_velocity reaches near-ceiling, compensating for the crushed
        execution dimensions.
        """
        from src.agents.profiler_agent import GroupingFunction
        gf = GroupingFunction()

        # Very low start, volatile, but steep upward trajectory
        improving_rates = [
            0.05, 0.10, 0.05, 0.20, 0.10, 0.30, 0.15,
            0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70,
        ]
        goals = _make_daily_goals(rate=improving_rates)
        reflection = {"growth_indicators": {"self_awareness_score": 0.95}}

        result = gf.classify(goals, reflection, {})
        assert result["archetype"] == "emerging_talent", (
            f"Expected emerging_talent, got {result['archetype']} "
            f"(exec={result['execution_composite']:.3f}, "
            f"growth={result['growth_composite']:.3f})"
        )
        assert result["execution_composite"] < 0.50
        assert result["growth_composite"] >= 0.65

    def test_mixed_signal_defaults_to_at_risk(self, daily_goal_entries):
        """Volatile, mixed data = At Risk. No participation trophies."""
        from src.agents.profiler_agent import GroupingFunction
        gf = GroupingFunction()

        result = gf.classify(
            daily_goal_entries,
            {"growth_indicators": {"self_awareness_score": 0.4}},
            {},
        )
        assert result["archetype"] == "at_risk"

    def test_mediocre_performer_is_at_risk(self):
        """50% completion with mediocre growth is NOT enough to escape At Risk."""
        from src.agents.profiler_agent import GroupingFunction
        gf = GroupingFunction()

        goals = _make_daily_goals(rate=0.50, count=14)
        reflection = {"growth_indicators": {"self_awareness_score": 0.4, "growth_velocity": 0.4}}

        result = gf.classify(goals, reflection, {})
        assert result["archetype"] == "at_risk"

    def test_vectors_all_in_range(self, daily_goal_entries):
        from src.agents.profiler_agent import GroupingFunction
        gf = GroupingFunction()
        vectors = gf.compute_vectors(
            daily_goal_entries,
            {"growth_indicators": {"self_awareness_score": 0.5}},
            {},
        )
        for key, val in vectors.items():
            assert 0.0 <= val <= 1.0, f"{key}={val} out of range"

    def test_confidence_requires_data(self):
        """< 10 days of data should reduce confidence."""
        from src.agents.profiler_agent import GroupingFunction
        gf = GroupingFunction()

        few_days = _make_daily_goals(rate=0.95, count=3)
        result = gf.classify(few_days, {"growth_indicators": {}}, {})
        assert result["confidence"] < 1.0  # 3/10 = 0.3


# ═══════════════════════════════════════════════════════════════════════════
# Tests: Success Function — Reference Persona Calibration
# ═══════════════════════════════════════════════════════════════════════════

class TestSuccessFunction:
    """Each test models a real-world reference persona and verifies
    the success function places them in the correct quadrant at
    approximately the correct coordinates."""

    def test_altman_zuck_compounding_builder(self, altman_zuck_persona):
        """Sam Altman / Zuck tier: X~0.95, Y~0.93 -> Compounding Builder."""
        from src.agents.profiler_agent import SuccessFunction
        sf = SuccessFunction()
        p = altman_zuck_persona

        result = sf.compute(
            p["profile"], {"traits": p["traits"]},
            p["sentiment"], p["engagement_growth"],
        )
        assert result["quadrant"] == "compounding_builder"
        assert result["execution_velocity"] >= 0.90
        assert result["growth_trajectory"] >= 0.85

    def test_reliable_operator_ships_but_plateaus(self, reliable_operator_persona):
        """Steady Builder: X~0.86, Y~0.36 -> Reliable Operator."""
        from src.agents.profiler_agent import SuccessFunction
        sf = SuccessFunction()
        p = reliable_operator_persona

        result = sf.compute(
            p["profile"], {"traits": p["traits"]},
            p["sentiment"], p["engagement_growth"],
        )
        assert result["quadrant"] == "reliable_operator"
        assert result["execution_velocity"] >= 0.70
        assert result["growth_trajectory"] < 0.50

    def test_emerging_talent_raw_potential(self, emerging_talent_persona):
        """Sporadic Sprinter: X~0.38, Y~0.83 -> Emerging Talent."""
        from src.agents.profiler_agent import SuccessFunction
        sf = SuccessFunction()
        p = emerging_talent_persona

        result = sf.compute(
            p["profile"], {"traits": p["traits"]},
            p["sentiment"], p["engagement_growth"],
        )
        assert result["quadrant"] == "emerging_talent"
        assert result["execution_velocity"] < 0.50
        assert result["growth_trajectory"] >= 0.65

    def test_stuck_dreamer_at_risk(self, stuck_dreamer_persona):
        """Stuck Dreamer: X~0.14, Y~0.20 -> At Risk."""
        from src.agents.profiler_agent import SuccessFunction
        sf = SuccessFunction()
        p = stuck_dreamer_persona

        result = sf.compute(
            p["profile"], {"traits": p["traits"]},
            p["sentiment"], p["engagement_growth"],
        )
        assert result["quadrant"] == "at_risk"
        assert result["execution_velocity"] < 0.30
        assert result["growth_trajectory"] < 0.30

    def test_no_mans_land_falls_to_at_risk(self):
        """Moderate on both axes but not clearing any threshold = At Risk."""
        from src.agents.profiler_agent import SuccessFunction
        sf = SuccessFunction()

        result = sf.compute(
            {"adherence_score": 0.55, "estimation_bias": 1.3},
            {"traits": {
                "execution_rate": 0.55, "completion_consistency": 0.55,
                "growth_velocity": 0.55, "self_awareness": 0.50,
                "ambition_calibration": 0.50, "recovery_speed": 0.50,
            }},
            {"avg_score": 0.0},
        )
        # Moderate values land in the dead zone between quadrants
        assert result["quadrant"] == "at_risk"

    def test_components_present(self, altman_zuck_persona):
        from src.agents.profiler_agent import SuccessFunction
        sf = SuccessFunction()
        p = altman_zuck_persona
        result = sf.compute(
            p["profile"], {"traits": p["traits"]}, p["sentiment"],
        )
        assert "components" in result
        assert "x" in result["components"]
        assert "y" in result["components"]
        assert "completion_rate" in result["components"]["x"]
        assert "learning_velocity" in result["components"]["y"]


# ═══════════════════════════════════════════════════════════════════════════
# Tests: Temporal Tracker
# ═══════════════════════════════════════════════════════════════════════════

class TestTemporalTracker:
    def test_add_snapshot(self):
        from src.agents.profiler_agent import TemporalTracker
        tt = TemporalTracker()
        tt.add_snapshot("2025-01-01", {"exec": 0.5, "growth": 0.6})
        assert len(tt.snapshots) == 1

    def test_no_drift_with_one_snapshot(self):
        from src.agents.profiler_agent import TemporalTracker
        tt = TemporalTracker()
        tt.add_snapshot("2025-01-01", {"exec": 0.5})
        assert tt.detect_drift() is None

    def test_drift_detected(self):
        from src.agents.profiler_agent import TemporalTracker
        tt = TemporalTracker(drift_threshold=0.15)
        tt.add_snapshot("2025-01-01", {"exec": 0.3, "growth": 0.4})
        tt.add_snapshot("2025-01-02", {"exec": 0.7, "growth": 0.4})
        drift = tt.detect_drift()
        assert drift is not None
        assert "exec" in drift["changed_fields"]
        assert drift["magnitude"] >= 0.15

    def test_no_drift_small_change(self):
        from src.agents.profiler_agent import TemporalTracker
        tt = TemporalTracker(drift_threshold=0.15)
        tt.add_snapshot("2025-01-01", {"exec": 0.5, "growth": 0.5})
        tt.add_snapshot("2025-01-02", {"exec": 0.55, "growth": 0.52})
        assert tt.detect_drift() is None

    def test_redis_serialization(self):
        from src.agents.profiler_agent import TemporalTracker
        tt = TemporalTracker()
        tt.add_snapshot("2025-01-01", {"exec": 0.5})
        tt.add_snapshot("2025-01-02", {"exec": 0.6})
        payload = tt.to_redis_payload()
        restored = TemporalTracker.from_redis_payload(payload)
        assert len(restored.snapshots) == 2
        assert restored.snapshots[0]["scores"]["exec"] == 0.5

    def test_get_trend(self):
        from src.agents.profiler_agent import TemporalTracker
        tt = TemporalTracker()
        for i in range(10):
            tt.add_snapshot(f"2025-01-{i+1:02d}", {"exec": 0.1 * (i + 1)})
        trend = tt.get_trend("exec", window=5)
        assert len(trend) == 5
        assert trend[-1] == 1.0


# ═══════════════════════════════════════════════════════════════════════════
# Tests: Decay Math
# ═══════════════════════════════════════════════════════════════════════════

class TestDecayMath:
    def test_decay_monotonically_decreasing(self):
        from src.agents.profiler_agent import PatternEngine
        engine = PatternEngine(decay_factor=0.85)
        weights = [engine._decay_weight(i) for i in range(10)]
        for i in range(1, len(weights)):
            assert weights[i] <= weights[i - 1]

    def test_decay_factor_one_is_no_decay(self):
        from src.agents.profiler_agent import PatternEngine
        engine = PatternEngine(decay_factor=1.0)
        values = [0.5, 0.6, 0.7]
        result = engine._apply_decay(values)
        expected = sum(values) / len(values)
        assert abs(result - expected) < 0.001

    def test_heavy_decay_favors_recent(self):
        from src.agents.profiler_agent import PatternEngine
        engine = PatternEngine(decay_factor=0.5)
        result = engine._apply_decay([0.0, 0.0, 0.0, 1.0])
        # With decay=0.5, the most recent value (1.0) has weight 1.0
        # while the oldest (0.0) has weight 0.125 — result should be > 0.5
        assert result > 0.5

    def test_negative_age_clamped(self):
        from src.agents.profiler_agent import PatternEngine
        engine = PatternEngine(decay_factor=0.85)
        assert engine._decay_weight(-5) == 1.0


# ═══════════════════════════════════════════════════════════════════════════
# Tests: Full ProfilerEngine Integration
# ═══════════════════════════════════════════════════════════════════════════

class TestProfilerEngine:
    def test_full_pipeline(self, daily_goal_entries):
        from src.agents.profiler_agent import ProfilerEngine

        engine = ProfilerEngine()
        result = engine.build_full_profile(
            daily_goals=daily_goal_entries,
            social_posting_hours={"linkedin": [9, 10, 14], "twitter": [10, 15]},
            reflection_data={"growth_indicators": {"self_awareness_score": 0.6}},
        )

        assert "user_profile" in result
        assert "grouping" in result
        assert "success_plot" in result
        assert "sentiment" in result

        profile = result["user_profile"]
        assert len(profile["peak_hours"]) <= 4
        assert len(profile["energy_curve"]) == 24
        assert 0.0 <= profile["adherence_score"] <= 1.0

        grouping = result["grouping"]
        assert grouping["archetype"] in (
            "compounding_builder", "reliable_operator",
            "emerging_talent", "at_risk",
        )

        success = result["success_plot"]
        assert 0.0 <= success["execution_velocity"] <= 1.0
        assert 0.0 <= success["growth_trajectory"] <= 1.0
        assert success["quadrant"] in (
            "compounding_builder", "emerging_talent",
            "reliable_operator", "at_risk",
        )

    def test_mixed_signal_data_is_at_risk(self, daily_goal_entries):
        """Real-world mixed signal data should NOT clear any elite threshold."""
        from src.agents.profiler_agent import ProfilerEngine
        engine = ProfilerEngine()
        result = engine.build_full_profile(
            daily_goals=daily_goal_entries,
            reflection_data={"growth_indicators": {"self_awareness_score": 0.4}},
        )
        # Mixed data = At Risk
        assert result["grouping"]["archetype"] == "at_risk"

    def test_empty_data_is_at_risk(self):
        """No data = At Risk by default. Cold start is conservative."""
        from src.agents.profiler_agent import ProfilerEngine
        engine = ProfilerEngine()
        result = engine.build_full_profile()
        assert result["grouping"]["archetype"] == "at_risk"

    def test_temporal_drift_on_second_run(self, daily_goal_entries):
        from src.agents.profiler_agent import ProfilerEngine
        engine = ProfilerEngine()
        engine.build_full_profile(daily_goals=daily_goal_entries)
        better_goals = [dict(e, completion_rate=0.95) for e in daily_goal_entries]
        result = engine.build_full_profile(daily_goals=better_goals)
        assert result["temporal_drift"] is None or isinstance(result["temporal_drift"], dict)
