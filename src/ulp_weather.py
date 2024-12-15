from esp32 import ULP
from machine import mem32
import time

ULP_MEM_BASE = 0x50000000
ULP_DATA_MASK = 0xffff  # ULP data is only in lower 16 bits

class ULP_WEATHER:
    def __init__(self):
        f = open('ulp_two_pins.ulp', 'rb')
        binary = f.read()
        f.close()
        
        self.load_addr = 0
        self.entry_addr = ULP_MEM_BASE + (16*4)
        self.sleep_micro_seconds = 5000

        # rain total holder
        self.rain_buckets_counter = 0
        #wind vars in ulp 
        # these values are calculated upon a compile of the ULP code.  Currently
        # this is found through watching the console during the compile and noting the 
        # memory offsets.
        self.ulp_wind_debounce_counter = ULP_MEM_BASE + (2*4)
        self.ulp_wind_debounce_max_count = ULP_MEM_BASE + (3*4)
        self.ulp_wind_pulse_edge = ULP_MEM_BASE 
        self.ulp_wind_next_edge = ULP_MEM_BASE + (1*4)
        self.ulp_wind_edge_count = ULP_MEM_BASE + (7*4)
        self.ulp_wind_pulse_min = ULP_MEM_BASE + (6*4)

        #rain vars in ulp 
        self.ulp_rain_debounce_counter = ULP_MEM_BASE + (10*4)
        self.ulp_rain_debounce_max_count = ULP_MEM_BASE + (11*4)
        self.ulp_rain_pulse_edge = ULP_MEM_BASE + (8*4) 
        self.ulp_rain_next_edge = ULP_MEM_BASE + (9*4)
        self.ulp_rain_edge_count = ULP_MEM_BASE + (15*4)
        self.ulp_rain_pulse_min = ULP_MEM_BASE + (14*4)  

        self.ulp = ULP()
        self.ulp.set_wakeup_period(0, self.sleep_micro_seconds)
        self.ulp.load_binary(self.load_addr, binary)

        mem32[ULP_MEM_BASE + self.load_addr] = 0x0  # initialise state to 0
        # init starting values for wind
        # min pulse calc.   sleep_micro_seconds * debounce_counter + 1.  5ms * 4 = 20ms
        mem32[self.ulp_wind_debounce_counter] = 0x1
        mem32[self.ulp_wind_debounce_max_count] = 0x1
        mem32[self.ulp_wind_pulse_edge] = 0x1
        mem32[self.ulp_wind_next_edge] = 0x1

        # init starting values for rain
        mem32[self.ulp_rain_debounce_counter] = 0x1 
        mem32[self.ulp_rain_debounce_max_count] = 0x1 
        mem32[self.ulp_rain_pulse_edge] = 0x1  
        mem32[self.ulp_rain_next_edge] = 0x1

        self.ulp.run(self.entry_addr)
    
    def increment_rain_holder(self, count):
        self.rain_buckets_counter += count
        return self.rain_buckets_counter

    def retrieve_metrics(self, seconds):
        dict = {}
        wind_p, rain_p = self.get_pulse_count()
        wind_sp, rain_sp = self.get_shortest_pulse(seconds)
        dict['wind_total_pulse_count'] = wind_p
        dict['rain_total_pulse_count'] = rain_p
        dict['wind_avg_pulse_second'] = (wind_p / seconds)
        dict['rain_avg_pulse_second'] = (rain_p / seconds)
        # shortest time in seconds betweeen two detected pulses.
        dict['wind_burst_pulse_second'] = wind_sp 
        dict['rain_burst_pulse_second'] = rain_sp 
        # total number of rain buckets since boot
        dict['rain_total_pulse_counter'] = self.increment_rain_holder(rain_p)
        return dict

    def get_pulse_count(self):
        wind_pulse_count = int((mem32[self.ulp_wind_edge_count] & 0xffff) / 2)
        mem32[self.ulp_wind_edge_count] = (mem32[self.ulp_wind_edge_count] & 0xffff) % 2
        rain_pulse_count = int((mem32[self.ulp_rain_edge_count] & 0xffff) / 2)
        mem32[self.ulp_rain_edge_count] = (mem32[self.ulp_rain_edge_count] & 0xffff) % 2
        return wind_pulse_count, rain_pulse_count

    def get_shortest_pulse(self,seconds):
        wind_pulse_time_us = (mem32[self.ulp_wind_pulse_min] & 0xffff) * self.sleep_micro_seconds
        mem32[self.ulp_wind_pulse_min] = 0
        wind_pulse_time_min = self.compute_shortest_pulse(wind_pulse_time_us, seconds)
        rain_pulse_time_us = (mem32[self.ulp_rain_pulse_min] & 0xffff) * self.sleep_micro_seconds
        mem32[self.ulp_rain_pulse_min] = 0
        rain_pulse_time_min = self.compute_shortest_pulse(rain_pulse_time_us, seconds)
        return wind_pulse_time_min, rain_pulse_time_min

    def compute_shortest_pulse(self, short_pulse, seconds):
        if short_pulse == 0:
            return 0.0
        # inverse and convert to seconds
        pulse_per_second = 1 / (short_pulse / 1000000) 
        if pulse_per_second > seconds:
            return seconds
        else:
            return pulse_per_second