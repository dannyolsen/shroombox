"""
Devices package for Shroombox hardware interfaces.
"""

import warnings

from devices.base import Device
from devices.fan import NoctuaFan
from devices.smart_plug import TapoController

# Import sensor classes after other dependencies
from devices.sensor import SCD30Controller  # Deprecated
from devices.simple_sensor import SimpleSCD30Controller

# Emit deprecation warning for SCD30Controller
warnings.warn(
    "SCD30Controller from devices.sensor is deprecated and will be removed in a future version. "
    "Please use SimpleSCD30Controller from devices.simple_sensor instead.",
    DeprecationWarning,
    stacklevel=2
)

__all__ = [
    'Device',
    'NoctuaFan',
    'TapoController',
    'SCD30Controller',  # Deprecated
    'SimpleSCD30Controller'  # Preferred implementation
] 