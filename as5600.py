from micropython import const

AS5600_ADDRESS = const(0x36)   # AS5600 has a fixed address (so can only use one per I2C bus?)
ANGLE_H	= const(0x0E)          # Angle register (high byte)
ANGLE_L	= const(0x0F)          # Angle register (low byte)
zero_correction = const(0)   # what the as5600 reads at North on the windvane.

class AS5600:
    def __init__(self, i2c=None):

        if i2c is None:
            raise ValueError('An I2C object is required.')
        self.i2c = i2c
        # set power mode to lowest
        conf = b'\x00\x03'
        self.i2c.writeto_mem(AS5600_ADDRESS, 0x07, conf)

    def getnReg(self, reg, n):
        self.i2c.writeto(AS5600_ADDRESS, bytearray([reg]))
        t =	self.i2c.readfrom(AS5600_ADDRESS, n)
        return t

    # main function to get angle information
    def getAngle(self):
        buf = self.getnReg(ANGLE_H, 2)
        #return ((buf[0]<<8) | buf[1])/ 4096.0*360
        angle = int(((buf[0]<<8) | buf[1])/ 4096.0*360)

        if angle >= zero_correction:
            angle = angle - zero_correction
        else:
            angle = angle - zero_correction
            angle = angle + 360
        return angle
