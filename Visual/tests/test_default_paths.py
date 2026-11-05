"""Every file the configuration defaults to exists in the checkout.

The guard for moving weights or calibration: a default that no longer
resolves degrades silently at runtime (a model is skipped, the spoof weights
are re-downloaded, intrinsics fall back to guesses).
"""

import os

import pytest

from Visual.config import Config
from Visual.infrastructure.spoof.minifasnet import SpoofDetector, _PAD_MODELS

CFG = Config()


@pytest.mark.parametrize("key", [
    "scrfd_model", "embedder_model_path", "person_model", "calibration_path",
])
def test_config_default_exists(key):
    assert os.path.isfile(getattr(CFG, key)), getattr(CFG, key)


@pytest.mark.parametrize("spec", _PAD_MODELS, ids=lambda s: s.filename)
def test_spoof_weights_exist(spec):
    path = os.path.join(SpoofDetector._WEIGHTS_DIR, spec.filename)
    assert os.path.isfile(path), path
