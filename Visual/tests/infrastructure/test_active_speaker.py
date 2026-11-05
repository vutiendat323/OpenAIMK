"""Light-ASD runtime provider: audio preprocessing and the ONNX port.

python_speech_features is not part of the ordinary test environment (it is
installed only into an isolated --target dir per requirements-asd.txt);
tests that need it are importorskip'd rather than always-skipped.  LightASD's
own tests fake the ONNX session, so no model file or torch is needed for them,
but they still live in this module (so the psf skip also covers them, since
LightASD.predict always calls prepare_audio).
"""

import json

import numpy as np
import pytest

pytest.importorskip("python_speech_features")

from python_speech_features import mfcc

from Visual.infrastructure.active_speaker.light_asd import LightASD, _sha256, prepare_audio
import Visual.infrastructure.active_speaker.light_asd as light_asd_module


def test_audio_features_have_the_exported_shape():
    pcm = (np.sin(np.arange(16000) * 0.1) * 1000).astype(np.int16)
    features = prepare_audio(pcm)
    assert features.shape == (1, 100, 13)
    assert features.dtype == np.float32 and np.isfinite(features).all()


def test_audio_features_match_mfcc_on_int16_scale_values():
    pcm = (np.sin(np.arange(16000) * 0.1) * 5000).astype(np.int16)

    expected = mfcc(np.concatenate([pcm.astype(np.float64), np.zeros(240)]),
                     16000, numcep=13, winlen=0.025, winstep=0.01)
    assert np.allclose(prepare_audio(pcm)[0], expected, atol=1e-4)

    # A prepare_audio that divided by 32768 first would match this instead.
    normalized = mfcc(np.concatenate([pcm.astype(np.float64) / 32768.0, np.zeros(240)]),
                       16000, numcep=13, winlen=0.025, winstep=0.01)
    assert not np.allclose(prepare_audio(pcm)[0], normalized)


# ---------------------------------------------------------------------------
# LightASD: fake ONNX session, no model file or torch needed.
# ---------------------------------------------------------------------------

class _FakeIO:
    def __init__(self, name):
        self.name = name


class _FakeSession:
    def __init__(self, output, providers=None):
        self._output = output
        self._providers = providers or []

    def get_providers(self):
        return [p[0] if isinstance(p, tuple) else p for p in self._providers]

    def get_inputs(self):
        return [_FakeIO("audio"), _FakeIO("visual")]

    def get_outputs(self):
        return [_FakeIO("probabilities")]

    def run(self, output_names, feed):
        return [self._output]


def _write_model_and_manifest(tmp_path):
    model_path = tmp_path / "light_asd.onnx"
    model_path.write_bytes(b"fake onnx bytes")
    manifest_path = tmp_path / "light_asd.onnx.json"
    manifest_path.write_text(json.dumps({"artifact_sha256": _sha256(str(model_path))}))
    return str(model_path)


def _patch_session(monkeypatch, output, capture=None):
    def fake_inference_session(path, sess_options=None, providers=None):
        if capture is not None:
            capture["sess_options"] = sess_options
            capture["providers"] = providers
        return _FakeSession(output, providers)
    monkeypatch.setattr(light_asd_module.ort, "InferenceSession", fake_inference_session)


_GOOD_PCM = np.zeros(16000, dtype=np.int16)
_GOOD_CROPS = np.zeros((25, 112, 112), dtype=np.uint8)
_GOOD_OUTPUT = np.linspace(0.1, 0.9, 25).astype(np.float32)


def test_predict_returns_25_finite_probabilities(tmp_path, monkeypatch):
    _patch_session(monkeypatch, _GOOD_OUTPUT)
    model = LightASD(_write_model_and_manifest(tmp_path))
    out = model.predict(_GOOD_PCM, _GOOD_CROPS)
    assert out.shape == (25,) and out.dtype == np.float32
    assert np.allclose(out, _GOOD_OUTPUT)


def test_predict_rejects_bad_pcm_shape(tmp_path, monkeypatch):
    _patch_session(monkeypatch, _GOOD_OUTPUT)
    model = LightASD(_write_model_and_manifest(tmp_path))
    with pytest.raises(ValueError):
        model.predict(np.zeros(8000, dtype=np.int16), _GOOD_CROPS)


def test_predict_rejects_bad_pcm_dtype(tmp_path, monkeypatch):
    _patch_session(monkeypatch, _GOOD_OUTPUT)
    model = LightASD(_write_model_and_manifest(tmp_path))
    with pytest.raises(ValueError):
        model.predict(np.zeros(16000, dtype=np.float32), _GOOD_CROPS)


def test_predict_rejects_bad_crops_shape(tmp_path, monkeypatch):
    _patch_session(monkeypatch, _GOOD_OUTPUT)
    model = LightASD(_write_model_and_manifest(tmp_path))
    with pytest.raises(ValueError):
        model.predict(_GOOD_PCM, np.zeros((25, 56, 56), dtype=np.uint8))


