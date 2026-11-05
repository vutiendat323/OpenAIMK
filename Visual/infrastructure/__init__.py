"""Infrastructure: the concrete technologies behind the application's ports.

SCRFD, ByteTrack, the ReID embedder, MiniFASNet, Metric3D, YOLO and the
camera, one package per technology.  Imports the domain (and third-party
libraries) only; satisfies the ports structurally, so it never imports the
application, the presentation or the configuration.
"""
