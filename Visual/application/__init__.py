"""Application: the three jobs the service does, and what they need.

Track faces, check liveness, measure presence -- each a loop that reads the
latest frame and reports to the Scene -- plus the frame hand-off between
threads and the ports (Protocols) every model must satisfy.  Imports the
domain and the configuration; never infrastructure or presentation.
"""
