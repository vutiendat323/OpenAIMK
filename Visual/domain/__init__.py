"""Domain: what the kiosk believes about the people in front of it.

The Scene, its smoothing, the kiosk event, and the geometry that turns
landmarks and depth into metres.  Imports only the standard library, numpy and
OpenCV used as mathematics (solvePnP, projectPoints) -- no camera or file I/O,
no model loading, no threads beyond the Scene's own lock, nothing else from
the service.
"""
