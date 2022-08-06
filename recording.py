from abc import ABC
from abc import abstractmethod
import collections
import io
import logging
from enum import Enum
import time
from tkinter.messagebox import NO
from typing import List, Optional, Tuple, Union
from threading import Lock

import numpy as np
import sounddevice as sd
import soundfile as sf
from timeit import default_timer as timer

import atexit
from viztracer import VizTracer, get_tracer
import yaml
from yaml import Loader


class State(Enum):
    Pause = "pause"
    Record = "record"
    Loop = "loop"


class RingAccessVector(ABC):
    """
    Dynamic vector of variable size with tail append and circular read access to elements.
    """
    @abstractmethod
    def set_idx(self, idx: int) -> bool:
        """
        Set the current index (for read access)

        :param idx: playback index
        :return: whether the index has been updated correctly
        """
        ...
    
    @abstractmethod
    def append(self, x: np.ndarray):
        """
        Appends x to the end of the vector.

        :param x: a numpy array
        """
        ...

    @abstractmethod
    def numpy(self) -> np.ndarray:
        """
        Get a numpy array holding the data of this vector.

        :return: numpy array with all data in this vector
        """
        ...

    @abstractmethod
    def take(self, n: int) -> Optional[np.ndarray]:
        """
        Take n elements from the vector and advance the index accordingly.

        :return: numpy array (view) with the elements. Returns None if there are
                 no elements in the vector.
        """
        ...

    @abstractmethod
    def __len__(self) -> int:
        """
        Get the size of the vector.

        :return: total number of elements in the vector
        """
        ...


class RingGrowingArray(RingAccessVector):
    def __init__(self, dtype):
        self.segment_size = 100_000
        self.capacity = self.segment_size
        self.data = np.empty((self.capacity, 1), dtype=dtype)
        self.size = 0
        self.idx = 0

    def set_idx(self, idx):
        if idx < 0 or idx >= self.size:
            logging.warning(f"Could not set idx to {idx} in data of length {self.size}.")
            return False
        
        self.idx = idx
        return True

    def append(self, x: np.ndarray):
        num_el = x.shape[0]
        if self.size + num_el >= self.capacity:
            self.capacity += self.segment_size
            new_data = np.empty((self.capacity, *self.data.shape[1:]))
            new_data[:self.size] = self.data[:self.size]
            self.data = new_data

        self.data[self.size:self.size + num_el] = x
        self.size += num_el

    def numpy(self):
        return self.data[:self.size]

    def take(self, n):
        if self.size == 0:
            return None

        curr_idx = self.idx
        next_idx = self.idx + n

        # already set next playback index
        self.idx = next_idx % self.size

        if next_idx <= self.size:
            # fast case: just get the slice
            return self.data[curr_idx:next_idx]
        else:
            # slow case: get with wrap around
            data_slice = slice(curr_idx, next_idx)
            return self.data[:self.size].take(data_slice, mode='wrap')

    def __len__(self):
        return self.size


class RingSegmentList(RingAccessVector):
    def __init__(self):
        self.li: List[np.ndarray] = []
        self.total_len = 0

        self.segment_idx: int = 0
        self.elem_idx: int = 0

    def append(self, x: np.ndarray):
        # note that copy is necessary
        self.li.append(x.copy())
        self.total_len += x.shape[0]

    def numpy(self):
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

    def take(self, n):
        if self.total_len == 0:
            return None

        remaining = n
        blocks = None
        while remaining > 0:
            available = self.li[self.segment_idx].shape[0] - self.elem_idx
            if remaining <= available:
                # collect the remaining number of elements
                block = self.li[self.segment_idx][self.elem_idx:self.elem_idx + remaining]

                if remaining == available:
                    # move to next segment
                    self.segment_idx = (self.segment_idx + 1) % len(self.li)
                    self.elem_idx = 0
                else:
                    self.elem_idx += remaining

                if blocks is None:
                    # as this is the only block, just return it
                    return block
                else:
                    # otherwise, we have to merge multiple blocks later
                    blocks.append(block)

                remaining = 0
            else:
                # collect everything from this segment and continue with the next one
                block = self.li[self.segment_idx][self.elem_idx:self.elem_idx + available]

                if blocks is None:
                    blocks = [block]
                else:
                    blocks.append(block)
                
                self.segment_idx = (self.segment_idx + 1) % len(self.li)
                self.elem_idx = 0

                remaining -= available

        return np.reshape(blocks, (n, -1))

    def clear(self):
        self.li = []
        self.total_len = 0
        self.segment_idx = 0
        self.elem_idx = 0

    def __len__(self):
        return self.total_len


class Recording:
    def __init__(self):
        self._data: RingAccessVector = RingSegmentList()
        self.state: State = State.Pause
        self.frame: int = 0
        self.volume: float = 1.0
        self.name: str = ''
        self.timestamp = time.time()

    def set_frame(self, new_frame):
        if self._data.set_idx(new_frame):
            self.frame = new_frame

    def record(self, data_in: np.ndarray):
        self._data.append(data_in)

    def loop(self, data_out: np.ndarray):
        n = data_out.shape[0]
        out = self._data.take(n)
        if out is not None:
            data_out += out * self.volume
            self.frame =  (self.frame + n) % len(self._data)

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


stream = None
recordings = collections.defaultdict(lambda: Recording())
duration_stats = StatsBuffer(capacity=100, dtype=float)

callback_lock = Lock()

if __debug__:
    logging.warning("Debug mode is enabled (__debug__).")
    callback_thread_added = False

def callback(data_in: np.ndarray, data_out: np.ndarray, frames: int, time, status: sd.CallbackFlags):
    global recordings, callback_lock

    if __debug__:
        global callback_thread_added
        if not callback_thread_added and get_tracer() is not None:
            get_tracer().enable_thread_tracing()
            callback_thread_added = True

    if status:
        logging.warning(status)

    start = timer()

    # add recordings 
    data_out.fill(0)
    with callback_lock:
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
        'duration_stats': duration_stats.get(),
        'debug': get_devices_list()
    }


def load_config():
    with open("config.yml", "r") as f:
        return yaml.load(f, Loader=Loader)

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

    if __debug__:
        # save tracer records
        tracer.stop()
        tracer.save()
