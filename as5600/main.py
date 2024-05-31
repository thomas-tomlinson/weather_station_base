from machine import I2C, Pin
from time import sleep
from micropython import const

AS5600_ADDRESS = const(0x36)   # AS5600 has a fixed address (so can only use one per I2C bus?)
ANGLE_H	= const(0x0E)          # Angle register (high byte)
ANGLE_L	= const(0x0F)          # Angle register (low byte)

def getnReg(reg, n):
    i2c.writeto(AS5600_ADDRESS, bytearray([reg]))
    t =	i2c.readfrom(AS5600_ADDRESS, n)
    return t

def getAngle():
    buf = getnReg(ANGLE_H, 2)
    return ((buf[0]<<8) | buf[1])/ 4096.0*360



# I2C bus init for ATOM Matrix MPU6886
i2c = I2C(0, scl=Pin(22), sda=Pin(21))

while True:
    print(getAngle())
    sleep(1)
