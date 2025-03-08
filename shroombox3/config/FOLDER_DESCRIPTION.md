# Config Directory

This directory contains configuration files for the Shroombox project. These files store settings, preferences, and other configuration data needed by the application.

## Files

- `settings.json`: Contains application settings and preferences
- `settings.json.bak`: Backup of the settings file
- `logging_config.json`: Configuration for the logging system

## File Formats

### settings.json
This file contains application settings and is managed by the `SettingsManager` class:

```json
{
  "devices": {
    "co2_sensor": {
      "type": "scd30",
      "enabled": true
    },
    "exhaust_fan": {
      "type": "fan",
      "enabled": true,
      "smart_plug": {
        "ip": "192.168.1.100",
        "alias": "Exhaust Fan"
      }
    }
  },
  "environment": {
    "co2": {
      "min": 400,
      "max": 1200,
      "target": 800
    },
    "temperature": {
      "min": 18,
      "max": 28,
      "target": 23
    },
    "humidity": {
      "min": 40,
      "max": 80,
      "target": 60
    }
  }
}
```

### logging_config.json
This file configures the logging system, specifying log levels, formats, and handlers:

```json
{
  "version": 1,
  "disable_existing_loggers": false,
  "formatters": {
    "standard": {
      "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    }
  },
  "handlers": {
    "console": {
      "class": "logging.StreamHandler",
      "level": "INFO",
      "formatter": "standard",
      "stream": "ext://sys.stdout"
    },
    "file": {
      "class": "logging.handlers.RotatingFileHandler",
      "level": "DEBUG",
      "formatter": "standard",
      "filename": "logs/main.log",
      "maxBytes": 1048576,
      "backupCount": 5
    }
  },
  "loggers": {
    "": {
      "handlers": ["console", "file"],
      "level": "DEBUG",
      "propagate": true
    }
  }
}
```

## Usage

The configuration files in this directory are used by various components of the Shroombox system:

- The `settings.json` file is loaded by the `SettingsManager` to configure the application
- The `logging_config.json` file is used by the logging system to set up loggers
- Backup files are created automatically to prevent data loss

## Modifying Configuration Files

When modifying configuration files:
1. Make sure to validate the JSON structure to prevent syntax errors
2. Create backups before making significant changes
3. Document any new settings or configuration options
4. Use the appropriate manager classes to modify settings programmatically 