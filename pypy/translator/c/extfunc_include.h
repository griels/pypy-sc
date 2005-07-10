/************************************************************/
 /***  C header subsection: external functions             ***/

/******************************************************************/
#ifdef HAVE_RTYPER      /* not defined if we don't have an RTyper */
/******************************************************************/


#include <unistd.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <time.h>
#ifndef PATH_MAX
  /* assume windows */
  #define PATH_MAX 254
#endif

/* The functions below are mapped to functions from pypy.rpython.module.*
   by the pypy.translator.c.fixedname.EXTERNALS dictionary.
   They should correspond to the functions with the suggested_primitive
   flag set, and NOT necessarily directly to the ll_os_*() functions.
   See for example ll_read_into(), which is called by ll_os_read().
   The latter would be messy to write here, but LL_read_into() is quite easy.
*/

#define RPyString_Size(rps)		((rps)->rs_chars.length)
#define RPyString_AsString(rps)		((rps)->rs_chars.items)


/************************************************************/
 /***   os module                                          ***/


int LL_os_open(RPyString *filename, int flag, int mode)
{
	char buf[PATH_MAX];
	int fd, error, namelen = RPyString_Size(filename);
	if (namelen >= PATH_MAX) {
		RAISE_OSERROR(ENAMETOOLONG);
		return -1;
	}
	else {
		memcpy(buf, RPyString_AsString(filename), namelen);
		buf[namelen] = 0;
		fd = open(buf, flag, mode);
		if (fd == -1)
			RAISE_OSERROR(errno);
		return fd;
	}
}

long LL_read_into(int fd, RPyString *buffer)
{
	long n = read(fd, RPyString_AsString(buffer), RPyString_Size(buffer));
	if (n == -1)
		RAISE_OSERROR(errno);
	return n;
}

long LL_os_write(int fd, RPyString *buffer)
{
	long n = write(fd, RPyString_AsString(buffer), RPyString_Size(buffer));
	if (n == -1)
		RAISE_OSERROR(errno);
	return n;
}

void LL_os_close(int fd)
{
	if (close(fd) == -1)
		RAISE_OSERROR(errno);
}


/************************************************************/
 /***   time module                                        ***/


double LL_time_clock(void)
{
	return ((double) clock()) / CLOCKS_PER_SEC;
}


/******************************************************************/
#endif                                             /* HAVE_RTYPER */
/******************************************************************/
