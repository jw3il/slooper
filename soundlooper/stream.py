import atexit
import logging
from threading import Lock
import collections
from typing import Optional, Tuple, Union
import numpy as np
import sounddevice as sd

from viztracer import VizTracer, get_tracer
import yaml
from soundlooper.recording import Recording

from soundlooper.valuestats import ValueStats
from timeit import default_timer as timer

from soundlooper.recording import State


if __debug__:
    callback_thread_added = False

# store stream and recordings as global variables
stream = None
recordings = collections.defaultdict(lambda: Recording())
duration_stats = ValueStats(capacity=100, dtype=float)

# lock for the recordings
lock = Lock()


def callback(data_in: np.ndarray, data_out: np.ndarray, frames: int, time, status: sd.CallbackFlags):
    if __debug__:
        global callback_thread_added
        if not callback_thread_added and get_tracer() is not None:
            get_tracer().enable_thread_tracing()
            callback_thread_added = True
    
    global recordings, lock

    if status:
        logging.warning(status)

    start = timer()

    # add recordings 
    data_out.fill(0)
    with lock:
        for r in recordings.values():
            if r.state == State.Record:
                r.record(data_in)
            elif r.state == State.Loop:
                r.loop(data_out)

    duration = timer() - start
    duration_stats.insert(duration)


def get_devices_list():
    return str(sd.query_devices()).split("\n")


def restart_sounddevice():
    sd._terminate()
    sd._initialize()


def search_device(name: Union[int, str], kind: Optional[str] = None):
    logging.info(f"Trying to find device containing '{name}' (kind {kind})")
    try:        
        search_result = sd.query_devices(name, kind)
        return search_result['name']
    except:
        raise ValueError(f"Could not find device with name containing '{name}'.\n"
                        f"Available devices:\n {sd.query_devices()}")


def stream_start(device: Union[int, str, Tuple[Union[int, str], Union[int, str]]], latency='high', channels=1):
    global stream, recordings
    if stream is not None:
        return None

    # restart sounddevice to reload available devices
    restart_sounddevice()

    if isinstance(device, (list, tuple)):
        stream_device = (
            search_device(device[0], kind='input'),
            search_device(device[1], kind='output')
        )
    else:
        stream_device = (
            search_device(device, kind='input'),
            search_device(device, kind='output')
        )
    
    logging.info("Using devices")
    logging.info(f"> Input: {stream_device[0]}")
    logging.info(f"> Output: {stream_device[1]}")

    if __debug__:
        logging.warning("Debug mode is enabled (__debug__).")

    stream = sd.Stream(callback=callback, device=stream_device, latency=latency, channels=channels, dtype='float32')
    stream.start()
    logging.info("Started stream")


def stream_close():
    global stream
    if stream is not None:
        stream.stop()
        stream.close()
        logging.info("Closed stream")
        stream = None


def get_stream_info_dict():
    global stream, duration_stats
    
    info = {
        'active': False if stream is None else stream.active,
        'samplerate': 0 if stream is None else stream.samplerate,
        'device': -1 if stream is None else stream.device,
        'duration_stats': duration_stats.get_stats(),
    }

    if stream is None or not stream.active:
        info['debug'] = get_devices_list()

    return info


def load_config():
    with open("config.yml", "r") as f:
        return yaml.load(f, Loader=yaml.Loader)

# make sure to properly close stream at exit
atexit.register(stream_close)

if __name__ == '__main__':
    logging.basicConfig(format="%(asctime)s %(message)s", level=logging.DEBUG)
    cfg = load_config()

    if __debug__:
        # start tracer
        tracer = VizTracer()
        tracer.start()
        tracer.enable_thread_tracing()

    stream_start(device=cfg["device"])

    # record for a few seconds
    logging.info("Record")
    recordings["a"].state = State.Record
    sd.sleep(int(1000 * 5))

    # play it back two times
    logging.info("Playback")
    recordings["a"].state = State.Loop
    sd.sleep(int(1000 * 10))
    sd.stop()
    
    if __debug__:
        # save tracer records
        tracer.stop()
        tracer.save()
