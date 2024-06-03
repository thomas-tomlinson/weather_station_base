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

        .global rain_counter
rain_counter:
        .long 0

loop_counter:
        .long 0

        .global wind_histogram
wind_histogram:
        .long 0
        .long 0
        .long 0
        .long 0
        .long 0
        .long 0
        .long 0
        .long 0
        .long 0
        .long 0
        .long 0

wind_offset:
        .long 0


        .text

incr_wind_counter:
        move r3, wind_counter
        ld r2, r3, 0
        add r2, r2, 1
        st r2, r3, 0
        # add to wind histogram
        move r3, wind_offset
        ld r1, r3, 0
        move r3, wind_histogram
        add r3, r3, r1
        ld r2, r3, 0
        add r2, r2, 1
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

incr_wind_offset:
        # reset our loop counter to 0
        move r3, loop_counter
        move r2, 0
        st r2, r3, 0
        # increment our wind_offset 
        move r3, wind_offset
        ld r2, r3, 0
        add r2, r2, 1
        st r2, r3, 0

        #check to see if we need to reset to 0
        add r2, r2, 1
        sub r2, r2, max_histogram_slots
        jump reset_wind_offset, eq

        halt

reset_wind_offset:
        # r2 should be 0 and r3 wind_offset.
        st r2, r3, 0 
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
        move r3, loop_counter
        ld r2, r3, 0
        add r2, r2, 1
        st r2, r3, 0

        # this should be moved below here with a label
        #jump check_loop_counter

check_loop_counter:
        # this checks if we need to reset the loop
        # and advance the wind_offset
        move r3, loop_counter
        ld r2, r3, 0 
        sub r2, r2, loops_per_sec
        jump incr_wind_offset, eq

        # halt ULP co-processor (until it gets woken up again)
        halt
"""
ULP_MEM_BASE = 0x50000000
ULP_DATA_MASK = 0xffff  # ULP data is only in lower 16 bits

class ULP_WEATHER:
    def __init__(self):
        self.binary = src_to_binary(source, cpu="esp32")  # cpu is esp32 or esp32s2
        self.load_addr = 0
        # these values are calculated upon a compile of the ULP code.  Currently
        # this is found through watching the console during the compile and noting the 
        # memory offsets.
        self.entry_addr = ULP_MEM_BASE + (63*4)
        self.wind_counter = ULP_MEM_BASE + (4*4)
        self.wind_histogram = ULP_MEM_BASE + (7*4)
        self.rain_counter = ULP_MEM_BASE +(4*5)

        ulp = ULP()
        ulp.set_wakeup_period(0, 5000)  # use timer0, wakeup after 50.000 cycles
        ulp.load_binary(self.load_addr, self.binary)

        mem32[ULP_MEM_BASE + self.load_addr] = 0x0  # initialise state to 0
        ulp.run(self.entry_addr)

    def windspeed(self):
        cup_r = 80 # 80mm radius of wind cups
        full_circle = (2 * 3.14 * cup_r)
        count = mem32[self.wind_counter] & ULP_DATA_MASK
        # clear the counter
        mem32[self.wind_counter] = 0
        rps = 0
        histo = []
        if count > 0:
            rps = (count / 10)
        # meters per second
        mps = ((rps * full_circle) / 1000) 
        # find the gust
        histogram_start = self.wind_histogram
        for i in range(0,10):
            value = int(mem32[histogram_start] & ULP_DATA_MASK)
            histo.append(value)
            print('mem address: {}, value: {}'.format(histogram_start, value))
            mem32[histogram_start] = 0
            histogram_start += 4
        histo.sort()
        
        return mps, histo[-1]

    def rainbuckets(self):
        value = int(mem32[self.rain_counter] & ULP_DATA_MASK)
        return value
