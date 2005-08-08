
/************************************************************/
 /***  C header subsection: operations between floats      ***/


/*** unary operations ***/

#define OP_FLOAT_IS_TRUE(x,r,err)   OP_FLOAT_NE(x,0.0,r,err)
#define OP_FLOAT_NEG(x,r,err)       r = -x
#define OP_FLOAT_ABS(x,r,err)       r = fabs(x)

/***  binary operations ***/

#define OP_FLOAT_EQ(x,y,r,err)	  r = (x == y)
#define OP_FLOAT_NE(x,y,r,err)	  r = (x != y)
#define OP_FLOAT_LE(x,y,r,err)	  r = (x <= y)
#define OP_FLOAT_GT(x,y,r,err)	  r = (x >  y)
#define OP_FLOAT_LT(x,y,r,err)	  r = (x <  y)
#define OP_FLOAT_GE(x,y,r,err)	  r = (x >= y)

#define OP_FLOAT_CMP(x,y,r,err) \
	r = ((x > y) - (x < y))

/* addition, subtraction */

#define OP_FLOAT_ADD(x,y,r,err)     r = x + y
#define OP_FLOAT_SUB(x,y,r,err)     r = x - y
#define OP_FLOAT_MUL(x,y,r,err)     r = x * y
#define OP_FLOAT_DIV(x,y,r,err)     r = x / y
#define OP_FLOAT_TRUEDIV(x,y,r,err) OP_FLOAT_DIV(x,y,r,err)
#define OP_FLOAT_MOD(x,y,r,err)     r = fmod(x, y) 
#define OP_FLOAT_POW(x,y,r,err)     r = pow(x, y) 

/*** conversions ***/

#define OP_CAST_FLOAT_TO_INT(x,r,err)    r = (long)(x)
#define OP_CAST_FLOAT_TO_UINT(x,r,err)   r = (unsigned long)(x)
#define OP_CAST_INT_TO_FLOAT(x,r,err)    r = (double)(x)
#define OP_CAST_UINT_TO_FLOAT(x,r,err)   r = (double)(x)
#define OP_CAST_BOOL_TO_FLOAT(x,r,err)   r = (double)(x)
