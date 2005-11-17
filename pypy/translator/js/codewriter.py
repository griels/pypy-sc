import py
from itertools import count
from pypy.translator.js.log import log 

log = log.codewriter 

class CodeWriter(object): 

    tabstring = '  '

    def __init__(self, f, js): 
        self.f = f
        self.js = js
        self._skip_closeblock = False
        self.set_indentation_level(0)

    def skip_closeblock(self, flag=True):
        self._skip_closeblock = flag

    def set_indentation_level(self, indentation_level):
        try:
            old = self.indentation_level
        except:
            old = 0
        self.indentation_level = indentation_level
        return old

    def indent_more(self):
        self.indentation_level += 1

    def indent_less(self):
        self.indentation_level -= 1

    def append(self, line): 
        if line and self.indentation_level:
            s = self.tabstring * self.indentation_level
        else:
            s = ''
        if not line or line[-1] in '{:};' or line.lstrip()[:2] == '//':
            eol = '\n'
        else:
            eol = ';\n'
        self.f.write(s + line + eol)

    def comment(self, line):
        self.append("// " + line)

    def newline(self):
        self.append("")

    def openblock(self, blocknum):
        self.indent_more()
        self.append("case %d:" % blocknum)
        self.indent_more()
        self._current_blocknum = blocknum

    def closeblock(self):
        if not self._skip_closeblock:
            self.append('break')
        self.indent_less()
        self.indent_less()
        self.skip_closeblock(False)

    def declare(self, decl):
        self.append(decl)

    def _goto_block(self, blocknum):
        if blocknum == self._current_blocknum + 1:
            self._skip_closeblock = True
        else:
            self.append('block = ' + str(blocknum))
            self.append('break')

    def _phi(self, exit):
        for i, exitarg in enumerate(exit.args):
            dest = str(exit.target.inputargs[i])
            src = str(self.js.db.repr_arg(exitarg))
            if src == 'False':
                src = 'false'
            elif src == 'True':
                src = 'true'
            elif src == 'None':
                src = 'undefined'
            if dest != src and not dest.startswith('etype_'):
                if dest.startswith('evalue_') and src.startswith('last_exc_value_'):
                    src = 'e'   #i.e. the caught exception
                self.append('%s = %s' % (dest, src))

    def br_uncond(self, blocknum, exit): 
        self._phi(exit)
        self._goto_block(blocknum)
        self.skip_closeblock()

    def br(self, cond, blocknum_false, exit_false, blocknum_true, exit_true):
        self.append('if (%s) {' % cond)
        self.indent_more()
        self._phi(exit_true)
        self._goto_block(blocknum_true)
        self.indent_less()
        self.append('} else {')
        self.indent_more()
        self._phi(exit_false)
        self._goto_block(blocknum_false)
        self.indent_less()
        self.append('}')
        self.skip_closeblock()

    def openfunc(self, decl, funcnode, blocks): 
        self.decl     = decl
        self.funcnode = funcnode
        self.blocks   = blocks
        self._savehandler_blocknum   = 1000
        self._resumehandler_blocknum = 1001
        self._resume_blocknum        = 2000
        self._usedvars = {}
        paramstr = decl.split('(')[1][:-1]
        for param in paramstr.split(','):
            param = param.strip()
            if param:
                self._usedvars[param] = True
        for block in blocks:
            if block != blocks[0]:  #don't double startblock inputargs
                for inputarg in block.inputargs:
                    targetvar = self.js.db.repr_arg(inputarg)
                    self._usedvars[targetvar] = True
            for op in block.operations:
                targetvar = self.js.db.repr_arg(op.result)
                self._usedvars[targetvar] = True

        self.append("function %s {" % self.decl)
        self.indent_more()
        if self._usedvars:
            self.append("var %s" % ', '.join(self._usedvars.keys()))
            
        if self.js.stackless:
            initial_block = "slp_frame_stack_top ? %d : 0" % self._resumehandler_blocknum
        else:
            initial_block = '0'

        self.append("for (block = %s;;) {" % initial_block)
        self.indent_more()
        self.append("switch (block) {")

    def closefunc(self): 
        if self.js.stackless:   #save&restore all local variable for now
            self.openblock(self._savehandler_blocknum)
            self.comment('save block for stackless feature')
            usedvars = ', '.join(self._usedvars.keys())
            self.append('slp_frame_stack_bottom.f_back = slp_new_frame(0, new Array(slp_function, slp_resume_block, slp_targetvar, %s))' % usedvars)    #XXX what should state (here 0) really be?
            self.append('slp_frame_stack_bottom        = slp_frame_stack_bottom.f_back')
            self.comment('and unwind')
            self.append('return')
            self.skip_closeblock()
            self.closeblock()

            self.openblock(self._resumehandler_blocknum)
            self.comment('resume block for stackless feature')
            self.append('%-19s = slp_frame_stack_top.resume_data[1]' % 'block')
            self.append('%-19s = slp_frame_stack_top.resume_data[2]' % 'slp_targetvar')
            for i, k in enumerate(self._usedvars.keys()):
                self.append('%-19s = slp_frame_stack_top.resume_data[%d]' % (k, i+3))
            self.append('slp_frame_stack_top = null')
            self.append('eval(slp_targetvar + " = slp_return_value")')
            self.closeblock()

        self.append("}")    #end of switch
        self.indent_less()
        self.append("}")    #end of forever (block) loop
        self.indent_less()
        self.append("};")   #end of function
        self.newline()

    def ret(self, ref=''): 
        self.append("return " + ref)
        self.skip_closeblock()

    def binaryop(self, name, targetvar, ref1, ref2):
        self.append("%(targetvar)s = %(ref1)s %(name)s %(ref2)s" % locals())

    def neg(self, targetvar, source):
        self.append('%(targetvar)s = -%(source)s' % locals())
        
    def call(self, targetvar, functionref, argrefs, no_exception=None, exceptions=[]):
        args = ", ".join(argrefs)

        if not exceptions:
            assert no_exception is None
            if self.js.stackless:
                self.append('%s = %s(%s)' % (targetvar, functionref, args))
                self.append('if (slp_frame_stack_bottom) { slp_function = %s; slp_targetvar = "%s"; block = %d; slp_resume_block = %d; break; }' %
                    (functionref, targetvar, self._savehandler_blocknum, self._resume_blocknum))
                self.indent_less()
                self.append('case %d:' % self._resume_blocknum)
                self.indent_more()
                self._resume_blocknum += 1
            else:
                self.append('%s = %s(%s)' % (targetvar, functionref, args))
        else:
            assert no_exception is not None
            no_exception_label, no_exception_exit = no_exception
            self.append('try {')
            self.indent_more()
            if self.js.stackless:
                self.comment('TODO: stackless andf exceptions handling')
            self.append('%s = %s(%s)' % (targetvar, functionref, args))
            self._phi(no_exception_exit)
            self._goto_block(no_exception_label)
            self.indent_less()
            
            self.append('} catch (e) {')
            self.indent_more()
            catch_all = False
            for i, exception in enumerate(exceptions):
                exception_match, exception_ref, exception_target, exit = exception
                if i:
                    else_ = 'else '
                else:
                    else_ = ''
                if exception_ref.startswith('structinstance_object_vtable'):
                    catch_all = True
                    matcher   = ''
                else:
                    matcher   = 'if (%s(e.typeptr, %s) == true) ' % (exception_match, exception_ref)
                self.append('%s%s{' % (else_, matcher))
                self.indent_more()
                self._phi(exit)
                self._goto_block(exception_target)
                self.indent_less()
                self.append('}')
            if not catch_all:
                self.append('else {')
                self.indent_more()
                self.throw('e') #reraise exception when not caught above
                self.indent_less()
                self.append('}')

            self.indent_less()
            self.append('}')

    def cast(self, targetvar, fromtype, fromvar, targettype):
        if fromtype == 'void' and targettype == 'void':
                return
        if targettype == fromtype:
            self.append("%(targetvar)s = %(fromvar)s" % locals())
        elif targettype in ('int','uint',):
            self.append("%(targetvar)s = Math.floor(%(fromvar)s)" % locals())
        elif targettype in ('double',):
            self.append("%(targetvar)s = 0.0 + %(fromvar)s" % locals())
        elif targettype in ('bool',):
            self.append("%(targetvar)s = %(fromvar)s == 0" % locals())
        else:
            self.comment("next line should be: %(targetvar)s = cast %(fromtype)s %(fromvar)s to %(targettype)s" % locals())
            self.append("%(targetvar)s = %(fromvar)s" % locals())

    def malloc(self, targetvar, type_):
        self.append('%(targetvar)s = new %(type_)s()' % locals())

    def getelementptr(self, targetvar, type, typevar, *indices):
        res = "%(targetvar)s = getelementptr %(type)s %(typevar)s, word 0, " % locals()
        res += ", ".join(["%s %s" % (t, i) for t, i in indices])
        self.comment(res)

        #res = "%(targetvar)s = %(typevar)s" % locals()
        #res += ''.join(['[%s]' % i for t, i in indices])
        #self.append(res)

    def load(self, destvar, src, srcindices):
        res  = "%(destvar)s = %(src)s" % locals()
        res += ''.join(['[%s]' % index for index in srcindices])
        self.append(res)

    def store(self, dest, destindices, srcvar):
        res  = dest
        res += ''.join(['[%s]' % index for index in destindices])
        res += " = %(srcvar)s" % locals()
        self.append(res)

    def throw(self, exc):
        self.append('throw ' + exc)
