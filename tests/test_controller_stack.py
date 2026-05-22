import pytest

from modules.controller_stack import (
    _axis_directions,
    _axis_deadzones,
    _axis_enabled,
    _merge,
    _route_packet_axes,
    _route_packet_buttons,
    _route_nidaq_axes,
    _route_gamepad_buttons,
    _route_nidaq_buttons,
    apply_axis_deadzones,
    apply_axis_enabled,
    apply_axis_settings,
    apply_deadzone,
    to_mask,
)


def test_apply_deadzone_matches_nidaq_shape():
    assert apply_deadzone(0.014, 0.015) == 0.0
    assert apply_deadzone(-0.014, 0.015) == 0.0
    assert apply_deadzone(1.0, 0.015) == pytest.approx(1.0)
    assert apply_deadzone(-1.0, 0.015) == pytest.approx(-1.0)
    assert apply_deadzone(0.5, 0.1) == pytest.approx((0.5 - 0.1) / 0.9)


def test_apply_axis_deadzones_quantizes_back_to_int8():
    assert apply_axis_deadzones([1, -1, 127, -128], [0.05, 0.05, 0.05, 0.05]) == [0, 0, 127, -127]


def test_axis_deadzones_use_named_axis_entries():
    config = {
        "gamepad": {
            "axes": [
                {"index": 0, "name": "right_stick_x", "deadzone_percent": 5},
                {"index": 3, "name": "left_stick_x", "deadzone_percent": 1.5},
            ]
        }
    }
    assert _axis_deadzones(config, "gamepad") == [0.05, 0.0, 0.0, 0.015, 0.0, 0.0, 0.0, 0.0]


def test_axis_deadzones_keep_legacy_array_compatibility():
    config = {
        "gamepad": {
            "deadzone_percent": {
                "axes": [5, 1.5]
            }
        }
    }
    assert _axis_deadzones(config, "gamepad") == [0.05, 0.015, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]


def test_axis_directions_default_to_positive_and_allow_negative_flip():
    config = {
        "gamepad": {
            "axes": [
                {"index": 0, "name": "right_stick_x", "direction": -1},
                {"index": 1, "name": "right_stick_y", "direction": 1},
            ]
        }
    }
    assert _axis_directions(config, "gamepad") == [-1, 1, 1, 1, 1, 1, 1, 1]
    assert apply_axis_settings([50, 50], [0.0, 0.0], [-1, 1]) == [-50, 50]


def test_axis_enabled_defaults_true_and_can_zero_disabled_axis():
    config = {
        "nidaq": {
            "axes": [
                {"index": 0, "name": "right_lr", "enabled": False},
                {"index": 2, "name": "right_rocker", "enabled": True},
            ]
        }
    }

    enabled = _axis_enabled(config, "nidaq")

    assert enabled == [False, True, True, True, True, True, True, True]
    assert apply_axis_enabled([50, -60, 70], enabled) == [0, -60, 70]


def test_nidaq_axes_route_to_configured_gamepad_axis_names():
    config = {
        "gamepad": {
            "axes": [
                {"index": 0, "name": "right_stick_x"},
                {"index": 1, "name": "right_stick_y"},
                {"index": 6, "name": "right_trigger"},
            ]
        },
        "nidaq": {
            "axes": [
                {"index": 0, "gamepad_axis": "right_trigger", "enabled": True},
                {"index": 1, "gamepad_axis": "right_stick_x", "enabled": True},
                {"index": 2, "gamepad_axis": "right_stick_y", "enabled": False},
            ]
        },
    }

    routed = _route_nidaq_axes([10, 20, 30], config)

    assert routed[0] == 20
    assert routed[1] == 0
    assert routed[6] == 10


def test_none_axis_names_are_not_routable_outputs():
    config = {
        "gamepad": {
            "axes": [
                {"index": 0, "name": "right_stick_x", "enabled": True},
                {"index": 5, "name": "none", "enabled": False},
            ]
        },
        "nidaq": {
            "axes": [
                {"index": 0, "gamepad_axis": "none", "enabled": True},
                {"index": 1, "gamepad_axis": "right_stick_x", "enabled": True},
            ]
        },
    }

    routed = _route_nidaq_axes([99, 42], config)

    assert routed[0] == 42
    assert routed[5] == 0


def test_merge_prefers_larger_absolute_axis_and_ors_buttons():
    ai, di = _merge(
        nidaq_ai=[10, -30, 0],
        nidaq_di=[False, True, False],
        gp_ai=[20, -10, -5],
        gp_di=[True, False, False],
    )
    assert ai == [20, -30, -5]
    assert di == [True, True, False]
    assert to_mask(di) == 0b011


def test_packet_axes_merge_configured_sources_by_slot():
    config = {
        "axes": [
            {
                "index": 0,
                "gamepad": {"name": "right_stick_x", "direction": 1, "deadzone_percent": 0},
                "nidaq": {"index": 2, "direction": -1, "deadzone_percent": 0},
            },
            {"index": 1, "gamepad": None, "nidaq": None},
        ]
    }

    routed = _route_packet_axes(nidaq_values=[0, 0, 50], gp_values=[20], config=config)

    assert routed[0] == -50
    assert routed[1] == 0
    assert len(routed) == 8


def test_packet_buttons_merge_configured_sources_by_slot():
    config = {
        "buttons": [
            {"index": 0, "gamepad": {"name": "A"}, "nidaq": {"index": 2}},
            {"index": 1, "gamepad": {"name": "B"}, "nidaq": None},
            {"index": 15, "gamepad": None, "nidaq": None},
        ]
    }

    routed = _route_packet_buttons(
        nidaq_values=[False, False, True],
        gp={"A": False, "B": True},
        config=config,
    )

    assert routed[0] is True
    assert routed[1] is True
    assert routed[15] is False
    assert len(routed) == 16


def test_nidaq_button_routes_can_remap_and_disable_inputs():
    config = {
        "nidaq": {
            "buttons": [
                {"index": 0, "gamepad_button": "LeftBumper", "enabled": True},
                {"index": 1, "gamepad_button": "RightBumper", "enabled": False},
                {"index": 2, "gamepad_button": "LeftBumper", "enabled": True},
            ]
        },
    }

    routed = _route_nidaq_buttons([True, True, True], config)

    assert routed[4] is True
    assert routed[5] is False
    assert to_mask(routed) == 0b10000


def test_gamepad_button_routes_use_xbox_names_as_source_truth():
    config = {
        "gamepad": {
            "buttons": [
                {"name": "A", "enabled": True},
                {"name": "Start", "enabled": True},
                {"name": "LeftDPad", "enabled": True},
                {"name": "RightDPad", "enabled": True},
                {"name": "B", "enabled": False},
            ]
        },
    }
    gp = {"A": True, "B": True, "Start": True, "LeftDPad": True, "RightDPad": True}

    routed = _route_gamepad_buttons(gp, config)

    assert routed[0] is True
    assert routed[9] is True
    assert routed[12] is True
    assert routed[13] is True
    assert routed[1] is False
    assert to_mask(routed) == 0b11001000000001
