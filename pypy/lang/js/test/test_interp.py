
import sys
from StringIO import StringIO

import py.test

from pypy.lang.js.astgen import *
from pypy.lang.js import interpreter
from pypy.lang.js.jsparser import parse
from pypy.lang.js.interpreter import ThrowException
from pypy.lang.js.jsobj import W_Number, W_Object, ExecutionContext


def js_is_on_path():
    try:
        py.path.local.sysfind("js")
    except py.error.ENOENT: 
        py.test.skip("js binary not found")



class TestInterp(object):
    def test_simple(self):
        assert Plus(Number(3), Number(4)).call(ExecutionContext()).floatval == 7
        l = []
        interpreter.writer = l.append
        Script([Semicolon(Call(Identifier('print', None), 
                List([Number(1), Number(2)])))],[],[]).call(ExecutionContext())
        assert l == ['1,2']

    def assert_prints(self, code, assval):
        l = []
        interpreter.writer = l.append
        js_int = interpreter.Interpreter(code)
        try:
            js_int.run()
        except ThrowException, excpt:
            l.append("uncaught exception: "+str(excpt.exception))
        assert l == assval
    
    def assert_result(self, code, result):
        inter = interpreter.Interpreter(code)
        r = inter.run()
        assert r.ToString() == result.ToString()
        
    def test_interp_parse(self):
        self.assert_prints("print(1+1)", ["2"])
        self.assert_prints("print(1+2+3); print(1)", ["6", "1"])
        self.assert_prints("print(1,2,3);\n", ["1,2,3"])

    def test_var_assign(self):
        self.assert_prints("x=3;print(x);", ["3"])
        self.assert_prints("x=3;y=4;print(x+y);", ["7"])

    def test_minus(self):
        self.assert_prints("print(2-1)", ["1"])
    
    def test_string_var(self):
        self.assert_prints('print(\"sss\");', ["sss"])
    
    def test_string_concat(self):
        self.assert_prints('x="xxx"; y="yyy"; print(x+y);', ["xxxyyy"])
    
    def test_string_num_concat(self):
        self.assert_prints('x=4; y="x"; print(x+y, y+x);', ["4x,x4"])

    def test_to_string(self):
        self.assert_prints("x={}; print(x);", ["[object Object]"])

    def test_object_access(self):
        self.assert_prints("x={d:3}; print(x.d);", ["3"])
        self.assert_prints("x={d:3}; print(x.d.d);", ["undefined"])
        self.assert_prints("x={d:3, z:4}; print(x.d+x.z);", ["7"])

    def test_object_access_index(self):
        self.assert_prints('x={d:"x"}; print(x["d"]);', ["x"])
    
    def test_function_prints(self):
        self.assert_prints('x=function(){print(3);}; x();', ["3"])
    
    def test_function_returns(self):
        self.assert_prints('x=function(){return 1;}; print(x()+x());', ["2"])
    
    def test_var_declaration(self):
        self.assert_prints('var x = 3; print(x);', ["3"])
        self.assert_prints('var x = 3; print(x+x);', ["6"])

    def test_var_scoping(self):
        self.assert_prints("""
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
        """, ["5,3,0"])

    def test_function_args(self):
        self.assert_prints("""
        x = function (t,r) {
               return t+r;
        };
        print(x(2,3));
        """, ["5"])

    def test_function_less_args(self):
        self.assert_prints("""
        x = function (t, r) {
                return t + r;
        };
        print(x(2));
        """, ["NaN"])

    def test_function_more_args(self):
        self.assert_prints("""
        x = function (t, r) {
                return t + r;
        };
        print(x(2,3,4));
        """, ["5"])

    def test_function_has_var(self):
        self.assert_prints("""
        x = function () {
                var t = 'test';
                return t;
        };
        print(x());
        """, ["test"])

    def test_function_arguments(self):
        self.assert_prints("""
        x = function () {
                r = arguments[0];
                t = arguments[1];
                return t + r;
        };
        print(x(2,3));
        """, ["5"])


    def test_index(self):
        self.assert_prints("""
        x = {1:"test"};
        print(x[1]);
        """, ["test"])

    def test_array_initializer(self):
        py.test.skip('not ready yet')
        self.assert_prints("""
        x = [];
        print(x);
        """, ["[]"])

    def test_throw(self):
        self.assert_prints("throw(3)", ["uncaught exception: 3"])
        
    def test_group(self):
        self.assert_prints("print((2+1))", ["3"])

    def test_comma(self):
        self.assert_prints("print((500,3))", ["3"])
    
    def test_try_catch(self):
        self.assert_prints("""
        try {
            throw(3);
        }
        catch (x) {
            print(x);
        }
        """, ["3"])
    
    def test_block(self):
        self.assert_result("{ 5}", W_Number(5))
        self.assert_result("{3; 5}", W_Number(5))
    
    def test_try_catch_finally(self):
        self.assert_prints("""
        try {
            throw(3);
        }
        catch (x) {
            print(x);
        }
        finally {
            print(5)
        }
        """, ["3", "5"])
        
    def test_if_then(self):
        self.assert_prints("""
        if (1) {
            print(1);
        }
        """, ["1"])

    def test_if_then_else(self):
        self.assert_prints("""
        if (0) {
            print(1);
        } else {
            print(2);
        }
        """, ["2"])

    def test_compare(self):
        self.assert_prints("print(1>0)",["true"])
        self.assert_prints("print(0>1)",["false"])
        self.assert_prints("print(0>0)",["false"])
        self.assert_prints("print(1<0)",["false"])
        self.assert_prints("print(0<1)",["true"])
        self.assert_prints("print(0<0)",["false"])
        self.assert_prints("print(1>=0)",["true"])
        self.assert_prints("print(1>=1)",["true"])
        self.assert_prints("print(1>=2)",["false"])
        self.assert_prints("print(0<=1)",["true"])
        self.assert_prints("print(1<=1)",["true"])
        self.assert_prints("print(1<=0)",["false"])
        self.assert_prints("print(0==0)",["true"])
        self.assert_prints("print(1==1)",["true"])
        self.assert_prints("print(0==1)",["false"])
        self.assert_prints("print(0!=1)",["true"])
        self.assert_prints("print(1!=1)",["false"])

    def test_binary_op(self):
        self.assert_prints("print(0||0); print(1||0)",["0", "1"])
        self.assert_prints("print(0&&1); print(1&&1)",["0", "1"])
    
    def test_while(self):
        self.assert_prints("""
        i = 0;
        while (i<3) {
            print(i);
            i = i+1;
        }
        print(i);
        """, ["0","1","2","3"])

    def test_object_creation(self):
        self.assert_prints("""
        o = new Object();
        print(o);
        """, ["[object Object]"])

    def test_var_decl(self):
        self.assert_prints("print(x); var x;", ["undefined"])
        self.assert_prints("""
        try {
            print(z);
        }
        catch (e) {
            print(e)
        }
        """, ["ReferenceError: z is not defined"])

    def test_function_name(self):
        self.assert_prints("""
        function x() {
            print("my name is x");
        }
        x();
        """, ["my name is x"])
            
    def test_new_with_function(self):
        c= """
        x = function() {this.info = 'hello';};
        o = new x();
        print(o.info);
        """
        print c
        self.assert_prints(c, ["hello"])

    def test_vars(self):
        self.assert_prints("""
        var x;x=3; print(x)""", ["3"])

    def test_minus(self):
        self.assert_prints("""
        x = {y:3};
        print("y" in x);
        print("z" in x);
        """, ["true", "false"])
    


