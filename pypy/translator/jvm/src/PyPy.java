package pypy;

import java.util.List;
import java.util.ArrayList;

/**
 * Class with a number of utility routines.
 * 
 * I apologize for the Python-esque naming conventions, but it seems
 * I can't switch my mind to camelCase when working so closely with 
 * Python mere minutes before.
 */
public class PyPy {
    /** 
     * Compares two unsigned integers (value1 and value2) and returns
     * a value greater than, equal to, or less than zero if value 1 is
     * respectively greater than, equal to, or less than value2.  The
     * idea is that you can do the following:
     * 
     * Call uint_cmp(value1, value2)
     * IFLT ... // jumps if value1 < value2
     * IFEQ ... // jumps if value1 == value2
     * IFGT ... // jumps if value1 > value2
     * etc 
     */
    public static int uint_cmp(int value1, int value2) {
        final int VALUE1BIGGER = 1;
        final int VALUE2BIGGER = -1;
        final int EQUAL = 0;

        if (((value1 | value2) & Integer.MIN_VALUE) == 0) {
            // neither is negative, presumably the common case
            return value1 - value2;
        }

        if (value1 == value2)
            return EQUAL;

        if (value1 < 0) {
            if (value2 < 0) {
                // both are negative
                if (value1 > value2)
                    // example: value1 == -1 (0xFFFF), value2 == -2 (0xFFFE)
                    return VALUE1BIGGER;
                return VALUE2BIGGER;
            }
            else {
                // value1 is neg, value 2 is not
                return VALUE1BIGGER;
            }
        }

        // value1 is not neg, value2 is neg
        return VALUE2BIGGER;
    }

    public static int ulong_cmp(long value1, long value2) {
        final int VALUE2BIGGER = -1;
        final int VALUE1BIGGER = 1;
        final int EQUAL = 0;

        if (value1 == value2)
            return EQUAL;

        if (value1 < 0) {
            if (value2 < 0) {
                // both are negative
                if (value1 > value2)
                    // example: value1 == -1 (0xFFFF), value2 == -2 (0xFFFE)
                    return VALUE1BIGGER;
                return VALUE2BIGGER;
            }
            else {
                // value1 is neg, value 2 is not
                return VALUE1BIGGER;
            }
        }
        else if (value2 < 0) {
            // value1 is not neg, value2 is neg
            return VALUE2BIGGER;
        }
        
        if (value1 > value2)
            return VALUE1BIGGER;
        return VALUE2BIGGER;
    }

    public static final double BITS16 = (double)0xFFFF;

    public static double uint_to_double(int value) {
        if (value >= 0)
            return value;
        else {
            int loword = value & 0xFFFF;
            double result = loword;
            int hiword = value >>> 16;
            result += hiword * BITS16;
            return result;
        }
    }

    public static int double_to_uint(double value) {
        if (value <= Integer.MAX_VALUE)
            return (int)value;

        int loword = (int)(value % BITS16);
        int hiword = (int)(Math.floor(value / BITS16));
        assert (loword & 0xFFFF0000) == 0;
        assert (hiword & 0xFFFF0000) == 0;
        return (hiword << 16) + loword;
    }

    public static long long_bitwise_negate(long value) {
        return ~value;
    }

    public static List<?> array_to_list(Object[] array) {
        List l = new ArrayList();
        for (Object o : array) {
            l.add(o);
        }
        return l;
    }

    public static int str_to_int(String s) {
        try {
            return Integer.parseInt(s);
        } catch (NumberFormatException fe) {
            throw new RuntimeException(fe);
        }
    }

    public static int str_to_uint(String s) {
        try {
            long l = Long.parseLong(s);
            if (l < Integer.MAX_VALUE)
                return (int)l;
            int lowerword = (int)(l & 0xFFFF);
            int upperword = (int)(l >> 16);
            return lowerword + (upperword << 16);
        } catch (NumberFormatException fe) {
            throw new RuntimeException(fe);
        }
    }

    public static long str_to_long(String s) {
        try {
            return Long.parseLong(s);
        } catch (NumberFormatException fe) {
            throw new RuntimeException(fe);
        }
    }

    public static long str_to_ulong(String s) {
        // oh bother
        throw new RuntimeException("TODO--- str to ulong");
    }

    public static boolean str_to_bool(String s) {
        // not sure what are considered valid boolean values...
        // let's be very accepting and take both strings and numbers
        if (s.equalsIgnoreCase("true"))
            return true;
        if (s.equalsIgnoreCase("false"))
            return false;

        try {
            int i = Integer.parseInt(s);
            return i != 0;
        } catch (NumberFormatException ex) {
            throw new RuntimeException(ex);
        }
    }

    public static double str_to_double(String s) {
        try {
            return Double.parseDouble(s);
        } catch (NumberFormatException ex) {
            throw new RuntimeException(ex);
        }
    }

    public static char str_to_char(String s) {
        if (s.length() != 1)
            throw new RuntimeException("String not single character: '"+s+"'");
        return s.charAt(0);
    }

    // Used in testing:

    public static void dump_indented(int indent, String text) {
        for (int i = 0; i < indent; i++)
            System.out.print(" ");
        System.out.println(text);
    }

    public static void dump_int(int i, int indent) {
        dump_indented(indent, Integer.toString(i));
    }

