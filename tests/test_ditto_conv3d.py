"""CPU checks for exact depth-folded Conv3d replacement; never loads the renderer."""

import pytest

torch = pytest.importorskip("torch")
nn = torch.nn


@pytest.fixture(autouse=True, scope="module")
def limited_cpu_threads():
    torch.set_num_threads(min(2, torch.get_num_threads()))


@pytest.mark.parametrize("channels_last", [False, True])
@pytest.mark.parametrize(
    "shape,kwargs",
    [
        ((2, 3, 4, 8, 9), {"out_channels": 5, "kernel_size": 3, "padding": 1}),
        ((1, 3, 2, 8, 9), {"out_channels": 2, "kernel_size": 7, "padding": 3}),
        ((2, 4, 5, 7, 9), {"out_channels": 6, "kernel_size": 1, "bias": False}),
        (
            (2, 4, 8, 9, 10),
            {
                "out_channels": 6,
                "kernel_size": (3, 2, 3),
                "padding": (2, 1, 2),
                "stride": (2, 2, 1),
                "dilation": (2, 1, 2),
                "groups": 2,
            },
        ),
        (
            (1, 3, 6, 9, 10),
            {"out_channels": 6, "kernel_size": 3, "groups": 3, "padding": 0},
        ),
    ],
)
def test_adapter_preserves_conv3d_values_and_layout(shape, kwargs, channels_last):
    # Catches swapped depth/channel order, missing boundary zeros, and wrong groups.
    from scripts.ditto_conv3d import Conv3dAs2d

    torch.manual_seed(41)
    original = nn.Conv3d(shape[1], **kwargs, dtype=torch.float64).eval()
    memory_format = torch.channels_last_3d if channels_last else torch.contiguous_format
    original.to(memory_format=memory_format)
    adapter = Conv3dAs2d(original, channels_last=channels_last)
    values = torch.randn(*shape, dtype=torch.float64).contiguous(memory_format=memory_format)
    with torch.no_grad():
        expected = original(values)
        actual = adapter(values)
    torch.testing.assert_close(actual, expected, rtol=1e-12, atol=1e-12)
    assert actual.is_contiguous(memory_format=memory_format)


def test_adapter_preserves_each_depth_boundary_and_refreshes_inputs():
    # Literal expected values make depth kernel reversal and stale data observable.
    from scripts.ditto_conv3d import Conv3dAs2d

    original = nn.Conv3d(1, 1, (3, 1, 1), padding=(1, 0, 0), bias=False)
    with torch.no_grad():
        original.weight.copy_(torch.tensor([1.0, 10.0, 100.0]).reshape(1, 1, 3, 1, 1))
    adapter = Conv3dAs2d(original)
    with torch.no_grad():
        first = adapter(torch.tensor([1.0, 2.0, 3.0]).reshape(1, 1, 3, 1, 1))
        second = adapter(torch.tensor([3.0, 2.0, 1.0]).reshape(1, 1, 3, 1, 1))
    torch.testing.assert_close(first.flatten(), torch.tensor([210.0, 321.0, 32.0]))
    torch.testing.assert_close(second.flatten(), torch.tensor([230.0, 123.0, 12.0]))


def test_adapter_handles_noncontiguous_input_and_different_depth():
    from scripts.ditto_conv3d import Conv3dAs2d

    torch.manual_seed(42)
    original = nn.Conv3d(2, 4, 3, padding=1).eval()
    adapter = Conv3dAs2d(original)
    with torch.no_grad():
        for depth in (1, 3, 6):
            values = torch.randn(2, 2, depth, 8, 10)[..., ::2]
            assert not values.is_contiguous()
            torch.testing.assert_close(adapter(values), original(values))


def test_adapter_supports_fullgraph_compile_with_changing_inputs():
    from scripts.ditto_conv3d import Conv3dAs2d

    torch.manual_seed(43)
    original = nn.Conv3d(2, 3, 3, padding=1).eval()
    adapter = torch.compile(Conv3dAs2d(original), backend="eager", fullgraph=True)
    with torch.no_grad():
        first = torch.randn(1, 2, 3, 5, 6)
        second = torch.randn_like(first)
        result = adapter(first)
        torch.testing.assert_close(result, original(first))
        changed = adapter(second)
        torch.testing.assert_close(changed, original(second))
    assert not torch.allclose(result, changed)


@pytest.mark.parametrize("kwargs", [{"padding_mode": "reflect"}, {"padding": "same"}])
def test_adapter_rejects_padding_it_cannot_preserve(kwargs):
    from scripts.ditto_conv3d import Conv3dAs2d

    with pytest.raises(ValueError, match="padding"):
        Conv3dAs2d(nn.Conv3d(2, 3, 3, **kwargs))


def test_replacement_changes_only_selected_nested_convolution():
    from scripts.ditto_conv3d import Conv3dAs2d, replace_conv3d_modules

    torch.manual_seed(44)
    model = nn.Sequential(nn.Conv3d(2, 3, 3, padding=1), nn.Sequential(nn.Conv3d(3, 2, 1)))
    model.eval()
    untouched = model[0]
    replaced = model[1][0]
    values = torch.randn(1, 2, 3, 5, 6)
    with torch.no_grad():
        expected = model(values)
    names = replace_conv3d_modules(model, ["1.0"])
    assert names == ["1.0"]
    assert model[0] is untouched
    assert isinstance(model[1][0], Conv3dAs2d)
    assert not model[1][0].training
    with torch.no_grad():
        torch.testing.assert_close(model(values), expected)
        # Original weights remain usable; conversion did not reshape them in place.
        torch.testing.assert_close(model[1][0](untouched(values)), replaced(untouched(values)))


def test_replacement_defaults_to_all_conv3d_and_is_idempotent():
    from scripts.ditto_conv3d import replace_conv3d_modules

    model = nn.Sequential(nn.Conv3d(2, 3, 3, padding=1), nn.Sequential(nn.Conv3d(3, 2, 1)))
    values = torch.randn(1, 2, 3, 5, 6)
    with torch.no_grad():
        expected = model(values)
        assert replace_conv3d_modules(model) == ["0", "1.0"]
        assert replace_conv3d_modules(model) == []
        torch.testing.assert_close(model(values), expected)


def test_replacement_validates_names_before_mutating_model():
    from scripts.ditto_conv3d import replace_conv3d_modules

    model = nn.Sequential(nn.Conv3d(2, 3, 1), nn.ReLU())
    original = model[0]
    with pytest.raises(ValueError, match="Conv3d"):
        replace_conv3d_modules(model, ["0", "1"])
    assert model[0] is original
