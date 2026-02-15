"""Rewind Protocol Specification — defines valid message interactions.

Modeled after:
- https://github.com/fetchai/uAgents/blob/main/python/uagents-core/uagents_core/contrib/protocols/chat/__init__.py
- https://github.com/fetchai/uAgents/blob/main/python/uagents-core/uagents_core/contrib/protocols/payment/__init__.py
"""

from uagents_core.protocol import ProtocolSpecification

from .models import (
    ContextChangeEvent,
    DelegationTask,
    DisruptionEvent,
    EnergyLevel,
    EnergyLevelRequest,
    SwapOperation,
    TaskCompletion,
    UpdatedSchedule,
    UserProfile,
    UserProfileRequest,
)


# ─── Main Rewind Protocol ───
# Defines all valid message interactions between Rewind agents
rewind_protocol_spec = ProtocolSpecification(
    name="RewindLifeScheduler",
    version="1.0.0",
    interactions={
        # Context Sentinel → Disruption Detector
        ContextChangeEvent: {DisruptionEvent},

        # Disruption Detector → Scheduler Kernel
        DisruptionEvent: {UpdatedSchedule, SwapOperation},

        # Profiler request/response
        UserProfileRequest: {UserProfile},
        UserProfile: set(),

        # Energy request/response
        EnergyLevelRequest: {EnergyLevel},
        EnergyLevel: set(),

        # Scheduler Kernel → GhostWorker → Kernel
        DelegationTask: {TaskCompletion},
        TaskCompletion: set(),

        # Outputs (terminal)
        UpdatedSchedule: set(),
        SwapOperation: set(),
    },
    roles={
        "sentinel": {ContextChangeEvent},
        "detector": {DisruptionEvent},
        "profiler": {UserProfileRequest},
        "kernel": {DisruptionEvent, UserProfileRequest, EnergyLevelRequest, DelegationTask},
        "ghostworker": {DelegationTask},
        "energy_monitor": {EnergyLevelRequest},
    },
)