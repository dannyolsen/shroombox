import scd30_i2c
import time

def read_measurement(sensor):
    """Read CO2, temperature and humidity from SCD30"""
    if sensor.get_data_ready():
        m = sensor.read_measurement()
        if m is not None:
            return m
    return None

# Initialize sensor
scd30 = scd30_i2c.SCD30()

# Print available methods
print("Available SCD30 methods:")
methods = [method for method in dir(scd30) if not method.startswith('_')]
for method in sorted(methods):
    print(f"  - {method}")
print("\n" + "="*50 + "\n")

print("Starting SCD30 calibration process...")

# Take initial measurement
print("\nTaking initial measurement...")
time.sleep(2)  # Wait for first measurement
measurement = read_measurement(scd30)
if measurement:
    co2, temp, hum = measurement
    print(f"Initial readings:")
    print(f"CO2: {co2:.1f} ppm")
    print(f"Temperature: {temp:.1f} °C")
    print(f"Humidity: {hum:.1f} %")
else:
    print("Failed to get initial measurement")

# Set the Forced Recalibration Reference Value (e.g., 400 ppm for fresh air)
frc_value = 400  # Adjust based on your reference CO₂ level
try:
    success = scd30.set_forced_recalibration_with_reference(frc_value)
    print(f"\nSCD30 Forced Calibration set to {frc_value} ppm successfully.")
except Exception as e:
    print(f"Failed to set forced calibration: {e}")

# Wait for sensor to stabilize after calibration
print("\nWaiting for sensor to stabilize (30 seconds)...")
time.sleep(30)

# Take final measurement
print("\nTaking final measurement...")
measurement = read_measurement(scd30)
if measurement:
    co2, temp, hum = measurement
    print(f"Final readings:")
    print(f"CO2: {co2:.1f} ppm")
    print(f"Temperature: {temp:.1f} °C")
    print(f"Humidity: {hum:.1f} %")
else:
    print("Failed to get final measurement")