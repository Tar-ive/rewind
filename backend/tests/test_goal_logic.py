import pytest
from src.goal_logic import GoalDescriptor, plan_goal_steps


class DummySignal:
    def __init__(self, pattern_type='generic', text=''):
        self.pattern_type = pattern_type
        self.text = text


ExplicitSignal = DummySignal
ImplicitSignal = DummySignal


def build_explicit(texts):
    return [ExplicitSignal(pattern_type='goal', text=text) for text in texts]


def build_implicit(types):
    return [ImplicitSignal(pattern_type=t) for t in types]


@pytest.mark.parametrize("goal,expected_readiness", [
    (GoalDescriptor('Move to SF', 2.0, 0.1, 'long', 'career'), pytest.approx(0.1, abs=0.05)),
    (GoalDescriptor('Support parents monthly', 0.2, 0.7, 'short', 'family'), pytest.approx(0.7, abs=0.05)),
])
def test_readiness_tracks_confidence(goal, expected_readiness):
    steps, readiness = plan_goal_steps(goal, [], [])
    assert len(steps) >= 2
    assert readiness == expected_readiness


def test_long_term_goal_includes_research_steps():
    goal = GoalDescriptor('Move to SF', 2.0, 0.1, 'long', 'career')
    steps, readiness = plan_goal_steps(goal, [], [])
    assert any('research' in step.lower() for step in steps)
    assert readiness <= 0.2


def test_medium_goal_builds_weekly_savings():
    goal = GoalDescriptor('Save 15k by semester', 0.5, 0.5, 'medium', 'finance')
    steps, _ = plan_goal_steps(goal, [], [])
    assert any('weekly' in step.lower() for step in steps)
    assert any('automate tracking' in step.lower() for step in steps)


def test_short_term_goal_prioritizes_payments():
    goal = GoalDescriptor('Pay credit card off', 0.1, 0.8, 'short', 'finance')
    steps, _ = plan_goal_steps(goal, [], [])
    assert steps[0].lower().startswith('list the exact amounts')


def test_profile_signals_boost_readiness():
    goal = GoalDescriptor('Support parents monthly', 0.2, 0.3, 'short', 'family')
    explicit = build_explicit(['Support parents monthly via cash transfers'])
    implicit = build_implicit(['working_style', 'peak_hours'])
    steps, readiness = plan_goal_steps(goal, explicit, implicit)
    assert readiness > 0.5


def test_low_confidence_long_term_with_signals():
    goal = GoalDescriptor('Go to Stanford grad school', 5.0, 0.0, 'long', 'education')
    explicit = build_explicit(['Goal: Go to Stanford grad school is a stretch target'])
    implicit = build_implicit(['engagement'])
    steps, readiness = plan_goal_steps(goal, explicit, implicit)
    assert len(steps) >= 4
    assert readiness > 0.0
