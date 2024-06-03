from esp32 import ULP
from machine import mem32
import time
from esp32_ulp import src_to_binary

source = """\
#define DR_REG_RTCIO_BASE            0x3ff48400
#define RTC_IO_TOUCH_PAD0_REG        (DR_REG_RTCIO_BASE + 0x94)
#define RTC_IO_TOUCH_PAD0_MUX_SEL_M  (BIT(19))
#define RTC_IO_TOUCH_PAD0_FUN_IE_M   (BIT(13))
#define RTC_GPIO_IN_REG              (DR_REG_RTCIO_BASE + 0x24)
#define RTC_GPIO_IN_NEXT_S           14
.set wind_pin, 9  # GPIO32 / RTC_GPIO9 wind anonmeter pin
.set rain_pin, 5  # GPIO35 RTC_GPIO5, rain bucket pin
.set max_histogram_slots, 10
.set max_histogram_bytes, max_histogram_slots * 4
.set loops_per_sec, 200

wind_status:
        .long 0

wind_status_next:
        .long 0

rain_status:
        .long 0

rain_status_next:
        .long 0

        .global wind_counter
wind_counter:
        .long 0

        .global wind_gust
wind_gust:
        .long 0

wind_holder:
        .long 0

        .global rain_counter
rain_counter:
        .long 0

        .text

incr_wind_counter:
        move r3, wind_counter
        ld r2, r3, 0
        add r2, r2, 1
        st r2, r3, 0
        # increment the wind_holder
        move r3, wind_holder
        ld r2, r3, 0
        add r2, r2, 1
        st r2, r3, 0
        #check if wind_holder is more than wind_gust
        move r3, wind_gust
        ld r1, r3, 0
        add r1, r1, 1
        sub r1, r1, r2
        jump update_gust, eq 
        jump rain_check

update_gust:
        move r3, wind_gust
        #r2 is the current wind_holder
        st r2, r3, 0        
        jump rain_check

wind_status_changed:
        move r3, wind_status_next
        ld r2, r3, 0
        add r2, r2, 1
        and r2, r2, 1
        st r2, r3, 0

        jump incr_wind_counter, eq
        
        jump rain_check

rain_status_changed:
        move r3, rain_status_next
        ld r2, r3, 0
        add r2, r2, 1
        and r2, r2, 1
        st r2, r3, 0

        jump incr_rain_counter, eq
        jump loop_incr

incr_rain_counter:
        move r3, rain_counter
        ld r2, r3, 0
        add r2, r2, 1
        st r2, r3, 0
        jump loop_incr

reset_counter:
        # reset stage to 0
        STAGE_RST
        # reset wind_holder to 0
        move r3, wind_holder
        move r1, 0
        st r1, r3, 0

        halt


    .global entry
entry:
        READ_RTC_REG(RTC_GPIO_IN_REG, RTC_GPIO_IN_NEXT_S, 16)
        move r1, r0

        # set wind_status, RTC4, GPIO34
        move r3, wind_status
        rsh r0, r1, wind_pin
        and r0, r0, 1
        st r0, r3, 0

        # set rain_status, RTC5, GPIO35
        move r3, rain_status
        rsh r0, r1, rain_pin
        and r0, r0, 1
        st r0, r3, 0

        # see if wind_status is changed
        rsh r0, r1, wind_pin
        and r0, r0, 1
        move r3, wind_status_next
        ld r3, r3, 0
        add r3, r0, r3
        and r3, r3, 1
        jump wind_status_changed, eq        

rain_check:
        # see if rain_status is changed
        rsh r0, r1, rain_pin
        and r0, r0, 1
        move r3, rain_status_next
        ld r3, r3, 0
        add r3, r0, r3
        and r3, r3, 1
        jump rain_status_changed, eq        

loop_incr:
        # increment loop_counter        
        STAGE_INC 1

        JUMPS reset_counter, 200, EQ
        halt
"""
ULP_MEM_BASE = 0x50000000
ULP_DATA_MASK = 0xffff  # ULP data is only in lower 16 bits

class ULP_WEATHER:
    def __init__(self):
        self.binary = src_to_binary(source, cpu="esp32")  
        self.load_addr = 0
        # these values are calculated upon a compile of the ULP code.  Currently
        # this is found through watching the console during the compile and noting the 
        # memory offsets.
        self.entry_addr = ULP_MEM_BASE + (49*4)
        self.wind_counter = ULP_MEM_BASE + (4*4)
        self.wind_gust = ULP_MEM_BASE + (5*4)
        self.rain_counter = ULP_MEM_BASE +(7*4)

        ulp = ULP()
        ulp.set_wakeup_period(0, 5000)  # use timer0, wakeup after 50.000 cycles
        ulp.load_binary(self.load_addr, self.binary)

        mem32[ULP_MEM_BASE + self.load_addr] = 0x0  # initialise state to 0
        ulp.run(self.entry_addr)

    def _speed(self, count, seconds):
        cup_r = 80 # 80mm radius of wind cups
        full_circle = (2 * 3.14 * cup_r)
        rps = count / seconds
        # meters per second
        mps = ((rps * full_circle) / 1000) 
        return mps

    def windspeed(self, seconds):
        total_count = mem32[self.wind_counter] & ULP_DATA_MASK
        gust_count = mem32[self.wind_gust] & ULP_DATA_MASK
        # clear the counters
        mem32[self.wind_counter] = 0
        mem32[self.wind_gust] = 0

        avg_mps = self._speed(total_count, seconds)
        gust_mps = self._speed(gust_count, 1)

        return avg_mps, gust_mps

    def rainbuckets(self):
        value = int(mem32[self.rain_counter] & ULP_DATA_MASK)
        return value
