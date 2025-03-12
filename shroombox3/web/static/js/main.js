// Enhanced main.js file with cache-busting and better error handling
console.log("Main.js loaded successfully");

// Default polling intervals (in milliseconds)
let MEASUREMENT_POLLING_INTERVAL = 8000;
let DEVICE_POLLING_INTERVAL = 3000;
const MIN_UPDATE_INTERVAL = 2000; // Minimum time between UI updates in ms

// Functions to update polling intervals
function setMeasurementPollingInterval(interval) {
    // Validate interval (minimum 1000ms)
    interval = Math.max(1000, parseInt(interval));
    MEASUREMENT_POLLING_INTERVAL = interval;
    
    // Restart polling with new interval if it's currently active
    if (measurementPollingInterval) {
        stopMeasurementPolling();
        startMeasurementPolling();
    }
    
    console.log(`Measurement polling interval set to ${interval}ms`);
    return interval;
}

function setDevicePollingInterval(interval) {
    // Validate interval (minimum 1000ms)
    interval = Math.max(1000, parseInt(interval));
    DEVICE_POLLING_INTERVAL = interval;
    
    // Restart polling with new interval if it's currently active
    if (devicePollingInterval) {
        stopDevicePolling();
        startDevicePolling();
    }
    
    console.log(`Device polling interval set to ${interval}ms`);
    return interval;
}

// Functions to handle UI interactions for polling settings
function updateMeasurementPolling(seconds) {
    const ms = Math.max(1, parseInt(seconds)) * 1000;
    setMeasurementPollingInterval(ms);
    
    // Save to localStorage for persistence
    localStorage.setItem('measurementPollingInterval', ms);
    
    // Show feedback
    showPollingFeedback('measurement', seconds);
}

function updateDevicePolling(seconds) {
    const ms = Math.max(1, parseInt(seconds)) * 1000;
    setDevicePollingInterval(ms);
    
    // Save to localStorage for persistence
    localStorage.setItem('devicePollingInterval', ms);
    
    // Show feedback
    showPollingFeedback('device', seconds);
}

function showPollingFeedback(type, seconds) {
    const inputId = `${type}-polling-interval`;
    const input = document.getElementById(inputId);
    
    if (!input) return;
    
    // Add a temporary success indicator with a green border and background
    const originalBorderColor = input.style.borderColor;
    const originalBackgroundColor = input.style.backgroundColor;
    
    // Apply visual feedback to the input
    input.style.borderColor = '#10B981'; // Green color
    input.style.backgroundColor = '#D1FAE5'; // Light green background
    
    // Create a confirmation message next to the input
    const parentElement = input.parentElement;
    let confirmationMessage = document.getElementById(`${type}-confirmation`);
    
    if (!confirmationMessage) {
        confirmationMessage = document.createElement('div');
        confirmationMessage.id = `${type}-confirmation`;
        confirmationMessage.className = 'ml-2 text-sm text-green-600 font-medium flex items-center';
        confirmationMessage.innerHTML = `
            <svg class="w-4 h-4 mr-1" fill="currentColor" viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg">
                <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd"></path>
            </svg>
            <span>Updated!</span>
        `;
        parentElement.appendChild(confirmationMessage);
    } else {
        // If it already exists, make it visible again
        confirmationMessage.style.display = 'flex';
    }
    
    // Reset the input styling and remove confirmation message after delay
    setTimeout(() => {
        input.style.borderColor = originalBorderColor;
        input.style.backgroundColor = originalBackgroundColor;
        
        // Fade out the confirmation message
        if (confirmationMessage) {
            confirmationMessage.style.opacity = '0';
            confirmationMessage.style.transition = 'opacity 0.5s';
            setTimeout(() => {
                if (confirmationMessage.parentNode) {
                    confirmationMessage.style.display = 'none';
                    confirmationMessage.style.opacity = '1';
                }
            }, 500);
        }
    }, 2500);
    
    // Show toast notification if Alpine.js is available
    if (window.Alpine) {
        const controlPanel = Alpine.store('controlPanel');
        if (controlPanel && typeof controlPanel.showToast === 'function') {
            const typeLabel = type === 'measurement' ? 'Sensor data' : 'Device status';
            controlPanel.showToast(`${typeLabel} polling interval updated to ${seconds} seconds`, 'success');
        }
    } else {
        // Fallback for when Alpine.js is not available
        createStandaloneToast(`${type === 'measurement' ? 'Sensor data' : 'Device status'} polling interval updated to ${seconds} seconds`);
    }
    
    // Log the change to console for debugging
    console.log(`${type === 'measurement' ? 'Sensor data' : 'Device status'} polling interval updated to ${seconds} seconds`);
}

