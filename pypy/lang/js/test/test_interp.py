
from pypy.lang.js.astgen import *
from pypy.lang.js import interpreter
from pypy.lang.js.parser import parse
from pypy.lang.js.interpreter import ThrowException
from pypy.lang.js.jsobj import W_Number
import py.test

import sys
from StringIO import StringIO

def parse_d(code):
    return build_interpreter(parse(code))

class TestInterp(object):
    def test_simple(self):
        assert Plus(Number(3), Number(4)).call().floatval == 7
        #    s = Script([Semicolon(Plus(Number(3), Number(4)))], [], [])
        #    s.call()
        l = []
        interpreter.writer = l.append
        Script([Semicolon(Call(Identifier('print', None), 
                List([Number(1), Number(2)])))],[],[]).call()
        assert l == ['1,2']

    def assert_prints(self, code, assval):
        l = []
        interpreter.writer = l.append
        try:
            code.call()
        except ThrowException, excpt:
            l.append("uncaught exception: "+str(excpt.exception))
        assert l == assval
    
    def assert_result(self, code, result):
        r = code.call()
        assert r.ToString() == result.ToString()
        
    def test_interp_parse(self):
        self.assert_prints(parse_d("print(1+1)"), ["2"])
        self.assert_prints(parse_d("print(1+2+3); print(1)"), ["6", "1"])
        self.assert_prints(parse_d("print(1,2,3);\n"), ["1,2,3"])

    def test_var_assign(self):
        self.assert_prints(parse_d("x=3;print(x);"), ["3"])
        self.assert_prints(parse_d("x=3;y=4;print(x+y);"), ["7"])

    def test_string_var(self):
        self.assert_prints(parse_d('print(\"sss\");'), ["sss"])
    
    def test_string_concat(self):
        self.assert_prints(parse_d('x="xxx"; y="yyy"; print(x+y);'), ["xxxyyy"])
    
    def test_string_num_concat(self):
        self.assert_prints(parse_d('x=4; y="x"; print(x+y, y+x);'), ["4x,x4"])

    def test_to_string(self):
        self.assert_prints(parse_d("x={}; print(x);"), ["[object Object]"])

    def test_object_access(self):
        self.assert_prints(parse_d("x={d:3}; print(x.d);"), ["3"])
        self.assert_prints(parse_d("x={d:3}; print(x.d.d);"), [""])
        self.assert_prints(parse_d("x={d:3, z:4}; print(x.d+x.z);"), ["7"])

    def test_object_access_index(self):
        self.assert_prints(parse_d('x={d:"x"}; print(x["d"]);'), ["x"])
    
    def test_function_prints(self):
        self.assert_prints(parse_d('x=function(){print(3);}; x();'), ["3"])
    
    def test_function_returns(self):
        self.assert_prints(parse_d('x=function(){return 1;}; print(x()+x());'), ["2"])
    
    def test_var_declartion(self):
        self.assert_prints(parse_d('var x = 3; print(x+x);'), ["6"])
    
    def test_var_scoping(self):
        self.assert_prints(parse_d("""
        var y;
        var p;
        p = 0;
        x = function() {
            var p;
            p = 1;
            y = 3; return y + z;
        };
        var z = 2;
        print(x(), y, p);
        """), ["5,3,0"])

    def test_function_args(self):
        self.assert_prints(parse_d("""
        x = function (t,r) {
               return t+r;
        };
        print(x(2,3));
        """), ["5"])

    def test_function_less_args(self):
        self.assert_prints(parse_d("""
        x = function (t, r) {
                return t + r;
        };
        print(x(2));
        """), ["NaN"])

    def test_function_more_args(self):
        self.assert_prints(parse_d("""
        x = function (t, r) {
                return t + r;
        };
        print(x(2,3,4));
        """), ["5"])

    def test_function_has_var(self):
        self.assert_prints(parse_d("""
        x = function () {
                var t = 'test';
                return t;
        };
        print(x());
        """), ["test"])

    def test_function_arguments(self):
        self.assert_prints(parse_d("""
        x = function () {
                r = arguments[0];
                t = arguments[1];
                return t + r;
        };
        print(x(2,3));
        """), ["5"])


    def test_index(self):
        self.assert_prints(parse_d("""
        x = {1:"test"};
        print(x[1]);
        """), ["test"])

    def test_array_initializer(self):
        py.test.skip('not ready yet')
        self.assert_prints(parse_d("""
        x = [];
        print(x);
        """), ["[]"])

    def test_throw(self):
        self.assert_prints(parse_d("throw(3)"), ["uncaught exception: 3"])
        
    def test_group(self):
        self.assert_prints(parse_d("print((2+1))"), ["3"])

    def test_comma(self):
        self.assert_prints(parse_d("print((500,3))"), ["3"])
    
    def test_try_catch(self):
        self.assert_prints(parse_d("""
        try {
            throw(3);
        }
        catch (x) {
            print(x);
        }
        """), ["3"])
    
    def test_block(self):
        self.assert_result(parse_d("{ 5}"), W_Number(5))
        self.assert_result(parse_d("{3; 5}"), W_Number(5))
        