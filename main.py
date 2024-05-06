import bme280_float as bme280
import json
import time
import binascii
from machine import I2C, Pin, UART, deepsleep, RTC

# set bme280
i2c = I2C(0, scl=Pin(22), sda=Pin(21))
bme = bme280.BME280(i2c=i2c)

# setup hc-12 radio
uart2 = UART(2, baudrate=9600, tx=17, rx=16)

# create the RTC object
rtc = RTC()

def readbme():
    dict = {}
    rawread = bme.values
    dict['temp'] = rawread[0]
    dict['pressure'] = rawread[1]
    dict['humidiy'] = rawread[2]
    return dict

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

def gather_loop():
    while True:
        payload = {}
        # BME280 data gather
        payload['bme280'] = readbme()
        # windspeed
        # winddirection
        # rain

        # timestamp
        # we're using seconds since boot as a way to tell the data packets apart.
        payload['timemark'] = time.time()
        payloadjson = json.dumps(payload)
        broadcast_data(payloadjson)

        # sleep for 30 seconds
        #deepsleep(10000)
        time.sleep(5)

def main():
    gather_loop()

main()