// Create a standalone toast when Alpine.js is not available
function createStandaloneToast(message) {
    const toastContainer = document.getElementById('toast-container') || createToastContainer();
    
    const toast = document.createElement('div');
    toast.className = 'fixed bottom-4 right-4 bg-green-500 text-white px-4 py-2 rounded shadow-lg z-50 animate-fade-in';
    toast.textContent = message;
    
    toastContainer.appendChild(toast);
    
    // Remove toast after 3 seconds
    setTimeout(() => {
        toast.classList.add('animate-fade-out');
        setTimeout(() => {
            if (toast.parentNode) {
                toast.parentNode.removeChild(toast);
            }
        }, 300);
    }, 3000);
}

function createToastContainer() {
    const container = document.createElement('div');
    container.id = 'toast-container';
    container.className = 'fixed bottom-4 right-4 flex flex-col space-y-2 z-50';
    document.body.appendChild(container);
    return container;
}

// Add cache-busting to fetch requests
function fetchWithCacheBusting(url, options = {}) {
    // Add timestamp to URL to prevent caching
    const cacheBuster = `_cb=${Date.now()}`;
    const separator = url.includes('?') ? '&' : '?';
    const urlWithCacheBuster = `${url}${separator}${cacheBuster}`;
    
    return fetch(urlWithCacheBuster, options);
}

// Debounce function to limit how often a function can be called
function debounce(func, wait) {
    let timeout;
    return function(...args) {
        const context = this;
        clearTimeout(timeout);
        timeout = setTimeout(() => func.apply(context, args), wait);
    };
}

// Add any initialization code here
document.addEventListener('DOMContentLoaded', () => {
    console.log("DOM fully loaded");
    
    // Load saved polling intervals from localStorage
    const savedMeasurementInterval = localStorage.getItem('measurementPollingInterval');
    const savedDeviceInterval = localStorage.getItem('devicePollingInterval');
    
    if (savedMeasurementInterval) {
        MEASUREMENT_POLLING_INTERVAL = parseInt(savedMeasurementInterval);
        // Update the input field
        const input = document.getElementById('measurement-polling-interval');
        if (input) {
            input.value = MEASUREMENT_POLLING_INTERVAL / 1000;
        }
    }
    
    if (savedDeviceInterval) {
        DEVICE_POLLING_INTERVAL = parseInt(savedDeviceInterval);
        // Update the input field
        const input = document.getElementById('device-polling-interval');
        if (input) {
            input.value = DEVICE_POLLING_INTERVAL / 1000;
        }
    }
    
    // Immediately fetch initial data before starting polling
    // This ensures data is displayed right away without waiting for the polling interval
    Promise.all([
        updateDeviceStatus(),
        updateMeasurements()
    ]).then(() => {
        console.log("Initial data loaded successfully");
    }).catch(error => {
        console.error("Error loading initial data:", error);
    });
    
    // Start measurement polling with the configured interval
    startMeasurementPolling();
    
    // Start device polling with the configured interval
    startDevicePolling();
    
    // Load initial phase from settings with cache-busting (but don't add event listener)
    const phaseSelect = document.getElementById('phase-select');
    if (phaseSelect) {
        fetchWithCacheBusting('/api/settings')
            .then(response => {
                if (!response.ok) throw new Error(`HTTP error ${response.status}`);
                return response.json();
            })
            .then(data => {
                // Only set the value if Alpine.js isn't handling it
                if (!window.Alpine) {
                    phaseSelect.value = data.environment.current_phase;
                    console.log('Phase loaded:', phaseSelect.value);
                }
            })
            .catch(error => {
                console.error('Error loading settings:', error);
                // Add visual feedback for errors
                const errorMsg = document.createElement('div');
                errorMsg.className = 'text-red-600 text-sm mt-1';
                errorMsg.textContent = `Error loading settings: ${error.message}`;
                phaseSelect.parentNode.appendChild(errorMsg);
                
                // Auto-remove error after 5 seconds
                setTimeout(() => {
                    if (errorMsg.parentNode) {
                        errorMsg.parentNode.removeChild(errorMsg);
                    }
                }, 5000);
            });
    }
});

