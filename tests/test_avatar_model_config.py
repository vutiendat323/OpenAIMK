from types import SimpleNamespace

import pytest

from scripts.livetalking_local import configure_avatar


def test_manifest_selects_musetalk_before_loading_the_avatar_and_batch():
    opt = SimpleNamespace(model="wav2lip", batch_size=4, avatar_id="sample", customopt=[{}])
    configure_avatar(opt, {"engine": "musetalk", "batch_size": 8, "avatar_id": "neutral_muse"})
    assert (opt.model, opt.batch_size, opt.avatar_id, opt.customopt) == (
        "musetalk",
        8,
        "neutral_muse",
        [],
    )


def test_legacy_avatar_keeps_its_requested_batch_and_uses_wav2lip():
    opt = SimpleNamespace(model="musetalk", batch_size=4, avatar_id="sample", customopt=[{}])
    configure_avatar(opt, {"avatar_id": "legacy"})
    assert (opt.model, opt.batch_size, opt.avatar_id) == ("wav2lip", 4, "legacy")


@pytest.mark.parametrize("fields", [{"engine": "unknown"}, {"batch_size": 0}, {"batch_size": True}])
def test_invalid_engine_configuration_is_rejected_before_model_loading(fields):
    opt = SimpleNamespace(batch_size=4)
    with pytest.raises(ValueError):
        configure_avatar(opt, {"avatar_id": "neutral", **fields})
