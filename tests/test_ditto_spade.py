"""CPU equivalence against the actual upstream Ditto SPADE implementation."""

import copy
import importlib.util
import sys
import types
from pathlib import Path

import pytest

torch = pytest.importorskip("torch")
ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def upstream():
    # Load only the real modules under test, avoiding unrelated model dependencies.
    directory = ROOT / ".runtime/Ditto/core/models/modules"
    if not (directory / "util.py").exists():
        pytest.skip("local Ditto source is not installed")
    package = types.ModuleType("_ditto_spade_reference")
    package.__path__ = [str(directory)]
    sys.modules[package.__name__] = package
    for name in ("util", "spade_generator"):
        spec = importlib.util.spec_from_file_location(
            f"{package.__name__}.{name}", directory / f"{name}.py"
        )
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        setattr(package, name, module)
    previous_threads = torch.get_num_threads()
    torch.set_num_threads(2)
    yield package
    torch.set_num_threads(previous_threads)
    for name in ("util", "spade_generator"):
        del sys.modules[f"{package.__name__}.{name}"]
    del sys.modules[package.__name__]


def test_fused_gamma_beta_preserves_distinct_heads_and_new_segmentation(upstream):
    from scripts.ditto_spade import FusedSPADE

    torch.manual_seed(41)
    reference = upstream.util.SPADE(7, 5).double().eval()
    optimized = FusedSPADE(copy.deepcopy(reference))
    x = torch.randn(2, 7, 9, 11, dtype=torch.float64)
    outputs = []
    with torch.inference_mode():
        for _ in range(2):
            seg = torch.randn(2, 5, 4, 6, dtype=torch.float64)
            expected = reference(x, seg)
            actual = optimized(x, seg)
            torch.testing.assert_close(actual, expected, rtol=1e-12, atol=1e-12)
            outputs.append(actual)
    assert not torch.allclose(*outputs)


@pytest.mark.parametrize("batch_conditioning", [False, True])
@pytest.mark.parametrize("fin,fout", [(12, 12), (12, 7), (7, 12)])
def test_block_preserves_shortcut_and_distinct_norm_weights(
    upstream, fin, fout, batch_conditioning
):
    from scripts.ditto_spade import install_spade_optimization

    torch.manual_seed(42)
    reference = upstream.util.SPADEResnetBlock(fin, fout, "spadeinstance", 5).double().eval()
    optimized = install_spade_optimization(
        copy.deepcopy(reference), batch_conditioning=batch_conditioning
    )
    calls = []
    handles = [
        module.register_forward_hook(lambda *_: calls.append(1))
        for module in optimized.modules()
        if isinstance(module, torch.nn.Conv2d)
    ]
    with torch.inference_mode():
        for height, width in ((7, 9), (10, 8)):
            x = torch.randn(2, fin, height, width, dtype=torch.float64)
            seg = torch.randn(2, 5, 4, 3, dtype=torch.float64)
            calls.clear()
            torch.testing.assert_close(optimized(x, seg), reference(x, seg), rtol=1e-11, atol=1e-11)
            if not batch_conditioning:
                assert len(calls) == (6 if fin == fout else 9)
            else:
                assert len(calls) == (4 if fin == fout else 7 if fin > fout else 5)
    for handle in handles:
        handle.remove()


@pytest.mark.parametrize("batch_conditioning", [False, True])
@pytest.mark.parametrize("fin,fout", [(12, 12), (12, 7)])
def test_channels_last_float32_block_captures_full_graph_on_cpu(
    upstream, batch_conditioning, fin, fout
):
    from scripts.ditto_spade import install_spade_optimization

    torch.manual_seed(44)
    reference = upstream.util.SPADEResnetBlock(fin, fout, "spadeinstance", 5).eval()
    reference.to(memory_format=torch.channels_last)
    optimized = install_spade_optimization(
        copy.deepcopy(reference), batch_conditioning=batch_conditioning
    )
    compiled = torch.compile(optimized, fullgraph=True, backend="eager")
    x = torch.randn(2, fin, 7, 9).contiguous(memory_format=torch.channels_last)
    with torch.inference_mode():
        for _ in range(2):
            seg = torch.randn(2, 5, 4, 3).contiguous(memory_format=torch.channels_last)
            expected = reference(x, seg)
            actual = compiled(x, seg)
            torch.testing.assert_close(actual, expected, rtol=2e-5, atol=2e-6)
            assert actual.is_contiguous(memory_format=torch.channels_last)


@pytest.mark.parametrize(
    "batch_conditioning,exclude_modules", [(False, ()), (True, ()), (True, ("up_1",))]
)
def test_actual_decoder_preserves_changing_frames_and_survives_reinstall(
    upstream, batch_conditioning, exclude_modules
):
    from scripts.ditto_spade import install_spade_optimization

    torch.manual_seed(43)
    reference = upstream.spade_generator.SPADEDecoder(
        block_expansion=2, max_features=8, out_channels=2, num_down_blocks=1
    ).double()
    # Initialize the real spectral-normalization buffers, then mirror the
    # renderer's materialization before installing the conditioning adapter.
    with torch.no_grad():
        reference(torch.randn(1, 4, 3, 4, dtype=torch.float64))
    reference.eval()
    for module in reference.modules():
        if hasattr(module, "weight_orig"):
            torch.nn.utils.remove_spectral_norm(module)
    optimized = copy.deepcopy(reference)
    last_block = optimized.up_1
    optimized = install_spade_optimization(
        optimized, batch_conditioning=batch_conditioning, exclude_modules=exclude_modules
    )
    if exclude_modules:
        assert optimized.up_1 is last_block
        assert type(optimized.G_middle_0.norm_0) is not upstream.util.SPADE
    assert (
        install_spade_optimization(
            optimized, batch_conditioning=batch_conditioning, exclude_modules=exclude_modules
        )
        is optimized
    )
    outputs = []
    with torch.inference_mode():
        for _ in range(2):
            feature = torch.randn(1, 4, 3, 4, dtype=torch.float64)
            expected = reference(feature)
            actual = optimized(feature)
            assert actual.shape == (1, 3, 24, 32)
            torch.testing.assert_close(actual, expected, rtol=1e-10, atol=1e-10)
            outputs.append(actual)
    assert (outputs[0] - outputs[1]).abs().max().item() > 1e-4