// Add device polling functionality
let devicePollingInterval = null;

function startDevicePolling() {
    // Use the configurable interval
    devicePollingInterval = setInterval(updateDeviceStatus, DEVICE_POLLING_INTERVAL);
    console.log(`Device polling started (interval: ${DEVICE_POLLING_INTERVAL}ms)`);
}

function stopDevicePolling() {
    if (devicePollingInterval) {
        clearInterval(devicePollingInterval);
        devicePollingInterval = null;
        console.log("Device polling stopped");
    }
}

async function updateDeviceStatus() {
    try {
        // Add a timeout to the fetch to prevent hanging requests
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 5000); // 5 second timeout
        
        try {
            // Fetch all devices with cache busting
            const response = await fetchWithCacheBusting('/api/devices/all', {
                signal: controller.signal
            });
            
            clearTimeout(timeoutId); // Clear the timeout if fetch completes
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const data = await response.json();
            if (data.status === 'success' && data.devices) {
                // Update UI for each device
                data.devices.forEach(device => {
                    updateDeviceUI(device);
                });
                
                // If Alpine.js is available, update the device states in the Alpine component
                if (window.Alpine) {
                    const controlPanel = Alpine.store('controlPanel');
                    if (controlPanel && typeof controlPanel.updateDeviceStates === 'function') {
                        controlPanel.updateDeviceStates(data.devices);
                    }
                }
            }
        } catch (fetchError) {
            clearTimeout(timeoutId); // Clear the timeout if fetch fails
            
            if (fetchError.name === 'AbortError') {
                console.warn("Device status update request timed out");
                // Show timeout message in UI
                showDeviceError("Device status update timed out. The server may be busy.");
            } else {
                throw fetchError; // Re-throw for the outer catch
            }
        }
    } catch (error) {
        console.error("Error updating device status:", error);
        showDeviceError(`Failed to update device status: ${error.message}`);
    }
}

function updateDeviceUI(device) {
    // Find device elements by role or name
    const deviceElements = document.querySelectorAll(`[data-device="${device.role}"], [data-device="${device.name}"]`);
    
    deviceElements.forEach(element => {
        // Update status display
        const statusElement = element.querySelector('.device-status');
        if (statusElement) {
            statusElement.textContent = device.state ? 'ON' : 'OFF';
            statusElement.className = `device-status px-2 py-1 text-xs font-medium rounded-full ${device.state ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-800'}`;
        }
        
        // Update toggle buttons
        const toggleButton = element.querySelector('.toggle-button');
        if (toggleButton) {
            toggleButton.textContent = device.state ? 'Turn OFF' : 'Turn ON';
            toggleButton.className = `toggle-button ml-2 px-2 py-1 text-xs font-medium rounded text-white hover:bg-blue-600 focus:outline-none focus:ring-2 focus:ring-blue-500 ${device.state ? 'bg-blue-500' : 'bg-blue-500'}`;
        }
    });
}

