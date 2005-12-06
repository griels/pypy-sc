
// we hand craft these in module/support.ll
char *RPyString_AsString(RPyString*);
int RPyString_Size(RPyString*);
RPyString *RPyString_FromString(char *);
int RPyExceptionOccurred(void);
char* LLVM_RPython_StartupCode(void);

#define RPyRaiseSimpleException(exctype, errormsg) raise##exctype(errormsg)

// generated by rpython - argggh have to feed in prototypes
RPyFREXP_RESULT *ll_frexp_result(double, int);
RPyMODF_RESULT *ll_modf_result(double, double);
RPySTAT_RESULT *ll_stat_result(int, int, int, int, int, int, int, int, int, int);
void RPYTHON_RAISE_OSERROR(int error);
RPyListOfString *_RPyListOfString_New(int);
void _RPyListOfString_SetItem(RPyListOfString *, int, RPyString *);

// include this to get constants and macros for below includes
#include <Python.h>

// overflows/zeros/values raising operations
#include "raisingop.h"

// append some genc files here manually from python
#include "c/src/thread.h"
#include "c/src/ll_os.h"
#include "c/src/ll_math.h"
#include "c/src/ll_time.h"
#include "c/src/ll_strtod.h"
#include "c/src/ll_thread.h"
#include "c/src/stack.h"

// setup code for ThreadLock Opaque types
char *RPyOpaque_LLVM_SETUP_ThreadLock(struct RPyOpaque_ThreadLock *lock,
				      int initially_locked) {

  struct RPyOpaque_ThreadLock tmp = RPyOpaque_INITEXPR_ThreadLock;
  memcpy(lock, &tmp, sizeof(struct RPyOpaque_ThreadLock));

  if (!RPyThreadLockInit(lock)) {
    return "Thread lock init error";
  }
  if ((initially_locked) && !RPyThreadAcquireLock(lock, 1)) {
    return "Cannot acquire thread lock at init";
  }
  return NULL;
}


char *raw_malloc(int size) {
  return malloc(size);
}

void raw_free(void *ptr) {
  free(ptr);
}

void raw_memcopy(char *ptr1, char *ptr2, int size) {
  memcpy((void *) ptr2, (void *) ptr1, size);
}

#include <gc.h>
#define USING_BOEHM_GC

char *LLVM_RPython_StartupCode();

char *pypy_malloc(unsigned int size) {
  // use the macros luke
  return GC_MALLOC(size);
}

char *pypy_malloc_atomic(unsigned int size) {
  // use the macros luke
  return GC_MALLOC_ATOMIC(size);
}

#ifdef ENTRY_POINT_DEFINED

extern GC_all_interior_pointers;
char *RPython_StartupCode() {
  GC_all_interior_pointers = 0;
  GC_INIT();
  return LLVM_RPython_StartupCode();
}

int __ENTRY_POINT__(RPyListOfString *);

int main(int argc, char *argv[])
{
    char *errmsg;
    int i, exitcode;
    RPyListOfString *list;
    errmsg = RPython_StartupCode();
    if (errmsg) goto error;
    
    list = _RPyListOfString_New(argc);
    if (RPyExceptionOccurred()) goto memory_out;
    for (i=0; i<argc; i++) {
      RPyString *s = RPyString_FromString(argv[i]);

      if (RPyExceptionOccurred()) {
	goto memory_out;
      }

      _RPyListOfString_SetItem(list, i, s);
    }

    exitcode = __ENTRY_POINT__(list);

    if (RPyExceptionOccurred()) {
      goto error; // XXX see genc
    }
    return exitcode;

 memory_out:
    errmsg = "out of memory";
 error:
    fprintf(stderr, "Fatal error during initialization: %s\n", errmsg);
    return 1;
}

#else
extern GC_all_interior_pointers;

char *RPython_StartupCode() {
  GC_all_interior_pointers = 0;
  GC_INIT();
  return LLVM_RPython_StartupCode();
}

int Pyrex_RPython_StartupCode() {

  char *error = RPython_StartupCode();
  if (error != NULL) {
    return 0;
  }
  return 1;
}

#endif /* ENTRY_POINT_DEFINED */

