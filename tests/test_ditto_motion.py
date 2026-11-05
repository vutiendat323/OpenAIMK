"""CPU equivalence and RNG checks against Ditto's actual motion modules."""

import copy
import importlib
import sys
import types
from pathlib import Path

import pytest

torch = pytest.importorskip("torch")
pytest.importorskip("einops")
ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def upstream():
    directory = ROOT / ".runtime/Ditto/core/models/modules"
    if not (directory / "LMDM.py").exists():
        pytest.skip("local Ditto source is not installed")
    package = types.ModuleType("_ditto_motion_reference")
    package.__path__ = [str(directory)]
    sys.modules[package.__name__] = package
    package.model = importlib.import_module(f"{package.__name__}.lmdm_modules.model")
    package.diffusion = importlib.import_module(f"{package.__name__}.LMDM")
    previous_threads = torch.get_num_threads()
    torch.set_num_threads(2)
    yield package
    torch.set_num_threads(previous_threads)
    for name in tuple(sys.modules):
        if name == package.__name__ or name.startswith(f"{package.__name__}."):
            del sys.modules[name]


def small_decoder(upstream, *, multi_cond_frame=False, use_rotary=True):
    return upstream.model.MotionDecoder(
        nfeats=3,
        seq_len=5,
        latent_dim=16,
        ff_size=32,
        num_layers=2,
        num_heads=2,
        cond_feature_dim=7,
        multi_cond_frame=multi_cond_frame,
        use_rotary=use_rotary,
    ).eval()


@pytest.mark.parametrize("cond_drop_prob", [0, 1])
@pytest.mark.parametrize("multi_cond_frame", [False, True])
@pytest.mark.parametrize("use_rotary", [False, True])
def test_drop_endpoints_preserve_changing_audio_and_skip_unused_encoder(
    upstream, cond_drop_prob, multi_cond_frame, use_rotary
):
    from scripts.ditto_motion import PreparedMotionDecoder

    torch.manual_seed(51)
    reference = small_decoder(upstream, multi_cond_frame=multi_cond_frame, use_rotary=use_rotary)
    optimized = PreparedMotionDecoder(copy.deepcopy(reference))
    calls = []
    handle = optimized.original.cond_encoder.register_forward_hook(lambda *_: calls.append(1))
    x = torch.randn(2, 5, 3)
    frame = torch.randn(2, 5, 4) if multi_cond_frame else torch.randn(2, 3)
    times = torch.tensor([299, 999])
    outputs = []
    with torch.inference_mode():
        for _ in range(2):
            audio = torch.randn(2, 5, 7)
            expected = reference(x, frame, audio, times, cond_drop_prob)
            actual = optimized(x, frame, audio, times, cond_drop_prob)
            torch.testing.assert_close(actual, expected, rtol=1e-6, atol=1e-6)
            outputs.append(actual)
    assert len(calls) == (2 if cond_drop_prob == 0 else 0)
    if cond_drop_prob == 0:
        assert (outputs[0] - outputs[1]).abs().max().item() > 1e-4
    else:
        torch.testing.assert_close(*outputs, rtol=0, atol=0)
    handle.remove()


@pytest.mark.parametrize("guidance_weight", [0, 1, 2])
def test_guidance_preserves_results_and_shares_audio_input_and_time_projections(
    upstream, guidance_weight
):
    from scripts.ditto_motion import PreparedMotionDecoder

    torch.manual_seed(52)
    reference = small_decoder(upstream)
    optimized = PreparedMotionDecoder(copy.deepcopy(reference))
    calls = {"cond_encoder": 0, "input_projection": 0, "time_mlp": 0}
    handles = []
    for name in calls:

        def record(*_, name=name):
            calls[name] += 1

        handles.append(getattr(optimized.original, name).register_forward_hook(record))
    with torch.inference_mode():
        for _ in range(2):
            x, frame = torch.randn(2, 5, 3), torch.randn(2, 3)
            audio, times = torch.randn(2, 5, 7), torch.tensor([199, 799])
            expected = reference.guided_forward(x, frame, audio, times, guidance_weight)
            actual = optimized.guided_forward(x, frame, audio, times, guidance_weight)
            torch.testing.assert_close(actual, expected, rtol=1e-6, atol=1e-6)
    assert calls == {"cond_encoder": 2, "input_projection": 2, "time_mlp": 2}
    for handle in handles:
        handle.remove()


