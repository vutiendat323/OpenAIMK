"""CPU math and prepared-cache contracts for the hybrid Ditto renderer."""

import importlib
import json
import sys
from pathlib import Path

import numpy as np
import pytest

torch = pytest.importorskip("torch")
ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def real_warper():
    checkpoint = ROOT / ".runtime/Ditto/checkpoints/ditto_pytorch/models/warp_network.pth"
    captures = ROOT / "output/avatar-quality-review/ditto-torch-benchmark"
    if not checkpoint.exists() or not (captures / "input-0.npz").exists():
        pytest.skip("local Ditto checkpoint and captured features are required")
    previous_threads = torch.get_num_threads()
    torch.set_num_threads(2)
    checkout = str(ROOT / ".runtime/Ditto")
    sys.path.insert(0, checkout)
    module = importlib.import_module("core.models.modules.warping_network")
    original = module.WarpingNetwork().load_model(str(checkpoint)).eval()
    yield original, captures
    sys.path.remove(checkout)
    torch.set_num_threads(previous_threads)


@pytest.mark.parametrize("capture", [0, 60])
def test_split_matches_real_warper_weights_on_cpu_32px(real_warper, capture):
    from scripts.ditto_trt import DenseMotionCNN, DenseMotionPost, DenseMotionPrep

    original, captures = real_warper
    prep = DenseMotionPrep(original.dense_motion_network).eval()
    cnn = DenseMotionCNN(original.dense_motion_network).eval()
    post = DenseMotionPost(original, half_boundaries=False).eval()
    with np.load(captures / f"input-{capture}.npz") as data:
        feature = torch.from_numpy(data["feature"][:, :, :, :32, :32].copy())
        source = torch.from_numpy(data["source"].copy())
        driving = torch.from_numpy(data["driving"].copy())
    with torch.inference_mode():
        expected = original(feature, source, driving)
        head_input, sparse = prep(feature, source, driving)
        actual = post(feature, sparse, *cnn(head_input))
    assert actual.shape == (1, 256, 32, 32)
    # Cold CPU FP32 kernels showed <3e-6 output drift, then bitwise equality.
    # This feature tolerance is separate from the renderer's RGB acceptance gate.
    torch.testing.assert_close(actual, expected, rtol=1e-5, atol=3e-6)


@pytest.mark.parametrize(
    "regions,expected",
    [
        ([(256, 368, 126, 94)], True),
        ([(256, 368, 127, 94)], False),
        ([(256, 368, 126, 95)], False),
        ([(256, 368, 90, 65), (256, 330, 90, 65)], False),
        ([(256, 368, 90, 65)], True),
        ([(256, float("nan"), 90, 65)], False),
        ([(256, 368, -1, 65)], False),
        ([], False),
    ],
)
def test_roi_coverage_includes_every_mouth_region_and_interpolation_halo(regions, expected):
    from scripts.ditto_trt import roi_covers_regions

    assert roi_covers_regions((128, 272, 384, 464), regions) is expected


@pytest.fixture
def prepared_cache(tmp_path):
    from scripts.ditto_trt import cache_fingerprint, sha256_file

    weights = {name: tmp_path / f"{name}.pth" for name in ("warp_head", "decoder")}
    engines = {name: tmp_path / f"{name}.engine" for name in weights}
    for name, path in weights.items():
        path.write_bytes(f"original {name} weights".encode())
    for name, path in engines.items():
        path.write_bytes(f"validated {name} engine".encode())
    manifest = {
        "fingerprint": cache_fingerprint(
            weights, tensorrt_version="10.7.0", compute_capability=(8, 6)
        ),
        "engines_sha256": {name: sha256_file(path) for name, path in engines.items()},
        "validation": {"passed": True, "captures": [0, 15, 30, 45, 60]},
    }
    path = tmp_path / "ditto-trt.json"
    path.write_text(json.dumps(manifest))
    return path, manifest, weights, engines


def test_prepared_manifest_accepts_identical_weights_engines_and_environment(prepared_cache):
    from scripts.ditto_trt import validate_manifest

    path, manifest, weights, engines = prepared_cache
    assert (
        validate_manifest(
            path,
            weight_paths=weights,
            engine_paths=engines,
            tensorrt_version="10.7.0",
            compute_capability=(8, 6),
        )
        == manifest
    )


@pytest.mark.parametrize(
    "changed", ["weight", "engine", "trt", "gpu", "schema", "roi", "unvalidated"]
)
def test_prepared_manifest_rejects_changed_cache_or_missing_equivalence(prepared_cache, changed):
    from scripts.ditto_trt import validate_manifest

    path, manifest, weights, engines = prepared_cache
    kwargs = {"tensorrt_version": "10.7.0", "compute_capability": (8, 6)}
    if changed == "weight":
        weights["decoder"].write_bytes(b"different decoder weights")
    elif changed == "engine":
        engines["warp_head"].write_bytes(b"different compiled engine")
    elif changed == "trt":
        kwargs["tensorrt_version"] = "10.8.0"
    elif changed == "gpu":
        kwargs["compute_capability"] = (9, 0)
    elif changed == "schema":
        manifest["fingerprint"]["schema"] = -1
    elif changed == "roi":
        kwargs["decoder_roi"] = (128, 272, 384, 464)
    else:
        manifest["validation"]["passed"] = False
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError):
        validate_manifest(path, weight_paths=weights, engine_paths=engines, **kwargs)


def test_partial_decoder_requires_validated_source_identity_and_every_frame(tmp_path):
    from scripts.ditto_trt import sha256_file, validate_mouth_sources

    source = tmp_path / "standing.mp4"
    source.write_bytes(b"validated source")
    paths = {source.name: source}
    infos = [{"mouth_regions": [(256, 361, 78, 57)]}]
    manifest = {
        "validation": {
            "all_source_wave_regions_covered": True,
            "sources_sha256": {source.name: sha256_file(source)},
        }
    }
    validate_mouth_sources(manifest, infos, paths)
    with pytest.raises(ValueError, match="cover every"):
        validate_mouth_sources(manifest, [*infos, {"mouth_regions": [(256, 275, 78, 57)]}], paths)
    source.write_bytes(b"changed source")
    with pytest.raises(ValueError, match="sources changed"):
        validate_mouth_sources(manifest, infos, paths)
