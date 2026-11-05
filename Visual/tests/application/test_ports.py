"""The real models keep to the ports the loops rely on.

Structural, so nothing else notices when an adapter's method is renamed.
"""

import typing

import pytest

from Visual.application import ports
from Visual.infrastructure.depth.metric3d import DepthEstimator
from Visual.infrastructure.faces.scrfd import SCRFDFaceDetector
from Visual.infrastructure.faces.embedder import FaceEmbedder
from Visual.infrastructure.faces.bytetrack import ByteTrack
from Visual.infrastructure.faces.lips import LipReader
from Visual.infrastructure.person.yolo import PersonDetector
from Visual.infrastructure.spoof.minifasnet import SpoofDetector
from Visual.infrastructure.active_speaker.light_asd import LightASD


@pytest.mark.parametrize("port,adapter", [
    (ports.FaceDetector, SCRFDFaceDetector),
    (ports.Tracker, ByteTrack),
    (ports.Embedder, FaceEmbedder),
    (ports.SpoofChecker, SpoofDetector),
    (ports.DepthEstimator, DepthEstimator),
    (ports.PersonDetector, PersonDetector),
    (ports.LipReader, LipReader),
    (ports.ActiveSpeakerDetector, LightASD),
], ids=lambda v: v.__name__)
def test_adapter_has_every_member_of_its_port(port, adapter):
    missing = [m for m in typing.get_protocol_members(port) if not hasattr(adapter, m)]
    assert missing == []
