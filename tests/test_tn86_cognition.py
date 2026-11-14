"""Tests for TN-86 attention, context, goals and conservative decisions."""
import pytest
from tara_app.cognition import ActionOption, AttentionFeatures, AttentionMechanism, CognitiveCoordinator, CognitiveRequest, ContextBuilder, ContextItem, DecisionEngine, DecisionPolicy, DecisionStatus, Goal, GoalScheduler, GoalStatus
from tara_app.memory import MemoryEngine, SQLiteMemoryRepository, MemoryKind

def make_memory(tmp_path):
    repository = SQLiteMemoryRepository(tmp_path / "memory.sqlite3", authorize_write=lambda: True)
    return MemoryEngine(repository)

def test_attention_ranks_by_weighted_features_with_stable_ties():
    attention = AttentionMechanism()
    items = [ContextItem("b", "second", AttentionFeatures(0.5, 0.5, 0.5)), ContextItem("a", "first", AttentionFeatures(0.5, 0.5, 0.5))]
    ranked = attention.select(items, limit=2)
    assert [item.item.item_id for item in ranked] == ["a", "b"]
    assert ranked[0].score == pytest.approx(0.5 * (0.35 + 0.20 + 0.15 + 0.15) + 0.15)

def test_context_builder_combines_memory_and_transient_observations(tmp_path):
    memory = make_memory(tmp_path)
    stored = memory.remember("TN-86 uses typed episodic memory", kind=MemoryKind.SEMANTIC, importance=0.9)
    builder = ContextBuilder(memory, recency_half_life_seconds=100.0)
    request = CognitiveRequest("r1", "episodic memory", max_context_items=4)
    observation = ContextItem("sensor-1", "Current screen observation", AttentionFeatures(0.2, 0.5, 1.0), source="vision")
    context = builder.build(request, observations=(observation,), now=stored.created_at)
    assert context.request == request
    assert {item.item.item_id for item in context.items} == {stored.memory_id, "sensor-1"}

def test_context_builder_recency_decays_by_half_life(tmp_path):
    memory = make_memory(tmp_path)
    record = memory.remember("project architecture", kind=MemoryKind.EPISODIC, importance=0.5)
    builder = ContextBuilder(memory, recency_half_life_seconds=10.0)
    context = builder.build(CognitiveRequest("r2", "project architecture"), now=record.created_at + 10.0)
    assert context.items[0].item.features.recency == pytest.approx(0.5)

def test_decision_engine_selects_clear_high_confidence_option():
    engine = DecisionEngine(DecisionPolicy(minimum_score=0.5, minimum_margin=0.1))
    result = engine.decide([ActionOption("a", "Use verified local cache", 0.95, 1.0, 0.0, 1.0), ActionOption("b", "Guess from incomplete data", 0.7, 0.5, 0.2, 0.4)])
    assert result.status is DecisionStatus.SELECTED
    assert result.selected_action is not None and result.selected_action.action_id == "a"

def test_decision_engine_abstains_when_evidence_is_weak():
    result = DecisionEngine().decide([ActionOption("a", "Uncertain action", 0.95, 0.5, 0.1, 0.4)])
    assert result.status is DecisionStatus.ABSTAINED
    assert result.selected_action is None

def test_decision_engine_abstains_when_scores_are_too_close():
    engine = DecisionEngine(DecisionPolicy(minimum_score=0.2, minimum_margin=0.15))
    result = engine.decide([ActionOption("a", "Option A", 0.9, 1.0, 0.0, 0.8), ActionOption("b", "Option B", 0.88, 1.0, 0.0, 0.8)])
    assert result.status is DecisionStatus.ABSTAINED

def test_goal_scheduler_respects_dependencies_and_deadline_pressure():
    scheduler = GoalScheduler()
    scheduler.add(Goal("blocked", "Ship release", 1.0, 1.0, 1.0, dependencies=("tests",)))
    scheduler.add(Goal("tests", "Run tests", 0.7, 0.7, 1.0, deadline_at=100.0))
    scheduler.add(Goal("docs", "Update docs", 0.6, 0.4, 0.8))
    ranked = scheduler.prioritize(now=100.0)
    assert [goal.goal_id for goal, _ in ranked] == ["tests", "docs"]

def test_completed_dependency_unblocks_goal():
    scheduler = GoalScheduler()
    scheduler.add(Goal("base", "Complete foundation"))
    scheduler.add(Goal("next", "Continue work", dependencies=("base",)))
    assert [goal.goal_id for goal, _ in scheduler.prioritize()] == ["base"]
    scheduler.update_status("base", GoalStatus.COMPLETED)
    assert [goal.goal_id for goal, _ in scheduler.prioritize()] == ["next"]

def test_goal_scheduler_rejects_capacity_overflow():
    scheduler = GoalScheduler(capacity=1)
    scheduler.add(Goal("one", "First"))
    with pytest.raises(OverflowError, match="capacity"):
        scheduler.add(Goal("two", "Second"))

def test_coordinator_does_not_fabricate_reasoning_without_provider(tmp_path):
    coordinator = CognitiveCoordinator(ContextBuilder(make_memory(tmp_path)))
    decision, trace = coordinator.process(CognitiveRequest("r3", "nothing stored"))
    assert decision.status is DecisionStatus.ABSTAINED
    assert trace.stages[-1] == "proposal_provider_unconfigured"
    assert "no action was fabricated" in trace.notes[0]

def test_coordinator_uses_injected_provider_but_never_executes_action(tmp_path):
    memory = make_memory(tmp_path)
    memory.remember("verified project configuration", kind=MemoryKind.SEMANTIC)
    coordinator = CognitiveCoordinator(ContextBuilder(memory), proposal_provider=lambda request, context: (ActionOption("inspect", "Inspect the verified configuration", 0.9, 1.0, 0.0, 1.0),))
    decision, trace = coordinator.process(CognitiveRequest("r4", "project configuration"))
    assert decision.status is DecisionStatus.SELECTED
    assert decision.selected_action is not None
    assert trace.stages[-1] == "decision_scored"
    assert "execution and approval remain" in trace.notes[0]
