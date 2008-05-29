
from pypy.lang.gameboy import constants
from pypy.lang.gameboy.interrupt import *
from pypy.lang.gameboy.ram import iMemory

class Serial(iMemory):
    """
    PyBoy GameBoy (TM) Emulator
    Serial Link Controller
     """

    def __init__(self, interrupt):
        assert isinstance(interrupt, Interrupt)
        self.interrupt = interrupt
        self.reset()

    def reset(self):
        self.cycles = int(constants.SERIAL_CLOCK)
        self.serial_data = 0x00
        self.serial_control = 0x00

    def get_cycles(self):
        return self.cycles

    def emulate(self, ticks):
        if (self.serial_control & 0x81) != 0x81:
            return
        self.cycles -= ticks
        if self.cycles <= 0:
            self.serial_data = 0xFF
            self.serial_control &= 0x7F
            self.cycles = constants.SERIAL_IDLE_CLOCK
            self.interrupt.raise_interrupt(constants.SERIAL)

    def set_serial_data(self, data):
        self.serial_data = data

    def set_serial_control(self, data):
        self.serial_control = data
        # HACK: delay the serial interrupt
        self.cycles = constants.SERIAL_IDLE_CLOCK + constants.SERIAL_CLOCK

    def get_serial_data(self):
        return self.serial_data

    def get_serial_control(self):
        return self.serial_control

    def write(self, address, data):
        address = int(address)
        if address == constants.SB:
            self.set_serial_data(data)
        elif address == constants.SC:
            self.set_serial_control(data)
            
    def read(self, address):
        address = int(address)
        if address == constants.SB:
            return self.get_serial_data()
        elif address == constants.SC:
            return self.get_serial_control()
        else:
            return 0xFF