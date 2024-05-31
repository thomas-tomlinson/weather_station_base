#
# This file is part of the micropython-esp32-ulp project,
# https://github.com/micropython/micropython-esp32-ulp
#
# SPDX-FileCopyrightText: 2018-2023, the micropython-esp32-ulp authors, see AUTHORS file.
# SPDX-License-Identifier: MIT

"""
Example for: ESP32

Very basic example showing how to read a GPIO pin from the ULP and access
that data from the main CPU.

In this case GPIO4 is being read. Note that the ULP needs to refer to GPIOs
via their RTC channel number. You can see the mapping in this file:
https://github.com/espressif/esp-idf/blob/v5.0.2/components/soc/esp32/include/soc/rtc_io_channel.h#L51

If you change to a different GPIO number, make sure to modify both the channel
number and also the RTC_IO_TOUCH_PAD0_* references appropriately. The best place
to see the mappings might be this table here (notice the "real GPIO numbers" as
comments to each line):
https://github.com/espressif/esp-idf/blob/v5.0.2/components/soc/esp32/rtc_io_periph.c#L53

The timer is set to a rather long period, so you can watch the data value
change as you change the GPIO input (see loop at the end).
"""

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
.set channel, 10  # 10 is the channel no. of gpio4
.set max_histogram_slots, 10
.set max_histogram_bytes, max_histogram_slots * 4
.set loops_per_sec, 200

        .global p1_status
p1_status:
        .long 0

        .global p1_status_next
p1_status_next:
        .long 0

        .global event_counter
event_counter:
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

bump_event_counter:
        move r3, event_counter
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

        jump check_loop_counter

p1_status_changed:
        move r3, p1_status_next
        ld r2, r3, 0
        add r2, r2, 1
        and r2, r2, 1
        st r2, r3, 0

        jump bump_event_counter, eq
        
        jump check_loop_counter

check_loop_counter:
        # this checks if we need to reset the loop
        # and advance the wind_offset
        move r3, loop_counter
        ld r2, r3, 0 
        sub r2, r2, loops_per_sec
        jump incr_wind_offset, eq

        halt

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
        # connect GPIO to the RTC subsystem so the ULP can read it
        WRITE_RTC_REG(RTC_IO_TOUCH_PAD0_REG, RTC_IO_TOUCH_PAD0_MUX_SEL_M, 1, 1)
        # switch the GPIO into input mode
        WRITE_RTC_REG(RTC_IO_TOUCH_PAD0_REG, RTC_IO_TOUCH_PAD0_FUN_IE_M, 1, 1)
        # read the GPIO's current state into r0
        READ_RTC_REG(RTC_GPIO_IN_REG, RTC_GPIO_IN_NEXT_S + channel, 1)

        # increment loop_counter        
        move r3, loop_counter
        ld r2, r3, 0
        add r2, r2, 1
        st r2, r3, 0

        # set r3 to the memory address of p1_status
        move r3, p1_status
        st r0, r3, 0

        # see if p1 status is changed
        and r0, r0, 1
        move r3, p1_status_next
        ld r3, r3, 0
        add r3, r0, r3
        and r3, r3, 1
        jump p1_status_changed, eq        

        jump check_loop_counter
        # halt ULP co-processor (until it gets woken up again)
        halt
"""

binary = src_to_binary(source, cpu="esp32")  # cpu is esp32 or esp32s2

load_addr, entry_addr = 0, (53*4)

ULP_MEM_BASE = 0x50000000
ULP_DATA_MASK = 0xffff  # ULP data is only in lower 16 bits

ulp = ULP()
ulp.set_wakeup_period(0, 5000)  # use timer0, wakeup after 50.000 cycles
ulp.load_binary(load_addr, binary)

mem32[ULP_MEM_BASE + load_addr] = 0x0  # initialise state to 0
ulp.run(entry_addr)

def windspeed():
    cup_r = 80 # 80mm radius of wind cups
    full_circle = (2 * 3.14 * cup_r)
    count = mem32[ULP_MEM_BASE + (2*4)] & ULP_DATA_MASK
    rps = 0
    histo = []
    if count > 0:
        rps = (count / 10)
    #clear the counter
    mem32[ULP_MEM_BASE + (2*4)] = 0
    # meters per second
    mps = ((rps * full_circle) / 1000) 
    # find the gust
    histogram_start = 4 * 4
    for i in range(0,10):
        value = int(mem32[ULP_MEM_BASE + histogram_start] & ULP_DATA_MASK)
        histo.append(value)
        print('mem address: {}, value: {}'.format(histogram_start, value))
        mem32[ULP_MEM_BASE + histogram_start] = 0
        histogram_start += 4
    histo.sort()
    
    return mps, histo[-1]

while True:
    time.sleep(10)

    avg, gust = windspeed()
    print("avg meters per second: {} gust: {}".format(avg, gust))
    #histogram_start = 4 * 4
    #for i in range(0,10):
    #    value = int(mem32[ULP_MEM_BASE + histogram_start] & ULP_DATA_MASK)
    #    mem32[ULP_MEM_BASE + histogram_start] = 0
    #    print('mem address: {}, value: {}'.format(histogram_start, value))
    #    histogram_start += 4
        #print(int(mem32[ULP_MEM_BASE + histogram_start] & ULP_DATA_MASK))
        #mem32[ULP_MEM_BASE + (histogram_start * 4)] = 0

    #print(hex(mem32[ULP_MEM_BASE] & ULP_DATA_MASK))
    #count = mem32[ULP_MEM_BASE + (2*4)] & ULP_DATA_MASK
    #print(count)
    #if count > 15:
    #    mem32[ULP_MEM_BASE + (2*4)] = 0
    