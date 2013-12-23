import logging
import os
import json

import numpy as np
import math
import mmh3



class CountingBloomFilter(object):
    _ENTRIES_PER_8BYTE = 1
    def __init__(self, capacity, data_path, error=0.005, id=None):
        self.capacity = capacity
        self.error = error
        self.num_bytes = int(-capacity * math.log(error) / math.log(2)**2) + 1
        self.num_hashes = int(self.num_bytes / capacity * math.log(2)) + 1
        self.data_path = data_path
        self.bloom_filename = os.path.join(data_path, 'bloom.npy')
        self.meta_filename = os.path.join(data_path, 'meta.json')
        self.id = id

        size = int(math.ceil(self.num_bytes / self._ENTRIES_PER_8BYTE))
        if os.path.exists(self.bloom_filename):
            self.data = np.load(self.bloom_filename)
        else:
            self.data = np.zeros((size,), dtype=np.uint8, order='C')

    def _indexes(self, key):
        """
        Generates the indicies corresponding to the given key
        """
        h1, h2 = mmh3.hash64(key)
        for i in xrange(self.num_hashes):
            yield (h1 + i * h2) % self.num_bytes

    def add(self, key, N=1):
        """
        Adds `N` counts to the indicies given by the key
        """
        assert isinstance(key, str)
        for index in self._indexes(key):
            self.data[index] += N
        return self

    def remove(self, key, N=1):
        """
        Removes `N` counts to the indicies given by the key
        """
        assert isinstance(key, str)
        indexes = list(self._indexes(key))
        if not any(self.data[index] < N for index in indexes):
            for index in indexes:
                self.data[index] -= N
        return self

    def remove_all(self, N=1):
        """
        Removes `N` counts to all indicies.  Useful for expirations
        """
        for i in xrange(self.num_bytes):
            if self.data[i] >= N:
                self.data[i] -= N

    def contains(self, key):
        """
        Check if the current bloom contains the key `key`
        """
        assert isinstance(key, str)
        return all(self.data[index] != 0 for index in self._indexes(key))

    def size(self):
        return -self.num_bytes * math.log(1 - self.num_non_zero / float(self.num_bytes)) / float(self.num_hashes) 

    def flush_data(self):
        np.save(self.bloom_filename, self.data)

    def get_meta(self):
        return {
            'capacity': self.capacity,
            'error': self.error,
            'id': self.id,
        }

    def save(self):
        logging.info("Saving counting bloom to %s" % self.data_path)
        if not os.path.exists(self.data_path):
            logging.info("Bloom path doesn't exist, creating:  %s" % self.data_path)
            os.makedirs(self.data_path)

        self.flush_data()
        meta = self.get_meta()

        with open(self.meta_filename, 'w') as meta_file:
            json.dump(meta, meta_file)

    @classmethod
    def load(cls, data_path):
        logging.info("Loading counting bloom from %s" % data_path)
        kwargs = None

        with open(os.path.join(data_path, 'meta.json'), 'r') as meta_file:
            kwargs = json.load(meta_file)

        kwargs['data_path'] = data_path

        return cls(**kwargs)


    def __contains__(self, key):
        return self.contains(key)

    def __add__(self, other):
        return self.add(other)

    def __sub__(self, other):
        return self.remove(other)

    def __len__(self):
        return self.size()


