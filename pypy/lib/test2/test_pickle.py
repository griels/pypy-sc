# -*- coding: iso-8859-1 -*-
import unittest, test.test_support
import pickle

class Picklable(object):
    def __init__(self, a=5):
        self.a = a
    def __eq__(self, other):
        return self.a == other.a
    def __str__(self):
        return '%s(%r)' % (self.__class__.__name__, self.a)

class PicklableSpecial2(Picklable):
    def __reduce__(self):
        return self.__class__, (self.a,)

class PickleTest(unittest.TestCase):

    def _pickle_some(self, x):
        for proto in range(pickle.HIGHEST_PROTOCOL + 1):
            s = pickle.dumps(x, proto)
            y = pickle.loads(s)
            self.assertEqual(x, y)

    def test_pickle_plain(self):
        self._pickle_some(Picklable())

    def test_pickle_special2(self):
        self._pickle_some(PicklableSpecial2())

def test_main():
    test.test_support.run_unittest(PickleTest)

if __name__ == "__main__":
    test_main()
