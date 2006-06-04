
from pypy.rpython.module.ll_strtod import ll_strtod_parts_to_float, ll_strtod_formatd
from pypy.rpython.module.support import LLSupport


def test_parts_to_float():
    data = [
    (("","1","","")     , 1.0),
    (("-","1","","")    , -1.0),
    (("-","1","5","")   , -1.5),
    (("-","1","5","2")  , -1.5e2),
    (("-","1","5","+2") , -1.5e2),
    (("-","1","5","-2") , -1.5e-2),
    ]

    for parts, val in data:
        assert ll_strtod_parts_to_float(*map(LLSupport.to_rstr, parts)) == val
    

def test_formatd():
    res = ll_strtod_formatd(LLSupport.to_rstr("%.2f"), 1.5)
    assert LLSupport.from_rstr(res) == "1.50"
