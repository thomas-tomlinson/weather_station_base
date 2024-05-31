import bme280_float as bme280
import json
import time
import binascii
from machine import I2C, Pin, UART, lightsleep, RTC, ADC
from micropython import const

AS5600_ADDRESS = const(0x36)
# set bme280
i2c = I2C(0, scl=Pin(22), sda=Pin(21))
bme = bme280.BME280(i2c=i2c)

# setup hc-12 radio
uart2 = UART(2, baudrate=9600, tx=17, rx=16)

# create the RTC object
rtc = RTC()

def read_bme():
    dict = {}
    rawread = bme.values
    dict['temp'] = rawread[0]
    dict['pressure'] = rawread[1]
    dict['humidity'] = rawread[2]
    return dict

def read_battery():
    # this reads the voltage of the battery pack where it's divided.  the value returned is half
    # the actual voltage in micro volts.  
    batpin = ADC(Pin(34), atten=ADC.ATTN_11DB)
    try:
        value = str(float((batpin.read_uv() / 1000000) * 2)) + "V"
    except:
        value = '0.0V'
    return value

def broadcast_data(payload):
    transmitPayload = binascii.b2a_base64(payload.encode())
    # console dump for anyone looking
    print(transmitPayload)
    # wake up HC-12
    set_pin = Pin(23, Pin.OUT)
    set_pin.off()
    time.sleep_ms(200)
    uart2.write('AT')
    trash = uart2.read()
    uart2.flush()
    set_pin.on()
    time.sleep_ms(200)

    uart2.write(transmitPayload)
    uart2.flush()
    time.sleep_ms(200)

    set_pin.off()
    time.sleep_ms(200)
    uart2.write('AT+SLEEP')
    uart2.flush()
    set_pin.on()
    time.sleep_ms(200)
    # HC-12 now in sleep mode

def init_hc12():
    # console dump for anyone looking
    # wake up HC-12
    set_pin = Pin(23, Pin.OUT)
    set_pin.off()
    time.sleep_ms(200)
    uart2.write('AT+P5')
    trash = uart2.read()
    uart2.flush()
    set_pin.on()
    time.sleep_ms(200)

def init_as5600():
    # unless your burn the config into this, it starts up full power mode
    conf = b'\x00\x03'
    i2c.writeto_mem(AS5600_ADDRESS, 0x07, conf)

def read_as5600_angle():
    buf = i2c.readfrom_mem(AS5600_ADDRESS, 0x0E, 2)
    ang = (buf[0]<<8 | buf[1]) / 4096.0*360
    return ang     

def gather_loop():
    while True:
        payload = {}
        # BME280 data gather
        payload['bme280'] = read_bme()
        payload['battery'] = read_battery()
        # windspeed
        # winddirection
        # rain

        # timestamp
        # we're using seconds since boot as a way to tell the data packets apart.
        payload['timemark'] = time.time()
        payloadjson = json.dumps(payload)
        broadcast_data(payloadjson)

        # sleep for 30 seconds
        #deepsleep(20000)
        lightsleep(20000)
        #time.sleep(5)

def main():
    init_hc12()
    gather_loop()

main()