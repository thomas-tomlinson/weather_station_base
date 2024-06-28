# reference for the memory locations : https://github.com/espressif/esp-idf/blob/v5.0.2/components/soc/esp32/rtc_io_periph.c#L53
# remember RTC_GPIO numbers are different than the actual GPIO

#define DR_REG_RTCIO_BASE            0x3ff48400
# this is the addressing for GPIO32 / RTCIO9
#define RTC_IO_XTAL_32K_PAD_REG      (DR_REG_RTCIO_BASE + 0x8c)
#define RTC_IO_X32P_MUX_SEL_M        (BIT(17))
#define RTC_IO_X32P_FUN_IE_M         (BIT(5))
# this is the addressing for GPIO35 / RTCIO5
#define RTC_IO_ADC_PAD_REG           (DR_REG_RTCIO_BASE + 0x80)
#define RTC_IO_ADC2_MUX_SEL_M        (BIT(28))
#define RTC_IO_ADC2_FUN_IE_M         (BIT(18))

#define RTC_GPIO_IN_REG              (DR_REG_RTCIO_BASE + 0x24)
#define RTC_GPIO_IN_NEXT_S           14
.set windpin, 9 # RTC9, GPIO32
.set rainpin, 5 # RTC5, GPIO35

#wind global vars
  .global wind_pulse_edge
wind_pulse_edge:
  .long 0

  .global wind_next_edge
wind_next_edge:
  .long 0

  .global wind_debounce_counter
wind_debounce_counter:
  .long 0

  .global wind_debounce_max_count
wind_debounce_max_count:
  .long 0

  .global wind_pulse_res
wind_pulse_res:
  .long 0

  .global wind_pulse_cur
wind_pulse_cur:
  .long 0

  .global wind_pulse_min
wind_pulse_min:
  .long 0

  .global wind_edge_count
wind_edge_count:
  .long 0

#rain global vars
  .global rain_pulse_edge
rain_pulse_edge:
  .long 0

  .global rain_next_edge
rain_next_edge:
  .long 0

  .global rain_debounce_counter
rain_debounce_counter:
  .long 0

  .global rain_debounce_max_count
rain_debounce_max_count:
  .long 0

  .global rain_pulse_res
rain_pulse_res:
  .long 0

  .global rain_pulse_cur
rain_pulse_cur:
  .long 0

  .global rain_pulse_min
rain_pulse_min:
  .long 0

  .global rain_edge_count
rain_edge_count:
  .long 0

  .text
  .global wind_entry
wind_entry:
  # connect GPIO to RTC
  WRITE_RTC_REG(RTC_IO_XTAL_32K_PAD_REG, RTC_IO_X32P_MUX_SEL_M, 1, 1)
  # switch the GPIO into input mode
  WRITE_RTC_REG(RTC_IO_XTAL_32K_PAD_REG, RTC_IO_X32P_FUN_IE_M, 1, 1)

  jump wind_pulse_tick

wind_read_now:
  READ_RTC_REG(RTC_GPIO_IN_REG, RTC_GPIO_IN_NEXT_S + windpin, 1)
  and r0, r0, 1
  move r3, wind_next_edge
  ld r3, r3, 0
  add r3, r0, r3
  and r3, r3, 1
  jump wind_changed, eq
  move r3, wind_debounce_max_count
  move r2, wind_debounce_counter
  ld r3, r3, 0
  st r3, r2, 0
  #halt
  jump rain_entry

wind_changed:
  move r3, wind_debounce_counter
  ld r2, r3, 0
  add r2, r2, 0 
  jump wind_edge_detected, eq
  sub r2, r2, 1
  st r2, r3, 0
  #halt
  jump rain_entry

