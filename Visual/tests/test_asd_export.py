"""The Light-ASD exporter: shared softmax helper and strict checkpoint checks.

No model download and no real checkpoint here -- those live in the opt-in
parity check the report runs by hand against the cached upstream checkout.
"""

import hashlib

import numpy as np
import pytest

torch = pytest.importorskip("torch")

from torch import nn

from Visual.tools.export_light_asd import (
    export_probabilities,
    load_checkpoint_state,
    load_state_dict_strict,
    split_checkpoint,
)


def test_export_uses_two_class_probability():
    probs = export_probabilities(torch.tensor([[8.0, 9.0], [-8.0, -9.0]]))
    assert probs.tolist() == pytest.approx([0.7310586, 0.2689414])


def test_load_checkpoint_state_rejects_altered_sha256(tmp_path):
    path = tmp_path / "ckpt.model"
    torch.save({"model.x": torch.zeros(1)}, path)
    good_sha256 = hashlib.sha256(path.read_bytes()).hexdigest()

    with open(path, "ab") as f:
        f.write(b"\x00")  # corrupt after computing the expected hash

    with pytest.raises(ValueError, match="sha256"):
        load_checkpoint_state(str(path), expected_sha256=good_sha256)


def test_load_checkpoint_state_accepts_matching_sha256(tmp_path):
    path = tmp_path / "ckpt.model"
    torch.save({"model.x": torch.zeros(1)}, path)
    sha256 = hashlib.sha256(path.read_bytes()).hexdigest()

    state = load_checkpoint_state(str(path), expected_sha256=sha256)
    assert list(state.keys()) == ["model.x"]


def test_split_checkpoint_normalizes_one_leading_module_prefix():
    state = {
        "module.model.x": torch.zeros(1),
        "module.lossAV.FC.weight": torch.zeros(2, 128),
        "module.lossAV.FC.bias": torch.zeros(2),
        "module.lossV.FC.weight": torch.zeros(2, 128),  # training-only, ignored
    }
    asd_state, classifier_state = split_checkpoint(state)
    assert list(asd_state.keys()) == ["x"]
    assert set(classifier_state.keys()) == {"FC.weight", "FC.bias"}


def test_split_checkpoint_rejects_missing_classifier_weight():
    state = {"model.x": torch.zeros(1)}  # no lossAV.* at all
    with pytest.raises(ValueError, match="classifier"):
        split_checkpoint(state)


def test_load_state_dict_strict_rejects_missing_weight():
    classifier = nn.Linear(128, 2)
    with pytest.raises(ValueError, match="classifier"):
        load_state_dict_strict(classifier, {"weight": torch.zeros(2, 128)}, "classifier")  # no bias


def test_load_state_dict_strict_rejects_nonmatching_shape():
    classifier = nn.Linear(128, 2)
    bad = {"weight": torch.zeros(2, 64), "bias": torch.zeros(2)}
    with pytest.raises(ValueError, match="classifier"):
        load_state_dict_strict(classifier, bad, "classifier")


def test_split_checkpoint_rejects_unexpected_prefix():
    state = {
        "model.x": torch.zeros(1),
        "lossAV.FC.weight": torch.zeros(2, 128),
        "lossAV.FC.bias": torch.zeros(2),
        "somethingElse.y": torch.zeros(1),
    }
    with pytest.raises(ValueError, match="somethingElse"):
        split_checkpoint(state)