def small_sampler(upstream):
    # Use the real sampler and schedules with a small real decoder; LMDM's
    # constructor otherwise hardcodes a 512-wide, eight-layer network.
    sampler = upstream.diffusion.LMDM.__new__(upstream.diffusion.LMDM)
    torch.nn.Module.__init__(sampler)
    sampler.motion_feat_dim, sampler.audio_feat_dim, sampler.seq_frames = 3, 7, 5
    sampler.device, sampler.n_timestep = "cpu", 1000
    sampler.clip_denoised, sampler.guidance_weight = False, 2
    sampler.model = small_decoder(upstream)
    sampler.init_diff()
    sampler.sampling_timesteps = None
    return sampler.eval()


def test_ddim_preserves_sampling_outputs_noise_and_rng_without_stale_audio(upstream):
    from scripts.ditto_motion import install_motion_optimization

    torch.manual_seed(53)
    reference = small_sampler(upstream)
    optimized = install_motion_optimization(copy.deepcopy(reference))
    assert install_motion_optimization(optimized) is optimized
    calls = []
    handle = optimized.model.original.cond_encoder.register_forward_hook(lambda *_: calls.append(1))
    for steps in (5, 4):
        outputs = []
        for _ in range(2):
            frame, audio = torch.randn(1, 3), torch.randn(1, 5, 7)
            initial_rng = torch.random.get_rng_state()
            expected = reference.ddim_sample(frame, audio, steps)
            expected_rng = torch.random.get_rng_state()
            torch.random.set_rng_state(initial_rng)
            calls.clear()
            actual = optimized.ddim_sample(frame, audio, steps)
            assert torch.equal(torch.random.get_rng_state(), expected_rng)
            assert len(calls) == 1
            torch.testing.assert_close(actual, expected, rtol=1e-6, atol=1e-6)
            for actual_noise, expected_noise in zip(
                optimized.noise_list, reference.noise_list, strict=True
            ):
                torch.testing.assert_close(actual_noise, expected_noise, rtol=0, atol=0)
            outputs.append(actual)
        assert (outputs[0] - outputs[1]).abs().max().item() > 1e-4
    handle.remove()


def test_fractional_dropout_preserves_random_mask_and_rng(upstream):
    from scripts.ditto_motion import PreparedMotionDecoder

    torch.manual_seed(54)
    reference = small_decoder(upstream)
    optimized = PreparedMotionDecoder(copy.deepcopy(reference))
    x, frame, audio = torch.randn(2, 5, 3), torch.randn(2, 3), torch.randn(2, 5, 7)
    times = torch.tensor([199, 799])
    initial_rng = torch.random.get_rng_state()
    with torch.inference_mode():
        expected = reference(x, frame, audio, times, cond_drop_prob=0.35)
        expected_rng = torch.random.get_rng_state()
        torch.random.set_rng_state(initial_rng)
        actual = optimized(x, frame, audio, times, cond_drop_prob=0.35)
    torch.testing.assert_close(actual, expected, rtol=0, atol=0)
    assert torch.equal(torch.random.get_rng_state(), expected_rng)


@pytest.mark.parametrize("use_rotary", [False, True])
def test_prepared_guidance_captures_full_graph_and_preserves_cpu_autocast(upstream, use_rotary):
    from scripts.ditto_motion import PreparedMotionDecoder

    torch.manual_seed(55)
    reference = small_decoder(upstream, use_rotary=use_rotary)
    optimized = PreparedMotionDecoder(copy.deepcopy(reference))
    compiled = torch.compile(optimized.guided_forward, fullgraph=True, backend="eager")
    with torch.inference_mode(), torch.autocast("cpu", dtype=torch.bfloat16):
        for _ in range(2):
            x, frame, audio = torch.randn(2, 5, 3), torch.randn(2, 3), torch.randn(2, 5, 7)
            times = torch.tensor([199, 799])
            expected = reference.guided_forward(x, frame, audio, times, 2)
            conditioning = optimized.prepare_conditioning(audio)
            actual = compiled(x, frame, conditioning, times, 2)
            torch.testing.assert_close(actual, expected, rtol=0, atol=0)
            for drop in (0, 1):
                torch.testing.assert_close(
                    optimized(x, frame, audio, times, drop),
                    reference(x, frame, audio, times, drop),
                    rtol=0,
                    atol=0,
                )
