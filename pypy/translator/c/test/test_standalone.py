from pypy.translator.translator import TranslationContext
from pypy.translator.c.genc import CStandaloneBuilder
from pypy.annotation.listdef import s_list_of_strings
import os


def test_hello_world():
    def entry_point(argv):
        os.write(1, "hello world\n")
        argv = argv[1:]
        os.write(1, "argument count: " + str(len(argv)) + "\n")
        for s in argv:
            os.write(1, "   '" + str(s) + "'\n")
        return 0

    t = TranslationContext()
    t.buildannotator().build_types(entry_point, [s_list_of_strings])
    t.buildrtyper().specialize()

    cbuilder = CStandaloneBuilder(t, entry_point)
    cbuilder.generate_source()
    cbuilder.compile()
    data = cbuilder.cmdexec('hi there')
    assert data.startswith('''hello world\nargument count: 2\n   'hi'\n   'there'\n''')

def test_print():
    def entry_point(argv):
        print "hello simpler world"
        argv = argv[1:]
        print "argument count:", len(argv)
        print "arguments:", argv
        print "argument lengths:",
        print [len(s) for s in argv]
        return 0

    t = TranslationContext()
    t.buildannotator().build_types(entry_point, [s_list_of_strings])
    t.buildrtyper().specialize()

    cbuilder = CStandaloneBuilder(t, entry_point)
    cbuilder.generate_source()
    cbuilder.compile()
    data = cbuilder.cmdexec('hi there')
    assert data.startswith('''hello simpler world\n'''
                           '''argument count: 2\n'''
                           '''arguments: [hi, there]\n'''
                           '''argument lengths: [2, 5]\n''')
    # NB. RPython has only str, not repr, so str() on a list of strings
    # gives the strings unquoted in the list
