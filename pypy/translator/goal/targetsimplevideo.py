from pypy.rlib.rsdl import RSDL, RSDL_helper
from pypy.rpython.lltypesystem import rffi, lltype
import py

WIDTH = 200
HEIGHT = 200

def entry_point(argv=None):
    RSDL.Init(RSDL.INIT_VIDEO) >= 0
    screen = RSDL.SetVideoMode(WIDTH, HEIGHT, 32, 0)
    event = lltype.malloc(RSDL.Event, flavor='raw')
    try:
        while True:
            ok = RSDL.WaitEvent(event)
            assert rffi.cast(lltype.Signed, ok) == 1
            c_type = rffi.getintfield(event, 'c_type')
            if c_type == RSDL.KEYDOWN:
                p = rffi.cast(RSDL.KeyboardEventPtr, event)
                if rffi.getintfield(p.c_keysym, 'c_sym') == RSDL.K_ESCAPE:
                    print 'Escape key'
                    break
            update_screen(screen)
    finally:
        lltype.free(event, flavor='raw')
        
# -----------------------------------------------------------------------------

def chess(screen, cola, colb):
    for i in xrange(WIDTH):
        for j in xrange(HEIGHT):
            if (i+j) % 2:
                c = cola
            else:
                c = colb
            RSDL_helper.set_pixel(screen, i, j, c)
                
def white(screen, cola, colb):
    for i in xrange(WIDTH):
        for j in xrange(HEIGHT):
            RSDL_helper.set_pixel(screen, i, j, colb)
                
def black(screen, cola, colb):
    for i in xrange(WIDTH):
        for j in xrange(HEIGHT):
            RSDL_helper.set_pixel(screen, i, j, cola)
                
def stripes_v(screen, cola, colb):
    for i in xrange(WIDTH):
        for j in xrange(HEIGHT):
            k = j*WIDTH + i
            if k % 2:
                c = cola
            else:
                c = colb
            RSDL_helper.set_pixel(screen, i, j, c)
                
def stripes_m(screen, cola, colb):
    for j in xrange(WIDTH):
        for i in xrange(HEIGHT):
            k = j*WIDTH + i
            if k % 2:
                c = cola
            else:
                c = colb
            RSDL_helper.set_pixel(screen, i, j, c)
            

# -----------------------------------------------------------------------------

pattern = (chess, white, black, stripes_v, stripes_m)
current_pattern_id = 0
def update_screen(screen):
    fmt = self.screen.c_format
    white = RSDL.MapRGB(fmt, 255, 255, 255)
    black = RSDL.MapRGB(fmt, 0, 0, 0)
    RSDL.LockSurface(self.screen)
    pattern[current_pattern_id % len(pattern)](screen, black, white)
    RSDL.UnlockSurface(self.screen)
    RSDL.Flip(self.screen)
    current_pattern_id += 1
    
    
# -----------------------------------------------------------------------------

def target(*args):
    return entry_point, None


if __name__ == '__main__':
    entry_point()


