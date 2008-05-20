
from pypy.lang.gameboy import constants
from pypy.lang.gameboy.interrupt import *
from pypy.lang.gameboy.serial import *


def get_serial():
    return Serial(Interrupt())

def test_reset():
    serial = get_serial()
    serial.cycles = 12
    serial.sb = 12
    serial.sc = 12
    serial.reset()
    assert serial.cycles == constants.SERIAL_CLOCK
    assert serial.sb == 0
    assert serial.sc == 0
    
    
def test_set_serial_control():
    serial = get_serial()
    value = 0x12
    serial.set_serial_control(value)
    assert serial.get_serial_control() == value
    assert serial.cycles == constants.SERIAL_IDLE_CLOCK + constants.SERIAL_CLOCK
    
    
def test_emulate():
    serial = get_serial()
    serial.sc = 0x00
    serial.emulate(20)
    assert serial.cycles == constants.SERIAL_CLOCK
    assert serial.sb == 0
    assert serial.sc == 0
    
    serial.reset()
    serial.sc = 0x81
    serial.cycles = 10
    cycles = serial.cycles
    serial.emulate(2)
    assert serial.cycles > 0
    assert cycles-serial.cycles == 2
    assert serial.sb == 0
    assert serial.sc == 0x81
    assert serial.interrupt.serial.is_pending() == False
    
    serial.reset()
    serial.sc = 0x81
    serial.cycles = 0
    serial.emulate(2)
    assert serial.sb == 0xFF
    assert serial.sc == 0x81 & 0x7F
    assert serial.cycles == constants.SERIAL_IDLE_CLOCK
    assert serial.interrupt.serial.is_pending() == True
    
    
def test_read_write():
    serial = get_serial()
    value = 0x12
    serial.write(constants.SB, value)
    assert serial.read(constants.SB) == value
    assert serial.sb == value 
    
    value += 1
    serial.write(constants.SC, value)
    assert serial.read(constants.SC) == value
    assert serial.sc == value
    
    assert serial.read(0) == 0xFF
    