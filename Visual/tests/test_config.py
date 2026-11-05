"""Tests for AI.config — YAML override discovery, parsing, and precedence."""

import os
import sys
from pathlib import Path

import pytest
import yaml

from Visual.config import Config, _resolve_yaml_path


class TestResolveYamlPath:
    """Tests for _resolve_yaml_path() discovery logic."""

    def test_explicit_path_exists(self, tmp_path: Path) -> None:
        """When an explicit path points to an existing file, return it."""
        yaml_file = tmp_path / "my_config.yml"
        yaml_file.write_text("camera_id: 1")

        result = _resolve_yaml_path(str(yaml_file))
        assert result == str(yaml_file)

    def test_explicit_path_missing_raises(self) -> None:
        """When an explicit path does not exist, raise FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            _resolve_yaml_path("/nonexistent/path/config.yml")

    def test_env_var_points_to_valid_file(self, tmp_path: Path, monkeypatch) -> None:
        """JARVIS_CONFIG env var takes priority over other auto-discovery."""
        yaml_file = tmp_path / "env_config.yml"
        yaml_file.write_text("camera_id: 2")
        monkeypatch.setenv("JARVIS_CONFIG", str(yaml_file))

        result = _resolve_yaml_path()
        assert result == str(yaml_file)

    def test_env_var_set_but_file_missing(self, monkeypatch) -> None:
        """When JARVIS_CONFIG points to a missing file, skip to next source."""
        monkeypatch.setenv("JARVIS_CONFIG", "/nonexistent/c.yml")
        # With no CLI arg and no project root config.yml, returns None
        result = _resolve_yaml_path(search_project_root=False)
        assert result is None

    def test_cli_arg_config_flag(self, tmp_path: Path, monkeypatch) -> None:
        """--config <path> in sys.argv is discovered."""
        yaml_file = tmp_path / "cli_config.yml"
        yaml_file.write_text("camera_id: 3")
        monkeypatch.setattr(sys, "argv", ["main.py", "--config", str(yaml_file)])
        monkeypatch.delenv("JARVIS_CONFIG", raising=False)

        result = _resolve_yaml_path()
        assert result == str(yaml_file)

    def test_cli_arg_not_present(self, monkeypatch) -> None:
        """When --config is not in sys.argv, skip to next source."""
        monkeypatch.setattr(sys, "argv", ["main.py"])
        monkeypatch.delenv("JARVIS_CONFIG", raising=False)

        result = _resolve_yaml_path(search_project_root=False)
        assert result is None

    def test_project_root_fallback(self, tmp_path: Path, monkeypatch) -> None:
        """Fall back to config.yml in project root when env/CLI are unset."""
        monkeypatch.delenv("JARVIS_CONFIG", raising=False)
        monkeypatch.setattr(sys, "argv", ["main.py"])
        # Simulate a project root by creating a git repo marker
        (tmp_path / ".git").mkdir()
        config_yml = tmp_path / "config.yml"
        config_yml.write_text("camera_id: 4")

        # Walk up from a subdirectory inside the project
        subdir = tmp_path / "AI"
        subdir.mkdir()
        original_cwd = os.getcwd()
        try:
            os.chdir(subdir)
            result = _resolve_yaml_path()
            assert result == str(config_yml)
        finally:
            os.chdir(original_cwd)

    def test_nothing_found_returns_none(self, monkeypatch) -> None:
        """When no YAML is discoverable, return None."""
        monkeypatch.delenv("JARVIS_CONFIG", raising=False)
        monkeypatch.setattr(sys, "argv", ["main.py"])

        result = _resolve_yaml_path(search_project_root=False)
        assert result is None


class TestFromYaml:
    """Tests for Config.from_yaml() class method."""

    @staticmethod
    def _write_yaml(path: Path, data: dict) -> None:
        """Write a dict as YAML to *path*."""
        with open(path, "w") as f:
            yaml.dump(data, f)

    def test_no_yaml_found_returns_defaults(self) -> None:
        """When no YAML is discoverable, from_yaml() returns default Config."""
        cfg = Config.from_yaml()  # auto-discovery with nothing found
        assert cfg.camera_id == 0
        assert cfg.camera_width == 640
        assert cfg.scrfd_conf == 0.5
        assert cfg.spoof_enabled is True

    def test_explicit_path_applies_overrides(self, tmp_path: Path) -> None:
        """Values in the YAML file override the matching defaults."""
        yaml_file = tmp_path / "test.yml"
        self._write_yaml(yaml_file, {
            "camera_id": 2,
            "scrfd_conf": 0.8,
            "spoof_enabled": False,
        })

        cfg = Config.from_yaml(str(yaml_file))
        assert cfg.camera_id == 2
        assert cfg.scrfd_conf == 0.8
        assert cfg.spoof_enabled is False
        # Unspecified fields retain defaults
        assert cfg.camera_width == 640
        assert cfg.track_buffer == 15

    def test_unknown_keys_skipped(self, tmp_path: Path) -> None:
        """YAML keys not in __dataclass_fields__ are ignored."""
        yaml_file = tmp_path / "unknown.yml"
        self._write_yaml(yaml_file, {
            "camera_id": 3,
            "bogus_key": "should be ignored",
            "another_invalid": 42,
        })

        cfg = Config.from_yaml(str(yaml_file))
        assert cfg.camera_id == 3
        # The unknown keys should not cause errors or appear as attributes
        assert not hasattr(cfg, "bogus_key")
        assert not hasattr(cfg, "another_invalid")

    def test_empty_yaml_returns_defaults(self, tmp_path: Path) -> None:
        """An empty or all-comments YAML file yields default Config."""
        yaml_file = tmp_path / "empty.yml"
        yaml_file.write_text("# just a comment\n")

        cfg = Config.from_yaml(str(yaml_file))
        assert cfg.camera_id == 0
        assert cfg.camera_width == 640

    def test_malformed_yaml_raises_valueerror(self, tmp_path: Path) -> None:
        """A syntactically invalid YAML file raises ValueError."""
        yaml_file = tmp_path / "bad.yml"
        yaml_file.write_text("camera_id: [unclosed\n")

        with pytest.raises(ValueError, match="YAML"):
            Config.from_yaml(str(yaml_file))

    def test_tuple_field_from_yaml_list(self, tmp_path: Path) -> None:
        """A YAML list is coerced to a tuple for tuple-typed fields."""
        yaml_file = tmp_path / "tuple.yml"
        self._write_yaml(yaml_file, {
            "scrfd_input_size": [640, 480],
            "metric3d_depth_range": [0.2, 8.0],
        })

        cfg = Config.from_yaml(str(yaml_file))
        assert cfg.scrfd_input_size == (640, 480)
        assert isinstance(cfg.scrfd_input_size, tuple)
        assert cfg.metric3d_depth_range == (0.2, 8.0)
        assert isinstance(cfg.metric3d_depth_range, tuple)

    def test_type_mismatch_falls_back_to_default(self, tmp_path: Path, capsys) -> None:
        """When a YAML value cannot be coerced, warn and use the default."""
        yaml_file = tmp_path / "badtype.yml"
        self._write_yaml(yaml_file, {
            "camera_id": "not_an_int",
            "scrfd_conf": [1, 2, 3],  # list instead of float
        })

        cfg = Config.from_yaml(str(yaml_file))
        # Falls back to defaults for the bad values
        assert cfg.camera_id == 0
        assert cfg.scrfd_conf == 0.5

        captured = capsys.readouterr()
        assert "camera_id" in captured.out or "camera_id" in captured.err

    def test_use_calibration_false_disables_calibration(self, tmp_path: Path) -> None:
        """When use_calibration is false in YAML, __post_init__ skips loading."""
        yaml_file = tmp_path / "nocal.yml"
        self._write_yaml(yaml_file, {"use_calibration": False})

        cfg = Config.from_yaml(str(yaml_file))
        # use_calibration flag is stored in the Config instance
        assert cfg.use_calibration is False

    def test_default_constructor_still_works(self) -> None:
        """The no-arg Config() constructor is unchanged."""
        cfg = Config()
        assert cfg.camera_id == 0
        assert cfg.camera_width == 640
        assert cfg.scrfd_conf == 0.5
        assert isinstance(cfg.intrinsics, tuple)
        assert len(cfg.intrinsics) == 4


class TestIntervalValidation:
    """P4/P5: intervals are real, validated seconds — not silently clamped.

    `spoof_interval_sec` used to be overridden by `max(1.0, ...)` inside the
    worker, so configuring 0.5 quietly ran at 1.0. `depth_every_n_frames`
    never counted frames at all. Both now mean what they say, and nonsense
    values raise instead of being papered over.
    """

    def test_spoof_interval_is_not_clamped_to_one_second(self):
        import dataclasses
        from Visual.config import Config
        cfg = dataclasses.replace(Config(), spoof_interval_sec=0.5)
        assert cfg.spoof_interval_sec == 0.5

    def test_depth_interval_is_seconds(self):
        from Visual.config import Config
        assert Config().depth_interval_sec == 1.0

    def test_frame_count_knob_is_gone(self):
        from Visual.config import Config
        assert not hasattr(Config(), "depth_every_n_frames")

    @pytest.mark.parametrize(
        "field,bad",
        [
            ("spoof_interval_sec", 0),
            ("spoof_interval_sec", -0.5),
            ("depth_interval_sec", 0),
            ("depth_interval_sec", -1),
            ("track_max_fps", -5),
        ],
    )
    def test_rejects_nonsense_values(self, field, bad):
        import dataclasses
        from Visual.config import Config
        with pytest.raises(ValueError, match=field):
            dataclasses.replace(Config(), **{field: bad})

    def test_zero_fps_is_allowed_as_cap_disable(self):
        import dataclasses
        from Visual.config import Config
        assert dataclasses.replace(Config(), track_max_fps=0).track_max_fps == 0


class TestActiveSpeakerConfig:
    def test_defaults_are_off_and_weights_live_outside_the_checkout(self):
        cfg = Config()
        assert cfg.asd_provider == "none"
        assert cfg.asd_model_path == os.path.expanduser(
            "~/.cache/openjarvis/light_asd/light_asd.onnx")
        assert cfg.asd_audio_offset_secs == 0.0

    @pytest.mark.parametrize("value", [-1.0, -0.4, 0.4, 1.0])
    def test_offset_within_one_second_is_accepted(self, value):
        import dataclasses
        assert dataclasses.replace(Config(), asd_audio_offset_secs=value).asd_audio_offset_secs == value

    @pytest.mark.parametrize("field,bad", [
        ("asd_provider", "light-asd"),
        ("asd_provider", "LightASD"),
        ("asd_audio_offset_secs", 1.01),
        ("asd_audio_offset_secs", -1.5),
        ("asd_audio_offset_secs", float("nan")),
        ("asd_audio_offset_secs", float("inf")),
    ])
    def test_rejects_bad_asd_values(self, field, bad):
        import dataclasses
        with pytest.raises(ValueError, match=field):
            dataclasses.replace(Config(), **{field: bad})

    def test_asd_keys_load_from_yaml(self, tmp_path: Path) -> None:
        yaml_file = tmp_path / "config.yml"
        yaml_file.write_text("asd_provider: light_asd\nasd_model_path: /tmp/m.onnx\n"
                             "asd_audio_offset_secs: -0.12\n")
        cfg = Config.from_yaml(str(yaml_file))
        assert (cfg.asd_provider, cfg.asd_model_path, cfg.asd_audio_offset_secs) == (
            "light_asd", "/tmp/m.onnx", -0.12)
