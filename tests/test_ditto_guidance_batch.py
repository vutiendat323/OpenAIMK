"""CPU comparisons of two-branch batching against actual Ditto guidance."""

import copy

import pytest
from test_ditto_motion import small_decoder, small_sampler
from test_ditto_motion import upstream as upstream

torch = pytest.importorskip("torch")


@pytest.mark.parametrize("autocast", [False, True])
@pytest.mark.parametrize("guidance_weight", [0, 1, 2])
@pytest.mark.parametrize("batch_size", [1, 2])
@pytest.mark.parametrize("use_rotary", [False, True])
def test_batched_guidance_preserves_null_and_conditional_branches_on_changing_inputs(
    upstream, autocast, guidance_weight, batch_size, use_rotary
):
    from scripts.ditto_guidance_batch import BatchedGuidanceMotionDecoder

    torch.manual_seed(61)
    reference = small_decoder(upstream, use_rotary=use_rotary)
    optimized = BatchedGuidanceMotionDecoder(copy.deepcopy(reference))
    batches = []
    handle = optimized.original.seqTransDecoder.register_forward_hook(
        lambda _module, inputs, _output: batches.append(inputs[0].shape[0])
    )
    with torch.inference_mode(), torch.autocast("cpu", dtype=torch.bfloat16, enabled=autocast):
        for _ in range(2):
            x = torch.randn(batch_size, 5, 3)
            frame, audio = torch.randn(batch_size, 3), torch.randn(batch_size, 5, 7)
            times = torch.full((batch_size,), 799, dtype=torch.long)
            expected = reference.guided_forward(x, frame, audio, times, guidance_weight)
            actual = optimized.guided_forward(x, frame, audio, times, guidance_weight)
            torch.testing.assert_close(
                actual, expected, rtol=0 if autocast else 2e-5, atol=0 if autocast else 2e-6
            )
    assert batches == [2 * batch_size, 2 * batch_size]
    handle.remove()


@pytest.mark.parametrize("autocast", [False, True])
def test_batched_five_step_sampling_preserves_outputs_rng_and_fresh_conditioning(
    upstream, autocast
):
    from scripts.ditto_guidance_batch import install_batched_guidance

    torch.manual_seed(62)
    reference = small_sampler(upstream)
    optimized = install_batched_guidance(copy.deepcopy(reference))
    outputs = []
    for _ in range(2):
        frame, audio = torch.randn(1, 3), torch.randn(1, 5, 7)
        initial_rng = torch.random.get_rng_state()
        with torch.autocast("cpu", dtype=torch.bfloat16, enabled=autocast):
            expected = reference.ddim_sample(frame, audio, 5)
            expected_rng = torch.random.get_rng_state()
            torch.random.set_rng_state(initial_rng)
            actual = optimized.ddim_sample(frame, audio, 5)
        torch.testing.assert_close(
            actual, expected, rtol=0 if autocast else 2e-5, atol=0 if autocast else 2e-6
        )
        assert torch.equal(torch.random.get_rng_state(), expected_rng)
        for actual_noise, expected_noise in zip(
            optimized.noise_list, reference.noise_list, strict=True
        ):
            torch.testing.assert_close(actual_noise, expected_noise, rtol=0, atol=0)
        outputs.append(actual)
    assert (outputs[0] - outputs[1]).abs().max().item() > 1e-4


@pytest.mark.parametrize("install", [False, True])
def test_training_guidance_retains_original_dropout_order_and_rng(upstream, install):
    from scripts.ditto_guidance_batch import BatchedGuidanceMotionDecoder, install_batched_guidance

    torch.manual_seed(63)
    reference = small_decoder(upstream).train()
    if install:
        diffusion = small_sampler(upstream)
        diffusion.model = copy.deepcopy(reference)
        optimized = install_batched_guidance(diffusion).model
        assert install_batched_guidance(diffusion).model is optimized
    else:
        optimized = BatchedGuidanceMotionDecoder(copy.deepcopy(reference))
    x, frame, audio = torch.randn(2, 5, 3), torch.randn(2, 3), torch.randn(2, 5, 7)
    times = torch.tensor([199, 799])
    initial_rng = torch.random.get_rng_state()
    expected = reference.guided_forward(x, frame, audio, times, 2)
    expected_rng = torch.random.get_rng_state()
    torch.random.set_rng_state(initial_rng)
    actual = optimized.guided_forward(x, frame, audio, times, 2)
    torch.testing.assert_close(actual, expected, rtol=0, atol=0)
    assert torch.equal(torch.random.get_rng_state(), expected_rng)


@pytest.mark.parametrize("autocast", [False, True])
def test_batched_multiframe_guidance_captures_full_graph_with_prepared_audio(upstream, autocast):
    from scripts.ditto_guidance_batch import install_batched_guidance

    torch.manual_seed(64)
    reference = small_decoder(upstream, multi_cond_frame=True)
    diffusion = small_sampler(upstream)
    diffusion.model = copy.deepcopy(reference)
    optimized = install_batched_guidance(diffusion).model
    compiled = torch.compile(optimized.guided_forward, fullgraph=True, backend="eager")
    x, frame = torch.randn(1, 5, 3), torch.randn(1, 5, 4)
    times = torch.tensor([799])
    with torch.inference_mode(), torch.autocast("cpu", dtype=torch.bfloat16, enabled=autocast):
        for _ in range(2):
            audio = torch.randn(1, 5, 7)
            expected = reference.guided_forward(x, frame, audio, times, 2)
            conditioning = optimized.prepare_conditioning(audio)
            actual = compiled(x, frame, conditioning, times, 2)
            torch.testing.assert_close(
                actual, expected, rtol=0 if autocast else 2e-5, atol=0 if autocast else 2e-6
            )