def test_predict_rejects_bad_crops_dtype(tmp_path, monkeypatch):
    _patch_session(monkeypatch, _GOOD_OUTPUT)
    model = LightASD(_write_model_and_manifest(tmp_path))
    with pytest.raises(ValueError):
        model.predict(_GOOD_PCM, np.zeros((25, 112, 112), dtype=np.float32))


def test_predict_rejects_nan_output(tmp_path, monkeypatch):
    bad = _GOOD_OUTPUT.copy()
    bad[0] = np.nan
    _patch_session(monkeypatch, bad)
    model = LightASD(_write_model_and_manifest(tmp_path))
    with pytest.raises(ValueError):
        model.predict(_GOOD_PCM, _GOOD_CROPS)


def test_predict_rejects_out_of_range_output(tmp_path, monkeypatch):
    bad = _GOOD_OUTPUT.copy()
    bad[0] = 1.5
    _patch_session(monkeypatch, bad)
    model = LightASD(_write_model_and_manifest(tmp_path))
    with pytest.raises(ValueError):
        model.predict(_GOOD_PCM, _GOOD_CROPS)


def test_predict_rejects_wrong_length_output(tmp_path, monkeypatch):
    _patch_session(monkeypatch, _GOOD_OUTPUT[:24])
    model = LightASD(_write_model_and_manifest(tmp_path))
    with pytest.raises(ValueError):
        model.predict(_GOOD_PCM, _GOOD_CROPS)


def test_missing_manifest_raises(tmp_path):
    model_path = tmp_path / "light_asd.onnx"
    model_path.write_bytes(b"fake onnx bytes")
    with pytest.raises(FileNotFoundError):
        LightASD(str(model_path))


def test_missing_mfcc_dependency_fails_at_load_not_first_inference(tmp_path, monkeypatch):
    # A load failure makes main mark ASD unavailable; a first-inference failure
    # would have reported "ready" to the socket owner first.
    import sys
    model_path = tmp_path / "light_asd.onnx"
    model_path.write_bytes(b"fake onnx bytes")
    (tmp_path / "light_asd.onnx.json").write_text(
        json.dumps({"artifact_sha256": _sha256(str(model_path))}))
    monkeypatch.setitem(sys.modules, "python_speech_features", None)
    monkeypatch.setattr(light_asd_module.ort, "InferenceSession",
                        lambda *a, **k: pytest.fail("session built without MFCC dependency"))
    with pytest.raises(ImportError):
        LightASD(str(model_path))


def test_manifest_sha256_mismatch_raises(tmp_path):
    model_path = tmp_path / "light_asd.onnx"
    model_path.write_bytes(b"fake onnx bytes")
    (tmp_path / "light_asd.onnx.json").write_text(json.dumps({"artifact_sha256": "not-the-hash"}))
    with pytest.raises(ValueError):
        LightASD(str(model_path))


def test_session_uses_cpu_provider_and_single_thread(tmp_path, monkeypatch, capsys):
    capture = {}
    _patch_session(monkeypatch, _GOOD_OUTPUT, capture=capture)
    LightASD(_write_model_and_manifest(tmp_path))
    assert capture["providers"] == ["CPUExecutionProvider"]
    assert capture["sess_options"].intra_op_num_threads == 1
    assert capture["sess_options"].inter_op_num_threads == 1
    assert capsys.readouterr().out == "[asd] Light-ASD on CPUExecutionProvider\n"


def test_cuda_device_asks_for_cuda_without_tf32_then_cpu(tmp_path, monkeypatch, capsys):
    capture = {}
    _patch_session(monkeypatch, _GOOD_OUTPUT, capture=capture)
    model = LightASD(_write_model_and_manifest(tmp_path), device="cuda")
    assert capture["providers"] == [("CUDAExecutionProvider", {"use_tf32": 0}),
                                    "CPUExecutionProvider"]
    assert capsys.readouterr().out == "[asd] Light-ASD on CUDAExecutionProvider\n"
    assert np.allclose(model.predict(_GOOD_PCM, _GOOD_CROPS), _GOOD_OUTPUT)


def test_cuda_device_loads_cuda_libraries_before_the_session(tmp_path, monkeypatch):
    # Without torch imported first, ORT could not find libcublasLt and fell
    # back to a 1-thread CPU at ~150 ms per window (2026-09-28 replay).
    calls = []
    monkeypatch.setattr(light_asd_module.ort, "preload_dlls", lambda: calls.append("preload"),
                        raising=False)
    _patch_session(monkeypatch, _GOOD_OUTPUT)
    LightASD(_write_model_and_manifest(tmp_path), device="cuda")
    assert calls == ["preload"]


def test_cuda_requested_but_cpu_granted_fails_loudly(tmp_path, monkeypatch):
    monkeypatch.setattr(light_asd_module.ort, "preload_dlls", lambda: None, raising=False)

    def cpu_only(path, sess_options=None, providers=None):
        return _FakeSession(_GOOD_OUTPUT, ["CPUExecutionProvider"])

    monkeypatch.setattr(light_asd_module.ort, "InferenceSession", cpu_only)
    with pytest.raises(RuntimeError, match="CUDA"):
        LightASD(_write_model_and_manifest(tmp_path), device="cuda")
