
class BaseCTypesTestChecker:
    def setup_class(cls):
        try:
            import _rawffi
        except ImportError:
            pass
        else:
            cls.old_num = _rawffi._num_of_allocated_objects()
    
    def teardown_class(cls):
        try:
            import _rawffi
        except ImportError:
            pass
        else:
            import gc
            gc.collect()
            # there is one reference coming from the byref() above
            assert _rawffi._num_of_allocated_objects() <= cls.old_num
