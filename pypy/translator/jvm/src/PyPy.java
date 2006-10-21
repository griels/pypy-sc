package pypy;

import java.util.List;
import java.util.ArrayList;

/**
 * Class with a number of utility routines.
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
            return value;

        int loword = value % BITS16;
        int hiword = Math.floor(value / BITS16);
        assert (loword & 0xFFFF0000) == 0;
        assert (hiword & 0xFFFF0000) == 0;
        return (hiword << 16) + loword;
    }

    public static long long_bitwise_negate(long value) {
        return ~value;
    }

    public static List<?> array_to_list(Object[] array) {
        List<?> l = new ArrayList();
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
                return l;
            int lowerword = l & 0xFFFF;
            int upperword = l >> 16;
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
}