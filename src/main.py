import sht4x
import time
import umsgpack
import rolling_average
from struct import pack
from machine import I2C, Pin, UART, lightsleep, RTC, ADC
from ulp_weather import ULP_WEATHER
from as5600 import AS5600

# I2C specific configs
i2c = I2C(0, scl=Pin(22), sda=Pin(21))
sht = sht4x.SHT4X(i2c=i2c)
as5600 = AS5600(i2c=i2c) 

# init the ULP data gather process
ulp = ULP_WEATHER()

# setup hc-12 radio
uart2 = UART(2, baudrate=9600, tx=17, rx=16)

# create the RTC object
rtc = RTC()

# voltage rolling average 
bat_volt_avg = rolling_average.ROLLINGAVERAGE(samples=5)

def read_sht41():
    dict = {}
    temp, humidity = sht.measurements
    dict['temp'] = temp
    dict['humidity'] = humidity
    return dict

def read_battery():
    # this reads the voltage of the battery pack where it's divided.  the value returned is half
    # the actual voltage in micro volts.  
    batpin = ADC(Pin(34), atten=ADC.ATTN_11DB)
    try:
        value = float((batpin.read_uv() / 1000000) * 2)
    except:
        return 0.0
    if value > 0 and value < 5:
        return value
    else:
        return 0.0

def pack_data(payload):
    packed = pack(">LfHHfffffs", 
                  payload['timemark'], # L
                  payload['battery'], # f
                  payload['rainbuckets'], # H
                  payload['wind']['wind_dir'], # H
                  payload['wind']['avg_wind'], # f
                  payload['wind']['gust_wind'], # f
                  payload['bme280']['temp'], # f
                  payload['bme280']['humidity'], # f
                  payload['bme280']['pressure'], # f
                  b'\n', #terminate character
                  ) 
    return packed

def broadcast_data(payload):
    #transmitPayload = binascii.b2a_base64(payload.encode())
    # console dump for anyone looking
    chksumed = checksum_payload(payload)
    print("checksumed payload: {}".format(chksumed))
    # wake up HC-12
    set_pin = Pin(23, Pin.OUT)
    set_pin.off()
    time.sleep_ms(200)
    uart2.write('AT')
    trash = uart2.read()
    uart2.flush()
    set_pin.on()
    time.sleep_ms(200)

    uart2.write(chksumed)
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
    # wake up HC-12
    set_pin = Pin(23, Pin.OUT)
    set_pin.off()
    time.sleep_ms(200)
    uart2.write('AT+P6')
    trash = uart2.read()
    uart2.flush()
    set_pin.on()
    time.sleep_ms(200)

def checksum_payload(bytes):
    data = umsgpack.dumps(bytes)
    checksum = sum(data)
    checksum1 = int(checksum // 256)
    checksum2 = int(checksum % 256)
    checksum = pack(">hh", checksum1, checksum2)
    checksum_payload = data + checksum
    return umsgpack.dumps(checksum_payload)

def compute_sleep_seconds(avg):
    default_seconds = 20
    max_delay = 200
    cutoff_voltage = 3.7
    min_voltage = 3.0
    delay_factor = (max_delay / (cutoff_voltage - min_voltage)) 
    if avg is None:
        sleep_seconds = default_seconds
    elif avg >= cutoff_voltage:
        sleep_seconds = default_seconds
    elif avg >= min_voltage:
        sleep_seconds = ((cutoff_voltage - avg) * delay_factor) + default_seconds
    else:
        sleep_seconds = max_delay + default_seconds

    return int(sleep_seconds)

def gather_loop():
    sleep_seconds = 20
    start_ms = time.ticks_ms()
    while True:
        lightsleep(int(sleep_seconds * 1000))
        span_secs = int((time.ticks_ms() - start_ms) / 1000)
        payload = {}
        sht41_data = read_sht41()
        payload['temp'] = sht41_data['temp']
        payload['humidity'] = sht41_data['humidity']
        payload['battery'] = read_battery()
        ulp_data = ulp.retrieve_metrics(span_secs)
        payload['avg_wind'] = ulp_data['wind_avg_pulse_second']
        payload['gust_wind'] = ulp_data['wind_burst_pulse_second']
        payload['wind_dir'] = int(as5600.getAngle())
        payload['rainbuckets'] = int(ulp_data['rain_total_pulse_count'])
        payload['rainbuckets_total'] = int(ulp_data['rain_total_pulse_counter'])
        bat_volt_avg.submit(payload['battery'])
        # we're using seconds since boot as a way to tell the data packets apart.
        payload['timemark'] = time.time()
        print("payload: {} ulp data: {}".format(payload, ulp_data))
        msgpacked = umsgpack.dumps(payload)
        broadcast_data(msgpacked)
        sleep_seconds = compute_sleep_seconds(bat_volt_avg.compute_avg())
        print("sleeping for {} seconds".format(sleep_seconds))
        start_ms = time.ticks_ms()

def main():
    print("waiting for 15 seconds before entering main loop.  break if you want to get REPL")
    time.sleep(15)
    init_hc12()
    gather_loop()

main()