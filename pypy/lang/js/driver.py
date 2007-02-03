#!/usr/bin/env python

import autopath
from py import path
import os

shell = path.local(__file__).dirpath('test', 'ecma', 'shell.js')

exclusionlist = ['shell.js', 'browser.js']
def filter(filename):
    if filename.basename in exclusionlist or not filename.basename.endswith('.js'):
        return False
    else:
        return True
results = open('results.txt', 'w')
for f in path.local(__file__).dirpath('test', 'ecma').visit(filter):
    print f.basename
    stdout = os.popen('./js_interactive.py -n -f %s -f %s'%(shell.strpath,f.strpath), 'r')
    passed = 0
    total = 0
    for line in stdout.readlines():
        if "PASSED!" in line:
            passed += 1
            total += 1
        elif "FAILED!" in line:
            total += 1
        
    results.write('%s passed %s of %s tests\n'%(f.basename, passed, total))
    results.flush()

            
            
