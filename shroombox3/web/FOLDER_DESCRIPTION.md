# Web Directory

This directory contains the web interface for the Shroombox project. The web interface provides a user-friendly way to monitor and control the Shroombox system through a browser.

## Files and Directories

- `web_server.py`: Main web server implementation using Flask
- `templates/`: Contains HTML templates for the web interface
- `static/`: Contains static assets (CSS, JavaScript, images)

## Web Server

The `web_server.py` file implements a Flask-based web server that:
- Provides API endpoints for retrieving sensor data
- Serves the web interface
- Handles user interactions and control commands
- Communicates with the main application components

## Templates

The `templates/` directory contains HTML templates using the Jinja2 templating engine:
- `index.html`: Main dashboard page
- `settings.html`: Settings configuration page
- `history.html`: Historical data visualization
- `layout.html`: Base template with common elements

## Static Assets

The `static/` directory contains static files used by the web interface:
- `css/`: Stylesheets for the web interface
- `js/`: JavaScript files for interactive features
- `images/`: Icons, logos, and other images
- `lib/`: Third-party libraries (Bootstrap, Chart.js, etc.)

## API Endpoints

The web server provides several API endpoints:

- `GET /api/measurements`: Returns current sensor measurements
- `GET /api/history`: Returns historical sensor data
- `GET /api/devices`: Returns information about connected devices
- `POST /api/settings`: Updates application settings
- `POST /api/control`: Sends control commands to devices

## Running the Web Interface

The web interface can be started using the provided shell scripts:

```bash
# Start the web interface
./scripts/run_web.sh

# Start as a service
./scripts/start_web.sh
```

## Development

When developing the web interface:
1. Make changes to templates and static files as needed
2. Test changes locally by running the web server
3. Use browser developer tools to debug issues
4. Ensure responsive design for different screen sizes

## Security Considerations

- The web interface is designed for local network use only
- Consider implementing authentication for production use
- Be cautious about exposing the interface to the internet
- Validate all user inputs to prevent security vulnerabilities 