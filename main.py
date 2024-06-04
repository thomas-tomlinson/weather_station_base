import bme280_float as bme280
import json
import time
import binascii
from struct import pack
from machine import I2C, Pin, UART, lightsleep, RTC, ADC
from micropython import const
from ulp_weather import ULP_WEATHER
from as5600 import AS5600

# I2C specific configs
i2c = I2C(0, scl=Pin(22), sda=Pin(21))
bme = bme280.BME280(i2c=i2c)
as5600 = AS5600(i2c=i2c) 

# init the ULP data gather process
ulp = ULP_WEATHER()

# setup hc-12 radio
uart2 = UART(2, baudrate=9600, tx=17, rx=16)

# create the RTC object
rtc = RTC()

def read_bme():
    dict = {}
    rawread = bme.values
    # bme.read_compensated_data a better return?
    dict['temp'] = rawread[0]
    dict['pressure'] = rawread[1]
    dict['humidity'] = rawread[2]
    return dict

def read_battery():
    # this reads the voltage of the battery pack where it's divided.  the value returned is half
    # the actual voltage in micro volts.  
    batpin = ADC(Pin(34), atten=ADC.ATTN_11DB)
    try:
        value = str(float((batpin.read_uv() / 1000000) * 2)) 
    except:
        value = '0.0'
    return value

def pack_data(payload):
    packed = pack(">LfHHffff", 
                  payload['timemark'], # L
                  payload['battery'], # f
                  payload['rainbuckets'], # H
                  payload['wind']['wind_dir'], # H
                  payload['wind']['avg_wind'], # f
                  payload['wind']['gust_wind'], # f
                  payload['bme280']['temp'], # f
                  payload['bme280']['humidity'], # f
                  payload['bme280']['pressure'], # f
                  ) 
# example payload
# '{"wind": 
#    {"wind_dir": 114, "avg_wind": 0.0, "gust_wind": 0.0},
# "rainbuckets": 0, 
# "battery": "3.774V", 
# "timemark": 1296, 
# "bme280": 
#    {"pressure": "914.10hPa", "temp": "24.97C", "humidity": "34.01%"}}'

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

def read_wind(seconds):
    dict = {}
    avg_wind, gust_wind =  ulp.windspeed(seconds)
    wind_dir = int(as5600.getAngle())
    dict['avg_wind'] = avg_wind
    dict['gust_wind'] = gust_wind
    dict['wind_dir'] = wind_dir
    return dict

def read_rain():
    value = ulp.rainbuckets()
    return value

def gather_loop():
    sleep_seconds = 20
    while True:
        payload = {}
        # BME280 data gather
        payload['bme280'] = read_bme()
        payload['battery'] = read_battery()
        payload['wind'] = read_wind(sleep_seconds)
        payload['rainbuckets'] = read_rain()

        # we're using seconds since boot as a way to tell the data packets apart.
        payload['timemark'] = time.time()
        #payloadjson = json.dumps(payload)
        #broadcast_data(payloadjson)
        packed_data = pack_data(payload)
        broadcast_data(packed_data)

        # sleep for 30 seconds
        #deepsleep(20000)
        lightsleep(sleep_seconds * 1000)
        #time.sleep(5)

def main():
    init_hc12()
    gather_loop()

main()