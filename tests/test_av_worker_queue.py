"""Exercise the actual worker IPC queue without loading perception models."""

import json
import subprocess
import sys


def test_fusion_telemetry_never_evicts_an_approved_audio_packet():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            """
import json,sys
from trendcoffee.av_worker import Worker
worker=Worker()
for n in range(16):worker.output.put_nowait({'type':'pcm','n':n})
worker.offer({'type':'fusion','locked':True})
events=[]
while not worker.output.empty():events.append(worker.output.get_nowait())
print(json.dumps([item['n'] for item in events if item['type']=='pcm']),file=sys.__stdout__)
""",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    assert json.loads(result.stdout) == list(range(16))


def test_post_handshake_check_waits_through_a_transient_missing_camera_frame():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            """
import asyncio,json,sys
import trendcoffee.av_worker as module
async def main():
 worker=module.Worker();worker.generation=1
 checks=iter([False,False,True]);events=[]
 worker.media_ready=lambda:next(checks,True)
 module.write=events.append
 await worker.command({'type':'check_ready','generation':1,'request_id':7})
 print(json.dumps(events),file=sys.__stdout__)
asyncio.run(main())
""",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    assert json.loads(result.stdout) == [
        {"type": "session_ready", "generation": 1, "request_id": 7}
    ]


def test_a_media_wait_names_every_condition_that_is_missing():
    """'Đang chờ camera ... A-V' must leave evidence of which check failed."""
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            """
import json,sys
import trendcoffee.av_worker as module
class Task:
 def __init__(s,done): s.d=done
 def done(s): return s.d
class Stream: _worker=Task(False); _releaser=Task(True)
class Bridge: ready=False; _terminal=True; _closed=False; _version=2
class Faces:
 def fresh(s,now,max_age=1.0): return True
 def anchor(s,now,m): return None
 def tracks_at(s,now): return [{'track_id':3,'distance_m':1.4,'is_live':True}]
w=module.Worker()
print(json.dumps(w.media_missing(100.0)),file=sys.__stdout__)
w.stream=Stream(); w.bridge=Bridge(); w.faces=Faces()
print(json.dumps(w.media_missing(100.0)),file=sys.__stdout__)
print(json.dumps(w.media_ready()),file=sys.__stdout__)
print(w.media_report(100.0),file=sys.__stdout__)
""",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    empty, missing, ready, report = result.stdout.strip().split("\n")
    assert json.loads(empty) == ["no_stream", "asd_bridge_not_ready", "no_faces"]
    assert json.loads(missing) == [
        "asd_bridge_not_ready",
        "no_live_face_within_0.8m",
        "fusion_tasks_stopped",
    ]
    assert json.loads(ready) is False
    assert "asd_bridge_not_ready" in report and "terminal=True" in report
    assert "nearest 1.40 m" in report and "faces 1" in report


def test_a_failed_begin_leaves_its_traceback_in_the_worker_log():
    """The worker used to answer `error` and say nothing; the cause was never visible."""
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            """
import asyncio,json,sys
import trendcoffee.av_worker as module
async def main():
 worker=module.Worker();events=[]
 async def boom(message): raise ValueError('begin exploded')
 worker.begin=boom
 module.write=events.append
 await worker.command({'type':'begin','generation':4,'request_id':9,'session_id':'s'})
 print(json.dumps(events),file=sys.__stdout__)
asyncio.run(main())
""",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    assert json.loads(result.stdout) == [{"type": "error", "generation": 4, "request_id": 9}]
    assert "[av_worker] begin failed" in result.stderr
    assert "ValueError: begin exploded" in result.stderr
