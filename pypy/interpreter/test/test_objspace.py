import testsupport

class TestStdObjectSpace(testsupport.TestCase):

    def setUp(self):
        self.space = testsupport.objspace()

    def tearDown(self):
        pass

    def test_newstring(self):
        w = self.space.wrap
        s = 'abc'
        chars_w = [w(ord(c)) for c in s]
        self.assertEqual_w(w(s), self.space.newstring(chars_w))

    def test_newstring_fail(self):
        w = self.space.wrap
        s = 'abc'
        not_chars_w = [w(c) for c in s]
        self.assertRaises_w(self.space.w_TypeError,
                            self.space.newstring,
                            not_chars_w)
        self.assertRaises_w(self.space.w_ValueError,
                            self.space.newstring,
                            [w(-1)])

    def test_newlist(self):
        w = self.space.wrap
        l = range(10)
        w_l = self.space.newlist([w(i) for i in l])
        self.assertEqual_w(w_l, w(l))

    def test_newdict(self):
        w = self.space.wrap
        items = [(0, 1), (3, 4)]
        items_w = [(w(k), w(v)) for (k, v) in items]
        d = dict(items)
        w_d = self.space.newdict(items_w)
        self.assertEqual_w(w_d, w(d))
        
if __name__ == '__main__':
    testsupport.main()
