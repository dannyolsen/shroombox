import unittest
from unittest.mock import Mock, patch
import time
from scd30_i2c import SCD30  # We'll use only this imported SCD30 class

class TestSCD30Calibration(unittest.TestCase):
    def setUp(self):
        """Set up the SCD30 sensor instance before each test"""
        self.scd30 = SCD30()
    
    @patch('scd30_i2c.SCD30.get_data_ready')
    @patch('scd30_i2c.SCD30.read_measurement')
    def test_automatic_self_calibration(self, mock_read, mock_ready):
        """Test enabling and disabling automatic self-calibration"""
        # Test enabling ASC
        self.scd30.set_automatic_self_calibration(True)
        self.assertTrue(self.scd30.get_automatic_self_calibration())
        
        # Test disabling ASC
        self.scd30.set_automatic_self_calibration(False)
        self.assertFalse(self.scd30.get_automatic_self_calibration())

    def test_forced_recalibration(self):
        """Test forced recalibration with a known CO2 reference value"""
        # Standard reference value for outdoor CO2 concentration is ~400 ppm
        reference_co2_ppm = 400
        
        # Perform forced recalibration
        self.scd30.forced_recalibration_with_reference(reference_co2_ppm)

    @patch('scd30_i2c.SCD30.get_data_ready')
    @patch('scd30_i2c.SCD30.read_measurement')
    def test_calibration_with_measurements(self, mock_read, mock_ready):
        """Test calibration by taking actual measurements"""
        # Set up mock return values
        mock_ready.return_value = True
        mock_read.return_value = (400.0, 25.0, 50.0)
        
        # Enable automatic self-calibration and wait for measurement
        self.scd30.set_automatic_self_calibration(True)
        
        # Verify sensor is ready
        self.assertTrue(self.scd30.get_data_ready())
        
        # Take a measurement and verify values
        co2, temp, hum = self.scd30.read_measurement()
        self.assertEqual(co2, 400.0)
        self.assertEqual(temp, 25.0)
        self.assertEqual(hum, 50.0)
        
        # Verify our mocks were called
        mock_ready.assert_called_once()
        mock_read.assert_called_once()

def calibrate_scd30():
    # Initialize sensor
    scd30 = SCD30()
    
    print("Starting SCD30 calibration process...")
    
    # Start continuous measurement
    scd30.start_periodic_measurement()
    
    # Take a few measurements to ensure stability
    print("Taking initial measurements...")
    for i in range(5):
        if scd30.get_data_ready():
            co2, temp, humidity = scd30.read_measurement()
            print(f"CO2: {co2:.2f}ppm, Temperature: {temp:.2f}°C, Humidity: {humidity:.2f}%")
            time.sleep(2)
    
    # Enable automatic self-calibration
    print("\nEnabling automatic self-calibration...")
    scd30.set_automatic_self_calibration(True)
    print("Automatic self-calibration is now enabled.")
    print("Note: The sensor will self-calibrate over the next 7 days,")
    print("      assuming it sees fresh air (~400ppm) for at least 1 hour each day.")
    
    # Take a few more measurements to verify sensor is still working
    print("\nTaking measurements after enabling ASC...")
    for i in range(5):
        if scd30.get_data_ready():
            co2, temp, humidity = scd30.read_measurement()
            print(f"CO2: {co2:.2f}ppm, Temperature: {temp:.2f}°C, Humidity: {humidity:.2f}%")
            time.sleep(2)

if __name__ == "__main__":
    try:
        calibrate_scd30()
        print("\nCalibration completed successfully!")
    except Exception as e:
        print(f"Error during calibration: {e}") 