# -*- coding: iso-8859-1 -*-
import unittest, test.test_support
import pickle

class FakeIterator(object):
    def __init__(self, *a):
        pass
    def __iter__(self):
        return self
    # no next method -- which is why it's *fake*!

class IterTest(unittest.TestCase):

    def test_fakeiterator(self):
        self.assertRaises(TypeError, iter, FakeIterator())

def test_main():
    test.test_support.run_unittest(IterTest)

if __name__ == "__main__":
    test_main()
