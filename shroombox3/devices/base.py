"""
Base device interfaces for Shroombox hardware.
"""

from abc import ABC, abstractmethod
from typing import Any, Optional

class Device(ABC):
    """Base interface for all hardware devices."""
    
    @abstractmethod
    def initialize(self) -> bool:
        """
        Initialize the device hardware.
        
        Returns:
            bool: True if initialization was successful, False otherwise
        """
        pass
    
    @abstractmethod
    def cleanup(self) -> None:
        """
        Clean up resources before shutdown.
        
        This method should be called before the program exits to ensure
        proper cleanup of hardware resources.
        """
        pass
    
    @property
    @abstractmethod
    def is_initialized(self) -> bool:
        """
        Check if the device is initialized.
        
        Returns:
            bool: True if the device is initialized, False otherwise
        """
        pass
    
    @property
    @abstractmethod
    def name(self) -> str:
        """
        Get the device name.
        
        Returns:
            str: The name of the device
        """
        pass 