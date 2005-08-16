extdeclarations = """
;ll_strtod.py
%__ll_strtod_formatd        = internal constant [12 x sbyte] c"formatd....\\00"
%__ll_strtod_parts_to_float = internal constant [12 x sbyte] c"parts2flt..\\00"
"""

extfunctions = {}

extfunctions["%ll_strtod_formatd"] = (("%__debug",), """
internal fastcc %RPyString* %ll_strtod_formatd(%RPyString* %s, double %x) {
    call fastcc void %__debug([12 x sbyte]* %__ll_strtod_formatd) ; XXX: TODO: ll_strtod_formatd
    ret %RPyString* null
}
""")

extfunctions["%ll_strtod_parts_to_float"] = (("%__debug",), """
internal fastcc double %ll_strtod_parts_to_float(%RPyString* s0, %RPyString* s1, %RPyString* s2, %RPyString* s3) {
    call fastcc void %__debug([12 x sbyte]* %__ll_strtod_parts_to_float) ; XXX: TODO: ll_strtod_parts_to_float
    ret double 0.0
}
""")
