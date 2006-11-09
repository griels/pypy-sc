from pypy.jit.codegen.ppc.instruction import \
     gprs, fprs, crfs, ctr, \
     NO_REGISTER, GP_REGISTER, FP_REGISTER, CR_FIELD, CT_REGISTER, \
     CMPInsn, Spill, Unspill, stack_slot, \
     rSCRATCH

class RegisterAllocation:
    def __init__(self, freeregs, initial_mapping, initial_spill_offset):
        #print
        #print "RegisterAllocation __init__", initial_mapping

        self.insns = []   # output list of instructions

        # registers with dead values
        self.freeregs = {}
        for regcls in freeregs:
            self.freeregs[regcls] = freeregs[regcls][:]

        self.var2loc = {} # maps Vars to AllocationSlots
        self.lru = []     # least-recently-used list of vars; first is oldest.
                          # contains all vars in registers, and no vars on stack

        self.spill_offset = initial_spill_offset # where to put next spilled
                                                 # value, relative to rFP,
                                                 # measured in bytes
        self.free_stack_slots = [] # a free list for stack slots

        # go through the initial mapping and initialize the data structures
        for var, loc in initial_mapping.iteritems():
            self.set(var, loc)
            if loc.is_register and loc in self.freeregs[loc.regclass]:
                self.freeregs[loc.regclass].remove(loc)
                self.lru.append(var)

        # crfinfo is a bit of a hack used to transmit which bit a compare
        # instruction set to the branch instruction
        self.crfinfo = [(0, 0)] * 8

    def set(self, var, loc):
        assert var not in self.var2loc
        self.var2loc[var] = loc

    def forget(self, var, loc):
        assert self.var2loc[var] is loc
        del self.var2loc[var]

    def loc_of(self, var):
        return self.var2loc[var]

    def spill_slot(self):
        """ Returns an unused stack location. """
        if self.free_stack_slots:
            return self.free_stack_slots.pop()
        else:
            self.spill_offset -= 4
            return stack_slot(self.spill_offset)

    def _allocate_reg(self, regclass, newarg):

        # check if there is a register available
        freeregs = self.freeregs[regclass]

        if freeregs:
            reg = freeregs.pop()
            self.set(newarg, reg)
            #print "allocate_reg: Putting %r into fresh register %r" % (newarg, reg)
            return reg

        # if not, find something to spill
        for i in range(len(self.lru)):
            argtospill = self.lru[i]
            reg = self.loc_of(argtospill)
            assert reg.is_register
            if reg.regclass == regclass:
                del self.lru[i]
                break
        else:
            assert 0

        # Move the value we are spilling onto the stack, both in the
        # data structures and in the instructions:

        self.forget(argtospill, reg)
        spill = self.spill_slot()
        if regclass != GP_REGISTER:
            self.insns.append(reg.move_to_gpr(self, 0))
            spillfrom_reg = gprs[0]
        else:
            spillfrom_reg = reg
        self.insns.append(Spill(argtospill, spillfrom_reg, spill))
        self.set(argtospill, spill)

        #print "allocate_reg: Spilled %r to %r." % (argtospill, spill)

        # update data structures to put newarg into the register
        self.set(newarg, reg)
        #print "allocate_reg: Put %r in stolen reg %r." % (newarg, reg)
        return reg

    def _promote(self, arg):
        if arg in self.lru:
            self.lru.remove(arg)
        self.lru.append(arg)

    def allocate_for_insns(self, insns):
        from pypy.jit.codegen.ppc.rgenop import Var

        insns2 = []

        # make a pass through the instructions, loading constants into
        # Vars where needed.
        for insn in insns:
            newargs = []
            for arg in insn.reg_args:
                if not isinstance(arg, Var):
                    newarg = Var()
                    arg.load(insns2, newarg)
                    newargs.append(newarg)
                else:
                    newargs.append(arg)
            insn.reg_args[0:len(newargs)] = newargs
            insns2.append(insn)

        # Walk through instructions in forward order
        for insn in insns2:

            #print "Processing instruction", insn,
            #print "with args", insn.reg_args, "and result", insn.result, ":"

            #print "LRU list was:", self.lru

            # put things into the lru
            for arg in insn.reg_args:
                self._promote(arg)
            if insn.result:
                self._promote(insn.result)
            #print "LRU list is now:", self.lru

            # We need to allocate a register for each used
            # argument that is not already in one
            for i in range(len(insn.reg_args)):
                arg = insn.reg_args[i]
                argcls = insn.reg_arg_regclasses[i]
                #print "Allocating register for", arg, "..."
                argloc = self.loc_of(arg)

                if not argloc.is_register:
                    # It has no register now because it has been spilled
                    self.forget(arg, argloc)
                    newargloc = self._allocate_reg(argcls, arg)
                    self.insns.append(Unspill(arg, newargloc, argloc))
                    self.free_stack_slots.append(argloc)
                elif argloc.regclass != argcls:
                    # it's in the wrong kind of register
                    # (this code is excessively confusing)
                    self.forget(arg, argloc)
                    if argloc.regclass != GP_REGISTER:
                        if argcls == GP_REGISTER:
                            gpr = self._allocate_reg(GP_REGISTER, arg).number
                        else:
                            gpr = rSCRATCH
                        self.insns.append(
                            argloc.move_to_gpr(self, gpr))
                    else:
                        gpr = argloc.number
                    if argcls != GP_REGISTER:
                        newargloc = self._allocate_reg(argcls, arg)
                        self.insns.append(
                            newargloc.move_from_gpr(self, gpr))
                else:
                    #print "it was in ", argloc
                    pass

            # Need to allocate a register for the destination
            assert not insn.result or insn.result not in self.var2loc
            if insn.result_regclass != NO_REGISTER:
                #print "Allocating register for result %r..." % (insn.result,)
                resultreg = self._allocate_reg(insn.result_regclass, insn.result)
                if isinstance(insn, CMPInsn):
                    self.crfinfo[resultreg.number] = insn.info
            insn.allocate(self)
            self.insns.append(insn)
        return self.insns
