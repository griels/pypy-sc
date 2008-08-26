
from pypy.lang.gameboy import constants
from pypy.lang.gameboy.interrupt import Interrupt
from pypy.lang.gameboy.video import Video
from pypy.lang.gameboy.video import VideoDriver
import py

class Memory(object):
    def __init__(self):
        self.memory = [0xFF]*0xFFFFF
        
    def write(self, address, data):
        self.memory[address] = data
        
    def read(self, address):
        return self.memory[address]

# ----------------------------------------------------------------------------
    
def get_video():
    return Video(get_video_driver(), Interrupt(), Memory())

def get_video_driver():
    return VideoDriver()

# ----------------------------------------------------------------------------


def test_reset():
    video = get_video()
    assert video.cycles == constants.MODE_2_TICKS
    assert video.control.read() == 0x91
    assert video.status.read(extend=False) == 2 
    assert video.status.read(extend=True) == 2 + 0x80
    assert video.line_y == 0
    assert video.line_y_compare == 0
    assert video.dma == 0xFF
    assert video.scroll_x == 0
    assert video.scroll_y == 0
    assert video.window_x == 0
    assert video.window_y == 0
    assert video.window_line_y == 0
    assert video.background_palette == 0xFC
    assert video.object_palette_0 == 0xFF
    assert video.object_palette_1 == 0xFF
    assert video.transfer == True
    assert video.display == True
    assert video.vblank == True
    assert video.dirty == True
    assert len(video.vram) == constants.VRAM_SIZE
    assert len(video.oam) == constants.OAM_SIZE
    assert len(video.line) == 176
    assert len(video.objects) == constants.OBJECTS_PER_LINE
    assert len(video.palette) == 1024
    assert video.frames == 0
    assert video.frame_skip == 0

def test_read_write_properties():
    video = get_video()
    checks = [(0xFF42, "scroll_y"),
              (0xFF43, "scroll_x"), 
              #(0xFF44, "line_y"), read only
              (0xFF45, "line_y_compare"), 
              (0xFF46, "dma"), 
              (0xFF47, "background_palette"), 
              (0xFF48, "object_palette_0"), 
              (0xFF49, "object_palette_1"), 
              (0xFF4A, "window_y"), 
              (0xFF4B, "window_x")]
    counted_value = 0
    for check in checks:
        address = check[0]
        property = check[1]
        value = counted_value
        if len(check) > 2:
            value = check[2]
        video.write(address, value)
        assert video.__getattribute__(property) == value
        assert video.read(address) == value
        counted_value = (counted_value + 1 ) % 0xFF
        
def test_read_write_control():
    video = get_video()
    value = 0x2
    video.write(0xFF40, value)
    assert video.control.read() == value
    assert video.read(0xFF40) == value
    
def test_set_status():
    video = get_video()
    valueA = 0x95
    for valueB in range(0, 0xFF):
        video.status.write(valueB, write_all=True)
        assert video.status.read(extend=True) == valueB
        video.write(0xFF41, valueA)
        assert video.get_status() == (valueB & 0x87) | (valueA & 0x78)
    
    video.control.write(0x80)
    video.status.write(0x01, write_all=True)
    video.write(0xFF41, 0x01)
    assert video.interrupt.lcd.is_pending()
    
    
def test_set_line_y_compare():
    video = get_video()
    value = 0xF6
    video.write(0xFF45, value)
    assert video.line_y_compare == value
    
    video.control.write(0x80)
    video.line_y = value -1
    video.status.write(0xFF, write_all=True)
    assert video.status.read(extend=True) == 0xFF
    video.write(0xFF45, value)
    assert video.status.read(extend=True) == 0xFB
    assert video.interrupt.lcd.is_pending() == False
    
    video.control.write(0x80)
    video.line_y = 0xF6
    video.status.write(0x04, write_all=True)
    video.write(0xFF45, value)
    assert video.status.read(extend=True) == 0x04
    assert video.interrupt.lcd.is_pending() == False
    
    video.control.write(0x80)
    video.line_y = 0xF6
    video.status.write(0x00, write_all=True)
    video.write(0xFF45, value)
    assert video.status.read(extend=True) == 0x04
    assert video.interrupt.lcd.is_pending() == False
    
    video.control.write(0x80)
    video.line_y = 0xF6
    video.status.write(0x40, write_all=True)
    video.write(0xFF45, value)
    assert video.status.read(extend=True) == 0x44
    assert video.interrupt.lcd.is_pending() == True
    
    
    
def test_control():
    video = get_video()
    
    video.control.write(0x80)
    video.window_line_y = 1
    video.write(0xFF40, 0x80)
    assert video.control.read() == 0x80
    assert video.window_line_y == 1
    
