# Todo List
SHROOMBOX PROJECT TODO LIST
=======================

CURRENT TASKS:
-------------
[ ] Investigate and fix SCD30 sensor connection issues
    - Check physical connections
    - Verify power supply
    - Consider sensor replacement if damaged by high humidity

[ ] Improve humidity control system
    - Fine-tune PID parameters
    - Add safeguards to prevent 100% humidity conditions

[ ] Enhance CO2 control system
    - Implement better ventilation when CO2 levels exceed sensor range
    - Add alerts for extreme CO2 levels

[ ] Optimize fan control
    - Test manual fan control under different conditions
    - Improve automatic fan speed adjustment algorithm

[ ] Add data visualization for historical measurements
    - Create graphs for temperature, humidity, and CO2 trends
    - Implement date range selection for viewing historical data

[ ] Implement system health monitoring
    - Add sensor status indicators
    - Create alerts for system issues
    - Implement automatic recovery procedures

[ ] Improve web interface
    - Add mobile-friendly responsive design
    - Implement dark mode
    - Add user authentication for remote access

COMPLETED TASKS:
--------------
[✓] Implement manual fan control on the dashboard
[✓] Add sensor status warning to the dashboard
[✓] Limit CO2 setpoints to valid range (400-10,000 ppm)
[✓] Fix fan speed control API endpoint
[✓] Implement fallback to measurements.json when sensor is unavailable
[✓] Fix sensor status detection on the dashboard
[✓] Consolidate sensor implementations
    - Moved deprecated sensor.py to deprecated/ folder
    - Updated imports to use only SimpleSCD30Controller
    - Verified system functionality after changes

BACKLOG:
-------
[ ] Create documentation for the system
[ ] Implement automatic updates
[ ] Add support for additional sensors
[ ] Create backup and restore functionality
[ ] Implement power management features
[ ] Add time-based control profiles (day/night cycles)

NOTES:
-----
- SCD30 sensor operating range: 400-10,000 ppm CO2, 0-95% humidity
- High humidity (100%) may damage electronic components
- Consider adding a dehumidifier if humidity consistently reaches 95%+
- The system now uses only the SimpleSCD30Controller implementation
  with the deprecated version moved to the deprecated/ folder 