// Helper function to show device errors in the UI
function showDeviceError(message) {
    // Find device status container
    const deviceStatusContainer = document.getElementById('device-status-container');
    if (deviceStatusContainer) {
        // Create or update error message
        let errorElement = document.getElementById('device-status-error');
        if (!errorElement) {
            errorElement = document.createElement('div');
            errorElement.id = 'device-status-error';
            errorElement.className = 'bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded relative mt-4';
            
            const closeButton = document.createElement('button');
            closeButton.className = 'absolute top-0 right-0 px-2 py-1 text-red-700';
            closeButton.textContent = '×';
            closeButton.onclick = function() {
                errorElement.remove();
            };
            
            errorElement.appendChild(closeButton);
            deviceStatusContainer.appendChild(errorElement);
        }
        
        // Set or update the message
        const textContent = errorElement.querySelector('.error-text') || document.createElement('span');
        textContent.className = 'error-text';
        textContent.textContent = message;
        
        if (!textContent.parentNode) {
            errorElement.appendChild(textContent);
        }
        
        // Auto-hide after 10 seconds
        setTimeout(() => {
            if (errorElement && errorElement.parentNode) {
                errorElement.remove();
            }
        }, 10000);
    }
}

// Add measurement polling functionality
let measurementPollingInterval = null;
let lastMeasurementUpdate = 0;

function startMeasurementPolling() {
    // Use the configurable interval
    measurementPollingInterval = setInterval(updateMeasurements, MEASUREMENT_POLLING_INTERVAL);
    console.log(`Measurement polling started (interval: ${MEASUREMENT_POLLING_INTERVAL}ms)`);
}

function stopMeasurementPolling() {
    if (measurementPollingInterval) {
        clearInterval(measurementPollingInterval);
        measurementPollingInterval = null;
        console.log("Measurement polling stopped");
    }
}

// Debounced version of updateMeasurementsUI to prevent too frequent DOM updates
const debouncedUpdateUI = debounce(updateMeasurementsUI, 500);

async function updateMeasurements() {
    try {
        // Throttle updates to prevent excessive API calls
        const now = Date.now();
        if (now - lastMeasurementUpdate < MIN_UPDATE_INTERVAL) {
            console.log("Throttling measurement update");
            return;
        }
        
        lastMeasurementUpdate = now;
        
        // Add a timeout to the fetch to prevent hanging requests
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 5000); // 5 second timeout
        
        try {
            // Fetch latest measurements
            const response = await fetchWithCacheBusting('/api/measurements/latest', {
                signal: controller.signal
            });
            
            clearTimeout(timeoutId); // Clear the timeout if fetch completes
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const data = await response.json();
            
            // Update UI with measurements using debounced function
            debouncedUpdateUI(data);
            
            // If Alpine.js is available, update the measurements in the Alpine component
            if (window.Alpine) {
                const controlPanel = Alpine.store('controlPanel');
                if (controlPanel && typeof controlPanel.updateMeasurementsFromPolling === 'function') {
                    controlPanel.updateMeasurementsFromPolling(data);
                }
            }
        } catch (fetchError) {
            clearTimeout(timeoutId); // Clear the timeout if fetch fails
            
            if (fetchError.name === 'AbortError') {
                console.warn("Measurement update request timed out");
                // Update UI to show timeout
                const timeoutData = {
                    source: 'error',
                    sensor_status: {
                        available: false,
                        message: 'Request timed out. Sensor may be busy or unavailable.'
                    }
                };
                debouncedUpdateUI(timeoutData);
            } else {
                throw fetchError; // Re-throw for the outer catch
            }
        }
    } catch (error) {
        console.error("Error updating measurements:", error);
        
        // Update UI to show error state
        const errorData = {
            source: 'error',
            sensor_status: {
                available: false,
                message: `Error: ${error.message}`
            }
        };
        debouncedUpdateUI(errorData);
    }
}

