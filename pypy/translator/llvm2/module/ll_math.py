extdeclarations = """
;ll_math.py
declare ccc double %acos(double)
declare ccc double %asin(double)
declare ccc double %atan(double)
declare ccc double %ceil(double)
declare ccc double %cos(double)
declare ccc double %cosh(double)
declare ccc double %exp(double)
declare ccc double %fabs(double)
declare ccc double %floor(double)
declare ccc double %log(double)
declare ccc double %log10(double)
declare ccc double %sin(double)
declare ccc double %sinh(double)
declare ccc double %sqrt(double)
declare ccc double %tan(double)
declare ccc double %tanh(double)
declare ccc double %atan2(double,double)
declare ccc double %fmod(double,double)

%__ll_math_frexp = internal constant [12 x sbyte] c"frexp......\\00"
%__ll_math_hypot = internal constant [12 x sbyte] c"hypot......\\00"
%__ll_math_ldexp = internal constant [12 x sbyte] c"ldexp......\\00"
%__ll_math_modf  = internal constant [12 x sbyte] c"modf.......\\00"
%__ll_math_pow   = internal constant [12 x sbyte] c"pow........\\00"
"""

extfunctions = {}

#functions with a one-to-one C equivalent
simple_functions = [
    ('double %x', ['acos','asin','atan','ceil','cos','cosh','exp','fabs',
                   'floor','log','log10','sin','sinh','sqrt','tan','tanh']),
    ('double %x, double %y', ['atan2','fmod']),
    ]

simple_function_template = """
internal fastcc double %%ll_math_%(function)s(%(params)s) {
    %%t = call ccc double %%%(function)s(%(params)s)
    ret double %%t
}

"""

for params, functions in simple_functions:
    for function in functions:
        extfunctions["%ll_math_" + function] = ((), simple_function_template % locals())

extfunctions["%ll_math_frexp"] = (("%__debug",), """
internal fastcc %structtype.tuple2.6* %ll_math_frexp(double %x) {
    call fastcc void %__debug([12 x sbyte]* %__ll_math_frexp) ; XXX: TODO: ll_math_frexp
    ret %structtype.tuple2.6* null
}
""")

extfunctions["%ll_math_hypot"] = (("%__debug",), """
internal fastcc double %ll_math_hypot(double %x, double %y) {
    call fastcc void %__debug([12 x sbyte]* %__ll_math_hypot) ; XXX: TODO: ll_math_hypot
    ret double 0.0
}
""")

extfunctions["%ll_math_ldexp"] = (("%__debug",), """
internal fastcc double %ll_math_ldexp(double %x, int %y) {
    call fastcc void %__debug([12 x sbyte]* %__ll_math_ldexp) ; XXX: TODO: ll_math_ldexp
    ret double 0.0
}
""")

extfunctions["%ll_math_modf"] = (("%__debug",), """
internal fastcc %structtype.tuple2.9* %ll_math_modf(double %x) {
    call fastcc void %__debug([12 x sbyte]* %__ll_math_modf) ; XXX: TODO: ll_math_modf
    ret %structtype.tuple2.9* null
}
""")

extfunctions["%ll_math_pow"] = (("%__debug",), """
internal fastcc double %ll_math_pow(double %x, double %y) {
    call fastcc void %__debug([12 x sbyte]* %__ll_math_pow) ; XXX: TODO: ll_math_pow
    ret double 0.0
}
""")