wind_edge_detected:
  move r3, wind_debounce_max_count
  move r2, wind_debounce_counter
  ld r3, r3, 0
  st r3, r2, 0
  move r3, wind_next_edge
  ld r2, r3, 0
  add r2, r2, 1
  and r2, r2, 1
  st r2, r3, 0
  move r3, wind_edge_count
  ld r2, r3, 0
  add r2, r2, 1
  st r2, r3, 0
  move r3, wind_pulse_edge
  ld r3, r3, 0
  add r3, r0, r3
  and r3, r3, 1
  jump wind_pulse_detected, eq
  #halt
  jump rain_entry

wind_pulse_tick:
  move r3, wind_pulse_cur
  ld r2, r3, 0
  add r2, r2, 1
  st r2, r3, 0
  jump wind_read_now

wind_pulse_detected:
  move r3, wind_pulse_min
  move r2, wind_pulse_cur
  ld r3, r3, 0
  ld r2, r2, 0
  sub r3, r2, r3
  jump wind_pulse_lower, ov
  move r3, wind_pulse_min
  ld r2, r3, 0
  add r2, r2, 0
  jump wind_pulse_lower, eq
  jump wind_pulse_reset

wind_pulse_lower:
  move r3, wind_pulse_cur
  move r2, wind_pulse_min
  ld r3, r3, 0
  st r3, r2, 0
  jump wind_pulse_reset

wind_pulse_reset:
  move r3, wind_pulse_res
  move r2, wind_pulse_cur
  ld r3, r3, 0
  st r3, r2, 0
  #halt

  .global rain_entry
rain_entry:
  # connect GPIO to RTC
  WRITE_RTC_REG(RTC_IO_ADC_PAD_REG, RTC_IO_ADC2_MUX_SEL_M, 1, 1)
  # switch the GPIO into input mode
  WRITE_RTC_REG(RTC_IO_ADC_PAD_REG, RTC_IO_ADC2_FUN_IE_M, 1, 1)
  jump rain_pulse_tick

rain_read_now:
  READ_RTC_REG(RTC_GPIO_IN_REG, RTC_GPIO_IN_NEXT_S + rainpin, 1)
  and r0, r0, 1
  move r3, rain_next_edge
  ld r3, r3, 0
  add r3, r0, r3
  and r3, r3, 1
  jump rain_changed, eq
  move r3, rain_debounce_max_count
  move r2, rain_debounce_counter
  ld r3, r3, 0
  st r3, r2, 0
  halt

rain_changed:
  move r3, rain_debounce_counter
  ld r2, r3, 0
  add r2, r2, 0 
  jump rain_edge_detected, eq
  sub r2, r2, 1
  st r2, r3, 0
  halt

rain_edge_detected:
  move r3, rain_debounce_max_count
  move r2, rain_debounce_counter
  ld r3, r3, 0
  st r3, r2, 0
  move r3, rain_next_edge
  ld r2, r3, 0
  add r2, r2, 1
  and r2, r2, 1
  st r2, r3, 0
  move r3, rain_edge_count
  ld r2, r3, 0
  add r2, r2, 1
  st r2, r3, 0
  move r3, rain_pulse_edge
  ld r3, r3, 0
  add r3, r0, r3
  and r3, r3, 1
  jump rain_pulse_detected, eq
  halt

rain_pulse_tick:
  move r3, rain_pulse_cur
  ld r2, r3, 0
  add r2, r2, 1
  st r2, r3, 0
  jump rain_read_now

rain_pulse_detected:
  move r3, rain_pulse_min
  move r2, rain_pulse_cur
  ld r3, r3, 0
  ld r2, r2, 0
  sub r3, r2, r3
  jump rain_pulse_lower, ov
  move r3, rain_pulse_min
  ld r2, r3, 0
  add r2, r2, 0
  jump rain_pulse_lower, eq
  jump rain_pulse_reset

rain_pulse_lower:
  move r3, rain_pulse_cur
  move r2, rain_pulse_min
  ld r3, r3, 0
  st r3, r2, 0
  jump rain_pulse_reset

rain_pulse_reset:
  move r3, rain_pulse_res
  move r2, rain_pulse_cur
  ld r3, r3, 0
  st r3, r2, 0
  halt