    public static void dump_uint(int i, int indent) {
        if (i >= 0)
            dump_indented(indent, Integer.toString(i));
        else {
            int loword = i & 0xFFFF;
            int hiword = i >>> 16;
            long res = loword + (hiword*0xFFFF);
            dump_indented(indent, Long.toString(res));
        }
    }

    public static void dump_boolean(boolean l, int indent) {
        if (l)
            dump_indented(indent, "True");
        else
            dump_indented(indent, "False");
    }

    public static void dump_long(long l, int indent) {
        dump_indented(indent, Long.toString(l));
    }

    public static void dump_double(double d, int indent) {
        dump_indented(indent, Double.toString(d));
    }

    public static void _append_char(StringBuffer sb, char c) {
        if (c == '"') 
            sb.append("\\\"");
        else
            sb.append(c);
    }

    public static void dump_string(byte[] b, int indent) {
        StringBuffer sb = new StringBuffer();
        sb.append('"');
        for (byte _c : b) {
            char c = (char)_c;
            _append_char(sb, c);
        }
        sb.append('"');
        dump_indented(indent, sb.toString());
    }

    public static void dump_string(String b, int indent) {
        StringBuffer sb = new StringBuffer();
        sb.append('"');
        for (int i = 0; i < b.length(); i++) {
            char c = b.charAt(i);
            _append_char(sb, c);
        }
        sb.append('"');
        dump_indented(indent, sb.toString());
    }

    public static void dump_object(Object o, int indent) {
        dump_indented(indent, o.toString());
    }

    // ----------------------------------------------------------------------
    // StringBuffer

    public static void ll_append_char(StringBuilder sb, char c) {
        // annoyingly, the actual return code is StringBuilder, so I have
        // to make this wrapper to ignore the return value
        sb.append(c);
    }

    public static void ll_append(StringBuilder sb, String s) {
        // annoyingly, the actual return code is StringBuilder, so I have
        // to make this wrapper to ignore the return value
        sb.append(s);
    }

    public static void ll_append(StringBuilder sb, byte[] s) {
        // This is only used when we are using byte arrays instead of
        // strings.  We should really replace StringBuilder with some
        // kind of ByteBuilder in that case...
        for (byte b : s) {
            sb.append((char)b);
        }
    }

    public static byte[] ll_build(StringBuilder sb) {
        // This is only used when we are using byte arrays instead of
        // strings.  We should really replace StringBuilder with some
        // kind of ByteBuilder in that case...
        return string2bytes(sb.toString());
    }

    // ----------------------------------------------------------------------
    // Type Manipulation Routines

    public static Object RuntimeNew(Class c) {
        // all classes in our system have constructors w/ no arguments
        try {
            return c.getConstructor().newInstance();
        } catch (Exception exc) {
            throw new RuntimeException("Unexpected", exc);
        }
    }

    // ----------------------------------------------------------------------
    // Helpers
    
    public static byte[] string2bytes(String s) {
    	return s.getBytes();
    }

    // ----------------------------------------------------------------------
    // OOString support
    
    public static String oostring(int n, int base_) {
    	// XXX needs special case for unsigned ints
        if (base_ == -1)
            base_ = 10;
        if (n < 0 && base_ != 10)
            return "-" + Integer.toString(-n, base_);
        else
            return Integer.toString(n, base_);
    }

    public static String oostring(double d, int base_) {
        return new Double(d).toString();
    }

    public static String oostring(Object obj, int base_)
    {
        return String.format("<%s object>", new Object[] { obj.getClass().getName() });
    }

    public static String oostring(char ch, int base_)
    {
        return new Character(ch).toString();
    }

    public static byte[] oostring(byte[] s, int base_)
    {
        return s;
    }

    public static String oostring(String s, int base_)
    {
        return s;
    }

    public static String oostring(boolean b, int base_)
    {
        if (b) return "True";
        return "False";
    }

    // ----------------------------------------------------------------------
    // Self Test

    public static int __counter = 0, __failures = 0;
    public static void ensure(boolean f) {
        if (f) {
            System.out.println("Test #"+__counter+": OK");
        }
        else {
            System.out.println("Test #"+__counter+": FAILED");
            __failures++;
        }
        __counter++;
    }

    public static void main(String args[]) {
        // Small self test:

        ensure(uint_cmp(0xFFFFFFFF, 0) > 0);
        ensure(uint_cmp(0, 0xFFFFFFFF) < 0);
        ensure(uint_cmp(0x80000000, 0) > 0);
        ensure(uint_cmp(0, 0x80000000) < 0);
        ensure(uint_cmp(0xFFFF, 0) > 0);
        ensure(uint_cmp(0, 0xFFFF) < 0);
        ensure(uint_cmp(0xFFFFFFFF, 0xFFFF) > 0);
        ensure(uint_cmp(0xFFFF, 0xFFFFFFFF) < 0);

        ensure(ulong_cmp(0xFFFFFFFFFFFFFFFFL, 0) > 0);
        ensure(ulong_cmp(0, 0xFFFFFFFFFFFFFFFFL) < 0);
        ensure(ulong_cmp(0xFFFFFFFFFFFFFFFFL, 0xFFFF) > 0);
        ensure(ulong_cmp(0xFFFF, 0xFFFFFFFFFFFFFFFFL) < 0);
        ensure(ulong_cmp(0x8000000000000000L, 0xFFFF) > 0);
        ensure(ulong_cmp(0xFFFF, 0x8000000000000000L) < 0);
        
        System.out.println("Total Failures: "+__failures);
    }
}