import bme280_float as bme280
import json
import time
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
    # console dump for anyone looking
    print(payload)
    uart2.write(payload)
    
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
    deepsleep(30000)    
