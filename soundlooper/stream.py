import atexit
import logging
from threading import Lock
import collections
import time
from typing import Tuple, Union
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


def search_device(name: Union[int, str], search_timeout: float):
    search_start_time = timer()
    logging.info(f"Trying to find device containing '{name}'")
    while timer() - search_start_time < search_timeout:
        try:
            search_result = sd.query_devices(name)
            return search_result['name']
        except ValueError:
            # could not find device, try again later
            time.sleep(0.1)
        except sd.PortAudioError:
            break

    raise ValueError(f"Could not find device with name containing '{name}'.\n"
                     f"Available devices:\n {sd.query_devices()}")


def stream_start(device: Union[int, str, Tuple[Union[int, str], Union[int, str]]], search_timeout=5, latency='high', channels=1):
    global stream, recordings
    if stream is not None:
        return None

    # make sure that the specified devices exist or search device by substring
    if isinstance(device, (list, tuple)):
        device = (
            search_device(device[0], search_timeout),
            search_device(device[1], search_timeout)
        )
    else:
        found_device = search_device(device, search_timeout)
        device = (
            found_device,
            found_device
        )

    logging.info("Using devices")
    logging.info(f"> Input: {device[0]}")
    logging.info(f"> Output: {device[1]}")

    if __debug__:
        logging.warning("Debug mode is enabled (__debug__).")

    stream = sd.Stream(callback=callback, device=device, latency=latency, channels=channels, dtype='float32')
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
    return {
        'active': False if stream is None else stream.active,
        'samplerate': 0 if stream is None else stream.samplerate,
        'device': -1 if stream is None else stream.device,
        'duration_stats': duration_stats.get_stats(),
        'debug': get_devices_list()
    }


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
