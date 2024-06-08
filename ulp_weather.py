from esp32 import ULP
from machine import mem32, Pin
import time

ULP_MEM_BASE = 0x50000000
ULP_DATA_MASK = 0xffff  # ULP data is only in lower 16 bits

class ULP_WEATHER:
    def __init__(self):
        f = open('ulp_two_pins.ulp', 'rb')
        binary = f.read()
        f.close()
        
        self.load_addr = 0
        self.entry_addr = ULP_MEM_BASE + (18*4)
        self.sleep_micro_seconds = 1000
        # setup GPIO pins
        self.wind_pin = Pin(32, Pin.IN, pull=None, hold=True)
        self.rain_pin = Pin(35, Pin.IN, hold=True) # pull down doesn't exist on GPIO35

        #wind vars in ulp 
        # these values are calculated upon a compile of the ULP code.  Currently
        # this is found through watching the console during the compile and noting the 
        # memory offsets.
        self.ulp_wind_io_number = ULP_MEM_BASE + (8*4)
        self.ulp_wind_debounce_counter = ULP_MEM_BASE + (2*4)
        self.ulp_wind_debounce_max_count = ULP_MEM_BASE + (3*4)
        self.ulp_wind_pulse_edge = ULP_MEM_BASE 
        self.ulp_wind_next_edge = ULP_MEM_BASE + (1*4)
        self.ulp_wind_edge_count = ULP_MEM_BASE + (7*4)
        self.ulp_wind_pulse_min = ULP_MEM_BASE + (6*4)

        #rain vars in ulp 
        self.ulp_rain_io_number = ULP_MEM_BASE + (17*4)
        self.ulp_rain_debounce_counter = ULP_MEM_BASE + (11*4)
        self.ulp_rain_debounce_max_count = ULP_MEM_BASE + (12*4)
        self.ulp_rain_pulse_edge = ULP_MEM_BASE + (9*4) 
        self.ulp_rain_next_edge = ULP_MEM_BASE + (10*4)
        self.ulp_rain_edge_count = ULP_MEM_BASE + (16*4)
        self.ulp_rain_pulse_min = ULP_MEM_BASE + (15*4)  

        self.wind_pin = Pin(32, Pin.IN, pull=None, hold=True)
        self.rain_pin = Pin(35, Pin.IN, hold=True) # pull down doesn't exist on GPIO35

        self.ulp = ULP()
        self.ulp.set_wakeup_period(0, self.sleep_micro_seconds)  # use timer0, wakeup after 50.000 cycles
        self.ulp.load_binary(self.load_addr, binary)

        mem32[ULP_MEM_BASE + self.load_addr] = 0x0  # initialise state to 0
        #init starting values for wind
        mem32[self.ulp_wind_io_number] = 0x9  # RTC9, which is GPIO32
        mem32[self.ulp_wind_debounce_counter] = 0x5  # initialise state to 0
        mem32[self.ulp_wind_debounce_max_count] = 0x5  # initialise state to 0
        mem32[self.ulp_wind_pulse_edge] = 0x1  # initialise state to 0
        mem32[self.ulp_wind_next_edge] = 0x1  # initialise state to 0

        #init starting values for rain
        mem32[self.ulp_rain_io_number] = 0x5  # RTC5, which is GPIO35
        mem32[self.ulp_rain_debounce_counter] = 0x5  # initialise state to 0
        mem32[self.ulp_rain_debounce_max_count] = 0x5  # initialise state to 0
        mem32[self.ulp_rain_pulse_edge] = 0x1  # initialise state to 0
        mem32[self.ulp_rain_next_edge] = 0x1  # initialise state to 0 

        self.ulp.run(self.entry_addr)

#    def _speed(self, count, seconds):
#        cup_r = 80 # 80mm radius of wind cups
#        full_circle = (2 * 3.14 * cup_r)
#        rps = count / seconds
#        # meters per second
#        #mps = ((rps * full_circle) / 1000) 
#        #return mps
#        # temp - just return rps
#        return rps
#
#    def windspeed(self, seconds):
#        total_count = mem32[self.wind_counter] & ULP_DATA_MASK
#        gust_count = mem32[self.wind_gust] & ULP_DATA_MASK
#        # clear the counters
#        mem32[self.wind_counter] = 0
#        mem32[self.wind_gust] = 0
#
#        avg_mps = self._speed(total_count, seconds)
#        gust_mps = self._speed(gust_count, 1)
#
#        return avg_mps, gust_mps
#
#    def rainbuckets(self, reset=None):
#        value = int(mem32[self.rain_counter] & ULP_DATA_MASK)
#        # need to either determine volume of each pulse.
#        if reset is True:
#            mem32[self.rain_counter] = 0
#        return value

    def retrieve_metrics(self, seconds):
        dict = {}
        wind_p, rain_p = self.get_pulse_count()
        wind_sp, rain_sp = self.get_shortest_pulse()
        dict['wind_total_pulse_count'] = wind_p
        dict['rain_total_pulse_count'] = rain_p
        dict['wind_avg_pulse_second'] = (wind_p / seconds)
        dict['rain_avg_pulse_second'] = (rain_p / seconds)
        # shortest time in seconds betweeen two detected pulses.
        dict['wind_shortest_pulse'] = wind_sp / 1000000
        dict['rain_shortest_pulse'] = rain_sp / 1000000
        # compute the burst value to pulses per second
        if wind_sp > 0:
            dict['wind_burst_pulse_second'] = 1 / (wind_sp / 1000000)
        else:
            dict['wind_burst_pulse_second'] = 0.0
        if rain_sp > 0:
            dict['rain_burst_pulse_second'] = 1 / (rain_sp / 1000000)
        else:
            dict['rain_burst_pulse_second'] = 0.0

        return dict

    def get_pulse_count(self):
        wind_pulse_count = (mem32[self.ulp_wind_edge_count] & 0xffff) / 2
        mem32[self.ulp_wind_edge_count] = (mem32[self.ulp_wind_edge_count] & 0xffff) % 2
        rain_pulse_count = (mem32[self.ulp_rain_edge_count] & 0xffff) / 2
        mem32[self.ulp_rain_edge_count] = (mem32[self.ulp_rain_edge_count] & 0xffff) % 2
        return wind_pulse_count, rain_pulse_count

    def get_shortest_pulse(self):
        wind_pulse_time_min = (mem32[self.ulp_wind_pulse_min] & 0xffff) * self.sleep_micro_seconds
        mem32[self.ulp_wind_pulse_min] = 0
        rain_pulse_time_min = (mem32[self.ulp_rain_pulse_min] & 0xffff) * self.sleep_micro_seconds
        mem32[self.ulp_rain_pulse_min] = 0
        return wind_pulse_time_min, rain_pulse_time_min