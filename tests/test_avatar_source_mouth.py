"""Source preparation must close lips without replacing the face or chin."""

import numpy as np
import pytest

from trendcoffee import avatar_whole_face as face
from trendcoffee.avatar_appearance import register_source

RING = [61, 146, 91, 181, 84, 17, 314, 405, 321, 375, 291, 409, 270, 269, 267, 0, 37, 39, 40, 185]


def points(opened):
    p = np.full((478, 2), [256, 250], np.float32)
    p[33], p[263] = [190, 220], [320, 220]
    angle = np.linspace(0, 2 * np.pi, len(RING), endpoint=False)
    p[RING] = np.column_stack((256 + 40 * np.cos(angle), 330 + opened * np.sin(angle)))
    p[61], p[291] = [216, 330], [296, 330]
    p[13], p[14] = [256, 330 - opened / 2], [256, 330 + opened / 2]
    return p


def test_closed_source_changes_only_the_mouth_not_eyes_nose_chin_or_neck():
    donor = np.full((512, 512, 3), 80, np.uint8)
    donor[329:332, 226:286] = 50
    original = donor.copy()
    original[315:347, 228:284] = 240
    untouched = original.copy()
    prepared = face.prepare_closed_mouth(original, points(25), donor, points(2))
    np.testing.assert_array_equal(prepared[:295], original[:295])
    np.testing.assert_array_equal(prepared[375:], original[375:])
    np.testing.assert_array_equal(prepared[:, :205], original[:, :205])
    assert prepared[320:340, 240:272].mean() < 130
    np.testing.assert_array_equal(original, untouched)


def test_donor_skin_around_the_lips_is_not_pasted_only_the_lips_are():
    donor = np.full((512, 512, 3), 80, np.uint8)
    donor[340:352, 216:296] = 130  # pale halo of the donor frame, below its closed lips
    donor[329:332, 226:286] = 50
    original = np.full((512, 512, 3), 80, np.uint8)
    original[315:347, 228:284] = 240
    prepared = face.prepare_closed_mouth(original, points(25), donor, points(2))
    assert abs(int(prepared[346, 256, 0]) - 80) <= 4
    assert prepared[330, 256, 0] < 70


def test_source_eye_spacing_not_a_pursed_speech_width_sets_the_closed_lip_width():
    donor = np.full((512, 512, 3), 80, np.uint8)
    donor[329:332, 226:286] = 30
    target = points(2)
    target[61], target[291] = [240, 330], [272, 330]
    prepared = face.prepare_closed_mouth(np.full_like(donor, 80), target, donor, points(2))
    assert prepared[330, 230, 0] < 40
    assert prepared[330, 280, 0] < 40


def test_speech_expression_keeps_source_anatomy_and_eyes_even_if_prediction_drifts():
    source = np.full((1, 63), 0.1, np.float32)
    voice = np.full((1, 63), 2.0, np.float32)
    rest = np.zeros((1, 63), np.float32)
    result = face.speech_expression(source, voice, rest, 0.5, 1).reshape(21, 3)
    nonlip = sorted(set(range(21)) - set(face.LIPS))
    np.testing.assert_array_equal(result[nonlip], source.reshape(21, 3)[nonlip])
    assert (result[face.LIPS] != source.reshape(21, 3)[face.LIPS]).any()


def test_lip_width_factor_tames_sideways_and_forward_lip_motion_not_opening():
    source = np.zeros((1, 63), np.float32)
    voice = np.zeros((1, 63), np.float32)
    rest = np.zeros((1, 63), np.float32)
    voice.reshape(21, 3)[face.LIPS] = [
        0.04,
        0.10,
        0.06,
    ]  # pursing: sideways and forward, plus opening
    plain = face.speech_expression(source, voice, rest, 1.0, 1).reshape(21, 3)[face.LIPS]
    tamed = face.speech_expression(source, voice, rest, 1.0, 1, lip_width=0.5).reshape(21, 3)[
        face.LIPS
    ]
    np.testing.assert_allclose(tamed[:, 0], plain[:, 0] * 0.5)
    np.testing.assert_allclose(tamed[:, 2], plain[:, 2] * 0.5)
    np.testing.assert_allclose(tamed[:, 1], plain[:, 1])


def test_silence_returns_the_current_closed_source_expression_exactly():
    source = np.arange(63, dtype=np.float32).reshape(1, 63)
    result = face.speech_expression(source, np.ones_like(source), np.zeros_like(source), 0.5, 0)
    np.testing.assert_array_equal(result, source)


def registrar_fixture(fail=False):
    donor = np.full((512, 512, 3), 80, np.uint8)
    donor[329:332, 226:286] = 50
    opened = donor.copy()
    opened[315:347, 228:284] = 240
    captured = []

    class Source:
        calls = 0

        def landmark478(self, image):
            p = points(2 if self.calls == 0 else 25)
            self.calls += 1
            return np.column_stack([p / 512, np.zeros(478)])[None]

        @staticmethod
        def _img_crop_to_bchw256(image):
            captured.append(image.copy())
            return image

    class Registrar:
        source2info = Source()

        def __call__(self, *args, **kwargs):
            for image in (donor, opened):
                self.source2info.landmark478(image)
                self.source2info._img_crop_to_bchw256(image)
                if fail:
                    raise RuntimeError("fixture registration failed")
            return {"img_rgb_lst": [donor, opened]}

    return Registrar(), captured, opened


def test_registration_prepares_the_actual_model_input_and_keeps_the_body_source_untouched():
    registrar, captured, opened = registrar_fixture()
    encode = registrar.source2info._img_crop_to_bchw256
    info = register_source(registrar, "source.mp4", close_mouth=True)
    assert captured[1][320:340, 240:272].mean() < 130
    np.testing.assert_array_equal(captured[1][:295], opened[:295])
    np.testing.assert_array_equal(captured[1][375:], opened[375:])
    np.testing.assert_array_equal(info["img_rgb_lst"][1], opened)
    assert registrar.source2info._img_crop_to_bchw256 is encode


def test_failed_preparation_restores_the_source_encoder_and_landmarker():
    registrar, _, _ = registrar_fixture(fail=True)
    encode = registrar.source2info._img_crop_to_bchw256
    detector = registrar.source2info.landmark478
    with pytest.raises(RuntimeError, match="fixture registration failed"):
        register_source(registrar, "source.mp4", close_mouth=True)
    assert registrar.source2info._img_crop_to_bchw256 is encode
    assert registrar.source2info.landmark478 == detector
