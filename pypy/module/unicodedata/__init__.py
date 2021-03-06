from pypy.interpreter.mixedmodule import MixedModule
    
class Module(MixedModule):
    appleveldefs = {
    }
    interpleveldefs = {
        'unidata_version' : 'space.wrap(interp_ucd.ucd.version)',
        'ucd_3_2_0'       : 'space.wrap(interp_ucd.ucd_3_2_0)',
        #'ucd_4_1_0'       : 'space.wrap(interp_ucd.ucd_4_1_0)',
        #'ucd_5_0_0'       : 'space.wrap(interp_ucd.ucd_5_0_0)',
        'ucd'             : 'space.wrap(interp_ucd.ucd)',
        '__doc__'         : "space.wrap('unicode character database')",
    }
    for name in '''lookup name decimal digit numeric category bidirectional
                   east_asian_width combining mirrored decomposition
                   normalize'''.split():
        interpleveldefs[name] = '''space.getattr(space.wrap(interp_ucd.ucd),
                                   space.wrap("%s"))''' % name