def test_control_window_draw_skip():
    video = get_video()   
    video.control.write(0x80)
    video.window_y = 0
    video.line_y = 1
    video.window_line_y = 0
    video.write(0xFF40, 0x80+0x20)
    assert video.control.read() == 0x80+0x20
    assert video.window_line_y == 144
 
def test_control_reset1():
    video = get_video()   
    video.control.write(0)
    video.status.write(0x30, write_all=True)
    video.line_y = 1
    video.display = True
    video.write(0xFF40, 0x80)
    assert video.control.read() == 0x80
    assert video.status.read(extend=True) == 0x30 + 0x02
    assert video.cycles == constants.MODE_2_TICKS
    assert video.line_y == 0
    assert video.display == False
    
def test_control_reset2():
    video = get_video()   
    video.control.write(0x80)
    video.status.write(0x30, write_all=True)
    video.line_y = 1
    video.display = True
    video.write(0xFF40, 0x30)
    assert video.control.read() == 0x30
    assert video.status.read(extend=True) == 0x30
    assert video.cycles == constants.MODE_1_TICKS
    assert video.line_y == 0
    assert video.display == True
    
def test_video_dirty_properties():
    video = get_video()
    video.background_palette = 0
    video.dirty = False
    video.write(0xFF47, 0)
    assert video.dirty == False
    assert video.dirty == 0
    video.write(0xFF47, 1)
    assert video.dirty == True
    assert video.background_palette == 1
    video.dirty = False
    video.write(0xFF47, 1)
    assert video.dirty == False
    
    
    video.object_palette_0 = 0
    video.write(0xFF48, 0)
    assert video.dirty == False
    assert video.object_palette_0 == 0
    video.write(0xFF48, 1)
    assert video.dirty == True
    assert video.object_palette_0 == 1
    video.dirty = False
    video.write(0xFF48, 1)
    assert video.dirty == False
    
    
    video.object_palette_1 = 0
    video.write(0xFF49, 0)
    assert video.dirty == False
    assert video.object_palette_1 == 0
    video.write(0xFF49, 1)
    assert video.dirty == True
    assert video.object_palette_1 == 1
    video.dirty = False
    video.write(0xFF49, 1)
    assert video.dirty == False
    
    
def test_emulate_OAM():
    video = get_video()
    video.transfer = False
    video.status.write(0xFE, write_all=True)
    video.cycles = 0
    video.emulate_oam()
    assert video.status.read(extend=True) == 0xFF
    assert video.cycles == constants.MODE_3_BEGIN_TICKS
    assert video.transfer == True
    
def test_emulate_transfer():
    video = get_video()
    
    video.transfer = False
    video.cycles = 0
    video.status.write(0xF0, write_all=True)
    video.emulate_transfer()
    assert video.status.read(extend=True) == 0xF0
    assert video.cycles == constants.MODE_0_TICKS
    assert not video.interrupt.lcd.is_pending()
    
    video.transfer = False
    video.cycles = 0
    video.status.write(0xF8, write_all=True)
    assert not video.interrupt.lcd.is_pending()
    video.emulate_transfer()
    assert video.status.read(extend=True) == 0xF8
    assert video.cycles == constants.MODE_0_TICKS
    assert video.interrupt.lcd.is_pending()
    
    video.transfer = True
    video.cycles = 0
    video.status.write(0xFC, write_all=True)
    video.emulate_transfer()
    assert video.cycles == constants.MODE_3_END_TICKS
    assert video.transfer == False
    assert video.status.read(extend=True) == 0xFF
   
   
def test_emulate_hblank_line_y_compare():
    video = get_video()
    video.line_y = 0x12
    video.line_y_compare = 0x13
    video.status.line_y_compare_flag = True
    video.status.line_y_compare_interrupt = False
    video.emulate_hblank_line_y_compare()
    assert not video.status.line_y_compare_flag
    assert not video.interrupt.lcd.is_pending()
    
    video.reset()
    video.line_y = 0x12
    video.line_y_compare = 0x12
    video.status.line_y_compare_flag = False
    video.status.line_y_compare_interrupt = False
    video.emulate_hblank_line_y_compare()
    assert video.status.line_y_compare_flag
    assert not video.interrupt.lcd.is_pending()
    
    video.reset()
    video.line_y = 0x12
    video.line_y_compare = 0x12
    video.status.line_y_compare_flag = False
    video.status.line_y_compare_interrupt = True
    video.emulate_hblank_line_y_compare()
    assert video.status.line_y_compare_flag
    assert video.interrupt.lcd.is_pending()
    
