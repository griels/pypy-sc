import testsupport
from pypy.module.builtin_app import filter


# trivial functions for testing 

def larger_than_three(x):
   if x > 3:
      return True
   else:
      return False

def larger_than_a(c):
   if c > 'a':
      return True
   else:
      return False

class TestFilter(testsupport.TestCase):

   def test_filter_no_arguments(self):
      self.assertRaises(TypeError, filter)
      
   def test_filter_no_function_no_seq(self):
      self.assertRaises(TypeError, filter, None)

   def test_filter_function_no_seq(self):
      self.assertRaises(TypeError, filter, larger_than_three)

   def test_filter_function_too_many_args(self):
      self.assertRaises(TypeError, filter, larger_than_three, [1], [2])

   def test_filter_no_function_list(self):
      self.assertEqual(filter(None, [1, 2, 3]), [1, 2, 3])

   def test_filter_no_function_tuple(self):
      self.assertEqual(filter(None, (1, 2, 3)), (1, 2, 3))

   def test_filter_no_function_string(self):
      self.assertEqual(filter(None, 'mystring'), 'mystring')

   def test_filter_no_function_with_bools(self):
      self.assertEqual(filter(None, (True, False, True)), (True, True))
      
   def test_filter_list(self):
      self.assertEqual(filter(larger_than_three, [1, 2, 3, 4, 5]), [4, 5])

   def test_filter_tuple(self):
      self.assertEqual(filter(larger_than_three, (1, 2, 3, 4, 5)), (4, 5))

   def test_filter_string(self):
      self.assertEqual(filter(larger_than_a, 'xyzabcd'), 'xyzbcd')

if __name__ == '__main__':
    testsupport.main()
