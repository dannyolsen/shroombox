from smbus2 import SMBus
import struct
import time

# SCD30 Default I2C Address
SCD30_I2C_ADDR = 0x61
FORCED_CALIBRATION_CMD = 0x5204  # SCD30 FRC Command


import scd30_i2c

scd30 = scd30_i2c.SCD30()



def send_forced_calibration(reference_co2):
    # Convert CO2 value to the required big-endian byte format
    co2_bytes = struct.pack(">H", reference_co2)  # Convert to 2-byte big-endian

    # Open I2C communication
    with SMBus(1) as bus:
        # Send command with calibration value
        bus.write_i2c_block_data(SCD30_I2C_ADDR, FORCED_CALIBRATION_CMD >> 8, list(co2_bytes))
        print(f"Forced calibration set to {reference_co2} ppm.")

    # Wait a few seconds for calibration to apply
    time.sleep(2)

# Disable Automatic Baseline Calibration (ABC)
scd30.set_auto_self_calibration(False)
print("ABC Mode Disabled. Now setting Forced Calibration...")

# Example: Set FRC to 400 ppm (typical outdoor air level)
send_forced_calibration(400)