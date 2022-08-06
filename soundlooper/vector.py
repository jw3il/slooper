
from abc import ABC, abstractmethod
import logging
from typing import List, Optional

import numpy as np


class RingAccessVector(ABC):
    """
    Dynamic numpy vector of variable size with tail append and circular read access to elements.
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
    """
    Numpy array that grows when adding elements would exceed its capacity.
    """
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
    """
    List of numpy arrays.
    """
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
