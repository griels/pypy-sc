//implementation for using the LLVM JIT

#include "libllvmjit.h"

#include "llvm/Module.h"
#include "llvm/Assembly/Parser.h"
#include "llvm/Bytecode/Writer.h"
#include "llvm/Analysis/Verifier.h"
#include "llvm/Support/CommandLine.h"
#include "llvm/Support/SystemUtils.h"
#include "llvm/System/Signals.h"
#include "llvm/ModuleProvider.h"
#include "llvm/ExecutionEngine/JIT.h"
#include "llvm/ExecutionEngine/Interpreter.h"
#include "llvm/ExecutionEngine/GenericValue.h"
#include <fstream>
#include <iostream>
#include <memory>

using namespace llvm;


ExecutionEngine*    g_execution_engine;


void    restart() {
    delete g_execution_engine; //XXX test if this correctly cleans up including generated code
    g_execution_engine = NULL;
}


int     compile(const char* llsource) {
    Module*     module = ParseAssemblyString(llsource, new Module("llvmjit"));
    if (!module) {
        std::cerr << "Error: can not parse " << llsource << "\n" << std::flush;
        return false;
    }

    //std::ostream *Out = new std::ofstream("temp-libllvmjit.bc",
    //        std::ios::out | std::ios::trunc | std::ios::binary);
    //WriteBytecodeToFile(module, *Out); //XXX what to do with the 3rd param (NoCompress)?

    ModuleProvider* module_provider = new ExistingModuleProvider(module);
    if (!g_execution_engine) {
        g_execution_engine = ExecutionEngine::create(module_provider, false);
    } else {
        g_execution_engine->addModuleProvider(module_provider);
    }

    return true;
}


void*   find_function(const char* name) {
    if (!g_execution_engine)    return NULL; //note: decided not to be treated as an error

    return g_execution_engine->FindFunctionNamed(name); //note: can be NULL
}


int     execute(const void* function, int param) { //XXX allow different function signatures
    if (!g_execution_engine) {
        std::cerr << "Error: no llvm code compiled yet!\n" << std::flush;
        return -1;
    }

    if (!function) {
        std::cerr << "Error: no function supplied to libllvmjit.execute(...)\n" << std::flush;
        return -1;
    }

    std::vector<GenericValue> args;
    args.push_back((void*)param);

    GenericValue gv = g_execution_engine->runFunction((Function*)function, args);
    return gv.IntVal;
}

