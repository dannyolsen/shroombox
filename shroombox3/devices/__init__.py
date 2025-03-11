"""
Devices package for Shroombox hardware interfaces.
"""

import warnings

from devices.base import Device
from devices.fan import NoctuaFan
from devices.smart_plug import TapoController

# Import sensor classes after other dependencies
from devices.simple_sensor import SimpleSCD30Controller

# Note about deprecated sensor implementation
# The deprecated SCD30Controller has been moved to the deprecated/ folder
# and is no longer part of the active codebase.

__all__ = [
    'Device',
    'NoctuaFan',
    'TapoController',
    'SimpleSCD30Controller'  # Preferred implementation
] 