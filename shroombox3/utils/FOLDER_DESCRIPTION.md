# Utils Directory

This directory contains utility functions and helper classes that are used throughout the Shroombox project. These utilities provide common functionality that is not specific to any particular component of the system.

## Files

- `__init__.py`: Exports the utility functions and classes
- `logging_setup.py`: Contains functions for setting up and configuring logging
- `singleton.py`: Contains a Singleton metaclass implementation for creating singleton classes

## Utility Functions and Classes

### Logging Setup
The `logging_setup.py` file provides functions for configuring the logging system:
- `setup_logging()`: Configures the logging system with appropriate handlers and formatters
- Functions for setting up file and console logging
- Configuration for different log levels

### Singleton Pattern
The `singleton.py` file provides a `Singleton` metaclass that ensures only one instance of a class exists:
- Used for classes that should have only one instance (e.g., managers)
- Implements the singleton design pattern
- Provides thread-safe singleton instantiation

## Usage Examples

```python
# Example: Setting up logging
from utils.logging_setup import setup_logging

logger = setup_logging('my_module', log_level='INFO')
logger.info('This is an info message')
logger.error('This is an error message')

# Example: Creating a singleton class
from utils.singleton import Singleton

class MySingleton(metaclass=Singleton):
    def __init__(self):
        self.value = 0
    
    def increment(self):
        self.value += 1
        return self.value

# These will be the same instance
instance1 = MySingleton()
instance2 = MySingleton()
assert instance1 is instance2
```

## Adding New Utilities

When adding new utility functions or classes:
1. Consider whether the functionality belongs in an existing file or requires a new file
2. For new files, follow the naming convention of descriptive lowercase names with underscores
3. Add exports to `__init__.py` for easy importing
4. Ensure utilities are well-documented with docstrings
5. Keep utilities focused on a single responsibility 