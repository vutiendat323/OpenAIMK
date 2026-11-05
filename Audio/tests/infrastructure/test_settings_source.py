"""Where speaker settings come from: an explicit file and table, never the env."""

import pytest

from audio.domain.settings import SpeakerSettings, settings_from_mapping
from audio.infrastructure.config.toml_store import load_speaker_settings


def test_a_missing_file_gives_the_defaults(tmp_path):
    assert load_speaker_settings(tmp_path / "absent.toml") == SpeakerSettings()


def test_the_environment_is_not_read(tmp_path, monkeypatch):
    preset = tmp_path / "preset.toml"
    preset.write_text("[voice.speaker]\nenabled = true\n")
    monkeypatch.setenv("OPENJARVIS_CONFIG", str(preset))
    assert load_speaker_settings(None) == SpeakerSettings()


@pytest.mark.parametrize(
    "body,code",
    [
        ("voice = 1\n", "voice_config_must_be_a_table"),
        ("[voice]\nspeaker = 1\n", "voice_speaker_config_must_be_a_table"),
    ],
)
def test_a_non_table_section_is_refused(tmp_path, body, code):
    preset = tmp_path / "preset.toml"
    preset.write_text(body)
    with pytest.raises(ValueError, match=code):
        load_speaker_settings(preset)


def test_another_table_can_hold_the_settings(tmp_path):
    preset = tmp_path / "app.toml"
    preset.write_text("[audio.speaker]\nenabled = true\nbargein_accept_frames = 5\n")
    assert load_speaker_settings(preset, table=("audio", "speaker")) == SpeakerSettings(
        enabled=True, bargein_accept_frames=5
    )


def test_mapping_validation_is_the_same_without_a_file():
    assert settings_from_mapping({}) == SpeakerSettings()
    with pytest.raises(ValueError, match="voice_speaker_enabled_must_be_a_boolean"):
        settings_from_mapping({"enabled": "yes"})


@pytest.mark.parametrize("path", ["", "   "])
def test_a_blank_path_gives_the_defaults(path):
    assert load_speaker_settings(path) == SpeakerSettings()
