from dataclasses import dataclass
from typing import List, Tuple

try:
    from src.data_pipeline.signals import ExplicitSignal, ImplicitSignal
except Exception:  # allow fallback when pandas or other deps missing
    @dataclass
    class ExplicitSignal:
        source: str = ''
        category: str = ''
        text: str = ''
        metadata: dict = None

    @dataclass
    class ImplicitSignal:
        source: str = ''
        pattern_type: str = ''
        description: str = ''
        metadata: dict = None


@dataclass
class GoalDescriptor:
    name: str
    horizon_years: float
    idea_confidence: float  # 0.0-1.0 idea clarity
    timeframe: str  # 'long', 'medium', 'short'
    priority: str  # e.g., 'career', 'finance', 'family'


def milestone_count(goal: GoalDescriptor) -> int:
    if goal.timeframe == 'short':
        return max(2, int(goal.horizon_years * 4))
    if goal.timeframe == 'medium':
        return max(3, int(goal.horizon_years * 2))
    return max(4, int(goal.horizon_years * 1.5) + 1)


def _signal_support_ratio(goal: GoalDescriptor, explicit: List[ExplicitSignal]) -> float:
    matches = sum(1 for signal in explicit if goal.name.lower() in signal.text.lower())
    return min(1.0, matches * 0.25)


def plan_goal_steps(
    goal: GoalDescriptor,
    explicit: List[ExplicitSignal],
    implicit: List[ImplicitSignal],
) -> Tuple[List[str], float]:
    steps = []
    base_steps = milestone_count(goal)

    if goal.timeframe == 'long':
        steps.append('Research the landscape (institutions, visa, funding).')
        steps.append('Build a living-in-SF hypothesis board: housing, cashflow, network.')
        if goal.idea_confidence < 0.3:
            steps.append('Experiment with exploratory visits or mentorship to validate the target.')
    elif goal.timeframe == 'medium':
        steps.append('Break down the $15k target into weekly savings milestones.')
        steps.append('Automate tracking using the Composio Google Sheet watcher.')
        steps.append('Flag a monthly review to celebrate progress and adjust categories.')
    elif goal.timeframe == 'short':
        steps.append('List the exact amounts due for tuition/credit card and payment deadlines.')
        steps.append('Schedule tasks in STS to pay the bills at least one week early.')
    else:
        steps.append('Define the critical first milestone and the signal that confirms momentum.')

    while len(steps) < base_steps:
        steps.append('Deepen the signal set: journal reflections and log progress in Flatnotes.')

    readiness = min(1.0, goal.idea_confidence + _signal_support_ratio(goal, explicit))
    energy_bumps = sum(0.05 for signal in implicit if signal.pattern_type in ('working_style', 'peak_hours'))
    readiness = min(1.0, readiness + energy_bumps)

    return steps, readiness