def test_emulate_hblank_line_y_compare_status_check():
    video = get_video()   
    video.line_y = 0x12
    video.line_y_compare = 0x12
    video.status.line_y_compare_flag = True
    video.status.line_y_compare_interrupt = True
    video.emulate_hblank_line_y_compare(stat_check=True)
    assert video.status.line_y_compare_flag
    assert not video.interrupt.lcd.is_pending()
    
    video.reset()
    video.line_y = 0x12
    video.line_y_compare = 0x12
    video.status.line_y_compare_flag = False
    video.status.line_y_compare_interrupt = True
    video.emulate_hblank_line_y_compare(stat_check=True)
    assert video.status.line_y_compare_flag
    assert video.interrupt.lcd.is_pending()

def test_emulate_h_blank_part_1_1():
    video = get_video()
    video.line_y = 0
    video.line_y_compare = 1
    video.status.write(0x20, write_all=True)
    video.cycles = 0
    video.frames = 0
    assert not video.interrupt.lcd.is_pending()
    video.emulate_hblank()
    assert video.cycles == constants.MODE_2_TICKS
    assert video.interrupt.lcd.is_pending()
    assert video.status.get_mode() == 2
    assert video.status.read(extend=True) == 0x20 + 0x04 + 0x2
    assert video.line_y == 1
    assert video.frames == 0
    
    
def test_emulate_h_blank_part_2_1():
    video = get_video()
    video.line_y = 1
    video.line_y_compare = 0
    video.status.write(0x0F, write_all=True)
    video.cycles = 0
    video.frames = 0
    video.emulate_hblank()
    assert video.line_y == 2
    assert video.cycles == constants.MODE_2_TICKS
    assert not video.interrupt.lcd.is_pending()
    assert video.status.read(extend=True) == 0x0B&0xFC + 0x2
    assert video.frames == 0
    
def test_emulate_h_blank_part_2_2():
    video = get_video()
    video.line_y = 144
    video.line_y_compare = 0
    video.status.write(0xFB, write_all=True)
    video.cycles = 0
    video.frames = 0
    video.frame_skip = 20
    video.vblank = False
    video.display = False
    video.emulate_hblank()
    assert video.line_y == 145
    assert video.cycles == constants.MODE_1_BEGIN_TICKS
    assert not video.interrupt.lcd.is_pending()
    assert video.status.read(extend=True) == 0xFB & 0xFC + 0x01
    assert video.frames == 1
    assert video.display == False
    assert video.vblank == True
    

def test_emulate_h_blank_part_2_2_frame_skip():
    video = get_video()
    video.line_y = 144
    video.line_y_compare = 0
    video.status.write(0xFB, write_all=True)
    video.cycles = 0
    video.frames = 10
    video.frame_skip = 10
    video.vblank = False
    video.display = False
    video.emulate_hblank()
    assert video.line_y == 145
    assert video.cycles == constants.MODE_1_BEGIN_TICKS
    assert not video.interrupt.lcd.is_pending()
    assert video.status.read(extend=True) == 0xFB & 0xFC + 0x01
    assert video.frames == 0
    assert video.vblank == True
    
    
def test_emulate_v_vblank_1():
    video = get_video()   
    video.interrupt.set_interrupt_flag(0)
    video.status.write(0xFE, write_all=True)
    video.vblank = True
    video.cycles = 0
    video.emulate_vblank()
    assert video.vblank == False
    assert video.status.get_mode() == 1
    assert video.status.read(extend=True) == 0xFD
    assert video.cycles == constants.MODE_1_TICKS - constants.MODE_1_BEGIN_TICKS
    assert video.interrupt.vblank.is_pending()
    assert video.interrupt.lcd.is_pending()
    
    video.interrupt.set_interrupt_flag(0)
    video.status.write(0x00, write_all=True)
    video.vblank = True
    assert not video.interrupt.vblank.is_pending()
    assert not video.interrupt.lcd.is_pending()
    video.emulate_vblank()
    assert video.status.read(extend=True) == 0x01
    assert video.interrupt.vblank.is_pending()
    assert not video.interrupt.lcd.is_pending()
    
    
    
def test_emulate_v_vblank_2():
    video = get_video()   
    video.interrupt.set_interrupt_flag(0)
    video.status.write(0x2D, write_all=True)
    video.vblank = False
    video.cycles = 0
    video.line_y = 0
    video.emulate_vblank()
    assert video.vblank == False
    assert video.status.read(extend=True) == 0x2E
    assert video.cycles == constants.MODE_2_TICKS 
    assert not video.interrupt.vblank.is_pending()
    assert video.interrupt.lcd.is_pending()
    
    video.interrupt.set_interrupt_flag(0)
    video.cycles = 0
    video.status.write(0xFD, write_all=True)
    video.emulate_vblank()
    assert video.vblank == False
    assert video.status.read(extend=True) == 0xFE
    assert video.cycles == constants.MODE_2_TICKS 
    assert not video.interrupt.lcd.is_pending()
