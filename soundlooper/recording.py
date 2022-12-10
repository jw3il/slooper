from enum import Enum
import io
import time

import numpy as np
import soundfile as sf
from soundlooper.vector import RingAccessVector, RingSegmentList


class State(Enum):
    Pause = "pause"
    Record = "record"
    Loop = "loop"


class Recording:
    def __init__(self):
        self._data: RingAccessVector = RingSegmentList()
        self.state: State = State.Pause
        self.frame: int = 0
        self.volume: float = 1.0
        self.name: str = ""
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
            self.frame = (self.frame + n) % len(self._data)

    def create_bytes_io(self, samplerate):
        bytes_io = io.BytesIO()
        sf.write(
            bytes_io, self._data.numpy(), samplerate=int(samplerate), format="FLAC"
        )
        return bytes_io

    def get_info_dict(self):
        return {
            "name": self.name,
            "state": self.state.value,
            "volume": self.volume,
            "frame": self.frame,
            "length": len(self._data),
        }
