import collections
import io
import logging
from enum import Enum
import time
from typing import Optional, List, Tuple, Union

import numpy as np
import sounddevice as sd
import soundfile as sf
from timeit import default_timer as timer

import atexit


class State(Enum):
    Pause = "pause"
    Record = "record"
    Loop = "loop"


class NumpySegmentList:
    def __init__(self):
        self.li: List[np.ndarray] = []
        self.total_len = 0

        self.segment_idx: int = 0
        self.elem_idx: int = 0

    def append(self, arr: np.ndarray):
        self.li.append(arr)
        self.total_len += arr.shape[0]

    def get_numpy(self):
        return np.reshape(self.li, (self.total_len, -1))

    def set_idx(self, idx):
        if idx < 0 or idx >= self.total_len:
            logging.warning(f"Could not set idx to {idx} in data of length {self.total_len}.")
            return False

        # find the segment & relative index this frame belongs to
        total_frame = 0
        for i, arr in enumerate(self.li):
            if idx <= arr.shape[0] + total_frame:
                # found it
                self.segment_idx = i
                self.elem_idx = idx - total_frame
                return True
            else:
                total_frame += arr.shape[0]

        return False

    def circular_add(self, data_out, factor):
        if self.total_len == 0:
            return 0

        collected = 0
        remaining = data_out.shape[0]
        while remaining > 0:
            available = self.li[self.segment_idx].shape[0] - self.elem_idx
            if remaining <= available:
                # collect remaining data
                data_out[collected:collected + remaining] += \
                    self.li[self.segment_idx][self.elem_idx:self.elem_idx + remaining] * factor

                if remaining == available:
                    # move to next segment
                    self.segment_idx = (self.segment_idx + 1) % len(self.li)
                    self.elem_idx = 0
                else:
                    self.elem_idx += remaining

                remaining = 0
                collected += remaining
            else:
                # collect everything from this segment and continue with the next one
                data_out[collected:collected + available] += \
                    self.li[self.segment_idx][self.elem_idx:self.elem_idx + available] * factor

                self.segment_idx = (self.segment_idx + 1) % len(self.li)
                self.elem_idx = 0

                remaining -= available
                collected += available

        return data_out.shape[0]

    def clear(self):
        self.li = []
        self.total_len = 0
        self.segment_idx = 0
        self.elem_idx = 0

    def __len__(self):
        return self.total_len


class Recording:
    def __init__(self):
        self._data: NumpySegmentList = NumpySegmentList()
        self.state: State = State.Pause
        self.frame: int = 0
        self.volume: float = 1.0
        self.name: str = ''
        self.timestamp = time.time()

    def set_frame(self, new_frame):
        if self._data.set_idx(new_frame):
            self.frame = new_frame

    def record(self, data_in: np.ndarray):
        self._data.append(data_in.copy())

    def loop(self, data_out: np.ndarray):
        self.frame = (self.frame + self._data.circular_add(data_out, self.volume)) % len(self._data)

    def create_bytes_io(self):
        global stream
        bytes_io = io.BytesIO()
        sf.write(bytes_io, self._data.get_numpy(), samplerate=int(stream.samplerate), format='FLAC')
        return bytes_io

    def get_info_dict(self):
        return {
            'name': self.name,
            'state': self.state.value,
            'volume': self.volume,
            'frame': self.frame,
            'length': len(self._data)
        }


def get_devices_list():
    return str(sd.query_devices()).split("\n")


class StatsBuffer:
    def __init__(self, capacity, dtype):
        self.data = np.empty(capacity, dtype=dtype)
        self.count = 0
        self.idx = 0

    def update(self, value):
        self.data[self.idx] = value
        self.idx = (self.idx + 1) % self.data.shape[0]
        self.count = min(self.count + 1, self.data.shape[0])

    def get(self):
        if self.count == 0:
            return {
                'mean': 0, 
                'max': 0, 
                'std': 0
            }

        return {
            'mean': self.data[:self.count].mean().item(), 
            'max': self.data[:self.count].max().item(), 
            'std': self.data[:self.count].std().item(),
            '99p': np.percentile(self.data[:self.count], 99).item(),
        }


stream: Optional[sd.Stream] = None
recordings = collections.defaultdict(lambda: Recording())
duration_stats = StatsBuffer(capacity=500, dtype=float)


def callback(data_in: np.ndarray, data_out: np.ndarray, frames: int, time, status: sd.CallbackFlags):
    start = timer()
    global recordings, stats

    if status:
        logging.warning(status)

    data_out[:] = 0
    for r in recordings.values():
        if r.state == State.Record:
            r.record(data_in)
        elif r.state == State.Loop:
            r.loop(data_out)

    duration = timer() - start
    duration_stats.update(duration)


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
        'duration_stats': duration_stats.get()
    }


# make sure to properly close stream at exit
atexit.register(stream_close)

if __name__ == '__main__':
    logging.basicConfig(format="%(asctime)s %(message)s", level=logging.INFO)
    stream_start(device='Spark')
    logging.info("Record")
    recordings["a"].state = State.Record
    sd.sleep(int(1000 * 5))
    logging.info("Playback")
    recordings["a"].state = State.Loop
    sd.sleep(int(1000 * 10))
