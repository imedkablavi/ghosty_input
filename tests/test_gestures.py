from ghosty_input.core.gestures import EdgeTrigger


def test_edge_trigger_only_fires_on_rising_edge():
    edge = EdgeTrigger()
    assert edge.rising(False) is False
    assert edge.rising(True) is True
    assert edge.rising(True) is False
    assert edge.rising(False) is False
    assert edge.rising(True) is True
