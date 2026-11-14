"""Tests for bounded Hebbian and spike-timing-dependent plasticity."""

import pytest

from tara_app.learning import HebbianRule, LearningEngine, STDPConfig
from tara_app.neural import LIFNeuron, SpikingNetwork, Synapse


def make_engine(weight=0.5, **kwargs):
    return LearningEngine([Synapse(pre=0, post=1, weight=weight)], **kwargs)


def test_hebbian_coactivity_strengthens_excitatory_weight():
    engine = make_engine(0.5, hebbian=HebbianRule(learning_rate=0.1))
    assert engine.apply_hebbian(0, pre_activity=1.0, post_activity=0.5) == pytest.approx(0.55)


def test_hebbian_strengthens_inhibitory_magnitude_without_reversing_sign():
    engine = make_engine(-0.5, hebbian=HebbianRule(learning_rate=0.1))
    assert engine.apply_hebbian(0, pre_activity=1.0, post_activity=1.0) == pytest.approx(-0.6)


def test_stdp_potentiates_when_precedes_post():
    engine = make_engine(0.5, stdp=STDPConfig(
        potentiation_amplitude=0.1,
        depression_amplitude=0.1,
        potentiation_tau_ms=20.0,
        depression_tau_ms=20.0,
    ))
    updated = engine.apply_stdp(
        0,
        pre_spike_times_ms=(10.0,),
        post_spike_times_ms=(15.0,),
    )
    assert updated > 0.5


def test_stdp_depresses_when_post_precedes_pre():
    engine = make_engine(0.5, stdp=STDPConfig(
        potentiation_amplitude=0.1,
        depression_amplitude=0.1,
    ))
    updated = engine.apply_stdp(
        0,
        pre_spike_times_ms=(15.0,),
        post_spike_times_ms=(10.0,),
    )
    assert updated < 0.5


def test_learning_is_bounded_and_preserves_synapse_polarity():
    engine = make_engine(-0.95, hebbian=HebbianRule(learning_rate=1.0), max_weight_magnitude=1.0)
    assert engine.apply_hebbian(0, pre_activity=1.0, post_activity=1.0) == -1.0
    assert engine.apply_hebbian(0, pre_activity=0.0, post_activity=1.0) == -1.0


def test_learning_snapshot_can_be_restored():
    engine = make_engine()
    initial = engine.snapshot()
    engine.apply_hebbian(0, pre_activity=1.0, post_activity=1.0)
    engine.restore(initial)
    assert engine.weights == initial


def test_learning_persistence_requires_approval_and_checks_topology(tmp_path):
    engine = make_engine()
    path = tmp_path / "weights.json"
    with pytest.raises(PermissionError, match="approval"):
        engine.save(path, authorize_write=lambda: False)
    assert not path.exists()
    engine.apply_hebbian(0, pre_activity=1.0, post_activity=1.0)
    engine.save(path, authorize_write=lambda: True)
    restored = make_engine()
    restored.load(path)
    assert restored.weights == engine.weights
    changed_topology = LearningEngine([Synapse(pre=1, post=0, weight=0.5)])
    with pytest.raises(ValueError, match="topology"):
        changed_topology.load(path)


def test_network_receives_learned_weights_without_topology_change():
    network = SpikingNetwork()
    network.add_neuron(LIFNeuron())
    network.add_neuron(LIFNeuron())
    network.add_synapse(Synapse(pre=0, post=1, weight=0.5))
    learner = LearningEngine(network.synapses)
    learner.apply_hebbian(0, pre_activity=1.0, post_activity=1.0)
    learner.apply_to_network(network)
    assert network.synapses[0].weight == pytest.approx(0.51)
    assert network.synapse_count == 1


def test_invalid_activity_and_unsorted_spike_times_are_rejected():
    engine = make_engine()
    with pytest.raises(ValueError, match="pre_activity"):
        engine.apply_hebbian(0, pre_activity=1.2, post_activity=1.0)
    with pytest.raises(ValueError, match="sorted"):
        engine.apply_stdp(0, pre_spike_times_ms=(2.0, 1.0), post_spike_times_ms=())


def test_invalid_learning_configuration_is_rejected():
    with pytest.raises(ValueError, match="learning_rate"):
        HebbianRule(learning_rate=0.0)
    with pytest.raises(ValueError, match="positive"):
        STDPConfig(potentiation_tau_ms=0.0)
