import sys, os
import unittest

testdir   = os.path.dirname(os.path.abspath(__file__))
parentdir = os.path.dirname(testdir)
rootdir   = os.path.dirname(os.path.dirname(parentdir))

sys.path.insert(0, os.path.dirname(rootdir))