function updateMeasurementsUI(data) {
    // Update temperature display
    const temperatureElement = document.querySelector('.temperature-value');
    if (temperatureElement && data.temperature !== undefined) {
        temperatureElement.textContent = `${data.temperature} °C`;
    } else if (temperatureElement && data.source === 'error') {
        temperatureElement.textContent = `-- °C`;
        temperatureElement.classList.add('text-gray-400');
    }
    
    // Update humidity display
    const humidityElement = document.querySelector('.humidity-value');
    if (humidityElement && data.humidity !== undefined) {
        humidityElement.textContent = `${data.humidity} %`;
    } else if (humidityElement && data.source === 'error') {
        humidityElement.textContent = `-- %`;
        humidityElement.classList.add('text-gray-400');
    }
    
    // Update CO2 display
    const co2Element = document.querySelector('.co2-value');
    if (co2Element && data.co2 !== undefined) {
        co2Element.textContent = `${data.co2} ppm`;
    } else if (co2Element && data.source === 'error') {
        co2Element.textContent = `-- ppm`;
        co2Element.classList.add('text-gray-400');
    }
    
    // Update fan speed display
    const fanSpeedElement = document.querySelector('.fan-speed-value');
    if (fanSpeedElement && data.fan_speed !== undefined) {
        fanSpeedElement.textContent = `${data.fan_speed} %`;
    } else if (fanSpeedElement && data.source === 'error') {
        fanSpeedElement.textContent = `-- %`;
        fanSpeedElement.classList.add('text-gray-400');
    }
    
    // Update data source indicator
    const sourceElement = document.querySelector('.data-source');
    if (sourceElement) {
        let sourceText = 'Unknown';
        let sourceClass = 'text-gray-500';
        
        if (data.source === 'sensor') {
            // Check if sensor is available
            if (data.sensor_status && !data.sensor_status.available) {
                sourceText = 'Sensor Error';
                sourceClass = 'text-red-600';
            } else {
                sourceText = 'Sensor (Real-time)';
                sourceClass = 'text-green-600';
            }
        } else if (data.source === 'cache') {
            sourceText = `Cached (${Math.round(data.cache_age)}s old)`;
            sourceClass = 'text-yellow-600';
        } else if (data.source === 'influxdb') {
            sourceText = 'InfluxDB (Historical)';
            sourceClass = 'text-blue-600';
        } else if (data.source === 'error') {
            sourceText = 'Connection Error';
            sourceClass = 'text-red-600';
        }
        
        sourceElement.textContent = sourceText;
        sourceElement.className = `data-source ${sourceClass} text-sm`;
    }
    
    // Update sensor status indicators if they exist
    if (data.sensor_status) {
        // Warning indicator (when sensor is not available)
        const statusContainer = document.getElementById('sensor-status-container');
        if (statusContainer) {
            if (!data.sensor_status.available) {
                statusContainer.classList.remove('hidden');
                
                const statusMessage = document.getElementById('sensor-status-message');
                if (statusMessage) {
                    statusMessage.textContent = data.sensor_status.message;
                }
            } else {
                statusContainer.classList.add('hidden');
            }
        }
        
        // Success indicator (when sensor is available)
        const successContainer = document.getElementById('sensor-status-success');
        if (successContainer) {
            if (data.sensor_status.available) {
                successContainer.classList.remove('hidden');
                
                const successMessage = document.getElementById('sensor-status-success-message');
                if (successMessage) {
                    successMessage.textContent = 'Sensor connected and working properly';
                }
            } else {
                successContainer.classList.add('hidden');
            }
        }
        
        // Update the measurement source indicators based on sensor status
        const liveIndicators = document.querySelectorAll('.measurement-source');
        if (liveIndicators.length > 0) {
            // Force Alpine.js to re-evaluate the conditions
            if (window.Alpine) {
                window.Alpine.nextTick(() => {
                    console.log('Forcing Alpine.js to update measurement source indicators');
                });
            }
        }
    }
}

// Start both polling mechanisms when the page loads
document.addEventListener('DOMContentLoaded', function() {
    startDevicePolling();
    startMeasurementPolling();
    
    // Add event listeners for device control buttons
    document.querySelectorAll('.toggle-button').forEach(button => {
        button.addEventListener('click', async function() {
            const deviceIP = this.getAttribute('data-ip');
            const currentState = this.classList.contains('on');
            const newState = !currentState;
            
            try {
                const response = await fetch('/api/devices/control/direct', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        ip: deviceIP,
                        state: newState
                    })
                });
                
                if (response.ok) {
                    // Force an immediate update
                    updateDeviceStatus();
                }
            } catch (error) {
                console.error("Error controlling device:", error);
            }
        });
    });
});

// Clean up when the page is unloaded
window.addEventListener('beforeunload', function() {
    stopDevicePolling();
    stopMeasurementPolling();
}); 