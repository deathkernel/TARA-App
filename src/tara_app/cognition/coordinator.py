"""Staged coordinator joining attention, memory context and decision policy."""
from __future__ import annotations
from collections.abc import Callable, Sequence
from .context import ContextBuilder
from .decision import DecisionEngine
from .models import ActionOption, CognitiveRequest, ContextItem, DecisionResult, ReasoningTrace

class CognitiveCoordinator:
    """Coordinate cognitive stages without executing tools or calling an LLM."""
    def __init__(self, context_builder: ContextBuilder, decision_engine: DecisionEngine | None = None, *, proposal_provider: Callable[[CognitiveRequest, tuple[ContextItem, ...]], Sequence[ActionOption]] | None = None) -> None:
        self.context_builder = context_builder
        self.decision_engine = decision_engine or DecisionEngine()
        self.proposal_provider = proposal_provider
    def process(self, request: CognitiveRequest, *, observations: tuple[ContextItem, ...] = ()) -> tuple[DecisionResult, ReasoningTrace]:
        stages = ["request_validated", "context_retrieved", "attention_allocated"]
        context = self.context_builder.build(request, observations=observations)
        attended_items = tuple(entry.item for entry in context.items)
        if self.proposal_provider is None:
            decision = self.decision_engine.decide(())
            stages.append("proposal_provider_unconfigured")
            notes = ("No reasoning provider configured; no action was fabricated.",)
        else:
            options = tuple(self.proposal_provider(request, attended_items))
            stages.extend(("candidate_actions_proposed", "decision_scored"))
            decision = self.decision_engine.decide(options)
            notes = ("Decision output is advisory; action execution and approval remain in SITA's existing security layer.",)
        trace = ReasoningTrace(request.request_id, tuple(stages), tuple(item.item_id for item in attended_items), decision, notes)
        return decision, trace
