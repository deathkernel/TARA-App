"""Tests for the first TN-86 spiking-neural processing primitives."""

import pytest

from tara_app.neural import LIFNeuron, SpikingNetwork, Synapse


def test_lif_neuron_remains_at_rest_without_current():
    neuron = LIFNeuron()

    assert neuron.step(0.0) is False
    assert neuron.voltage == pytest.approx(neuron.resting_potential)


def test_lif_neuron_spikes_when_threshold_is_crossed():
    neuron = LIFNeuron(
        resting_potential=0.0,
        threshold=1.0,
        reset_potential=0.0,
        membrane_time_constant_ms=10.0,
        resistance=1.0,
        refractory_period_ms=2.0,
    )

    assert neuron.step(20.0, dt_ms=1.0) is True
    assert neuron.voltage == 0.0


def test_lif_neuron_observes_refractory_period():
    neuron = LIFNeuron(
        resting_potential=0.0,
        threshold=1.0,
        reset_potential=0.0,
        membrane_time_constant_ms=10.0,
        refractory_period_ms=2.0,
    )

    assert neuron.step(20.0) is True
    assert neuron.step(20.0) is False
    assert neuron.step(20.0) is False
    assert neuron.step(20.0) is True


def test_network_delivers_spike_to_synapse_on_next_step():
    network = SpikingNetwork()
    source = network.add_neuron(
        LIFNeuron(
            resting_potential=0.0,
            threshold=1.0,
            reset_potential=0.0,
            membrane_time_constant_ms=10.0,
            refractory_period_ms=0.0,
        )
    )
    target = network.add_neuron(
        LIFNeuron(
            resting_potential=0.0,
            threshold=1.0,
            reset_potential=0.0,
            membrane_time_constant_ms=10.0,
            refractory_period_ms=0.0,
        )
    )
    network.add_synapse(Synapse(pre=source, post=target, weight=20.0))

    assert network.step([20.0, 0.0]) == (source,)
    assert network.step([0.0, 0.0]) == (target,)


def test_network_rejects_unknown_synapse_endpoint():
    network = SpikingNetwork()
    network.add_neuron()

    with pytest.raises(ValueError, match="endpoint"):
        network.add_synapse(Synapse(pre=0, post=1, weight=1.0))


def test_network_rejects_wrong_input_width():
    network = SpikingNetwork()
    network.add_neuron()

    with pytest.raises(ValueError, match="match neuron_count"):
        network.step([0.0, 1.0])


def test_neuron_rejects_invalid_time_step():
    neuron = LIFNeuron()

    with pytest.raises(ValueError, match="dt_ms"):
        neuron.step(0.0, dt_ms=0.0)
