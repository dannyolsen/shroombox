# Logs Directory

This directory contains log files generated by the Shroombox application. These logs record system events, errors, and other information useful for monitoring and debugging the system.

## Files

- `main.log`: Current main application log file
- `main.log.1`, `main.log.2`, etc.: Rotated backup log files for the main application
- `web.log`: Log file for the web interface

## Log Format

Log entries follow a standard format that includes timestamp, log level, module name, and message:

```
2023-03-08 08:17:00,123 [INFO] main: Application started
2023-03-08 08:17:01,456 [DEBUG] devices.sensor: SCD30 sensor initialized
2023-03-08 08:17:02,789 [ERROR] managers.device_manager: Failed to connect to device: Connection refused
```

## Log Levels

The logs contain entries with different severity levels:

- **DEBUG**: Detailed information, typically useful only for diagnosing problems
- **INFO**: Confirmation that things are working as expected
- **WARNING**: Indication that something unexpected happened, but the application is still working
- **ERROR**: Due to a more serious problem, the application has not been able to perform a function
- **CRITICAL**: A serious error indicating that the application itself may be unable to continue running

## Log Rotation

Log files are automatically rotated when they reach a certain size (typically 1MB). This prevents log files from growing too large and consuming excessive disk space. The rotation system keeps several backup files (e.g., `main.log.1`, `main.log.2`, etc.) before discarding the oldest logs.

## Usage

The log files in this directory are used for:

- Monitoring system operation
- Diagnosing problems and errors
- Tracking system performance
- Auditing system activity

## Accessing Logs

You can view logs using standard text tools:

```bash
# View the most recent log entries
tail -f logs/main.log

# Search for errors
grep ERROR logs/main.log

# View logs for a specific component
grep "devices.sensor" logs/main.log
```

## Log Management

- Log files should be periodically archived or deleted to prevent disk space issues
- The logging configuration can be adjusted in `config/logging_config.json`
- For production systems, consider implementing log forwarding to a centralized logging system 