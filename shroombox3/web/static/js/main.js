// Enhanced main.js file with cache-busting and better error handling
console.log("Main.js loaded successfully");

// Add cache-busting to fetch requests
function fetchWithCacheBusting(url, options = {}) {
    // Add timestamp to URL to prevent caching
    const cacheBuster = `_cb=${Date.now()}`;
    const separator = url.includes('?') ? '&' : '?';
    const urlWithCacheBuster = `${url}${separator}${cacheBuster}`;
    
    return fetch(urlWithCacheBuster, options);
}

// Add any initialization code here
document.addEventListener('DOMContentLoaded', () => {
    console.log("DOM fully loaded");
    const phaseSelect = document.getElementById('phase-select');
    
    if (!phaseSelect) {
        console.warn('Phase select element not found');
        return;
    }
    
    // Load initial phase from settings with cache-busting
    fetchWithCacheBusting('/api/settings')
        .then(response => {
            if (!response.ok) throw new Error(`HTTP error ${response.status}`);
            return response.json();
        })
        .then(data => {
            phaseSelect.value = data.environment.current_phase;
            console.log('Phase loaded:', phaseSelect.value);
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
    
    // Handle phase changes with improved error handling
    phaseSelect.addEventListener('change', function() {
        // Disable select while updating
        this.disabled = true;
        
        // Show loading indicator
        const loadingIndicator = document.createElement('span');
        loadingIndicator.className = 'ml-2 text-sm text-gray-600';
        loadingIndicator.textContent = 'Updating...';
        this.parentNode.appendChild(loadingIndicator);
        
        fetchWithCacheBusting('/api/settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                environment: {
                    current_phase: this.value
                }
            })
        })
        .then(response => {
            if (!response.ok) {
                throw new Error(`Failed to update phase: HTTP error ${response.status}`);
            }
            console.log('Phase updated successfully, reloading page');
            
            // Add a small delay before reloading to ensure settings are saved
            setTimeout(() => {
                // Add cache-busting to the reload
                window.location.href = window.location.pathname + '?_cb=' + Date.now();
            }, 500);
        })
        .catch(error => {
            console.error('Error updating phase:', error);
            
            // Show error message
            const errorMsg = document.createElement('div');
            errorMsg.className = 'text-red-600 text-sm mt-1';
            errorMsg.textContent = `Error: ${error.message}`;
            this.parentNode.appendChild(errorMsg);
            
            // Re-enable select
            this.disabled = false;
            
            // Auto-remove error after 5 seconds
            setTimeout(() => {
                if (errorMsg.parentNode) {
                    errorMsg.parentNode.removeChild(errorMsg);
                }
            }, 5000);
            
            alert('Failed to update growth phase: ' + error.message);
        })
        .finally(() => {
            // Remove loading indicator
            if (loadingIndicator.parentNode) {
                loadingIndicator.parentNode.removeChild(loadingIndicator);
            }
        });
    });
});

// Add device status polling functionality
let devicePollingInterval = null;

function startDevicePolling() {
    // Poll every 2 seconds
    devicePollingInterval = setInterval(updateDeviceStatus, 2000);
    console.log("Device status polling started");
}

function stopDevicePolling() {
    if (devicePollingInterval) {
        clearInterval(devicePollingInterval);
        devicePollingInterval = null;
        console.log("Device status polling stopped");
    }
}

async function updateDeviceStatus() {
    try {
        // Fetch all devices
        const response = await fetch('/api/devices/all');
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
    } catch (error) {
        console.error("Error updating device status:", error);
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

// Add measurement polling functionality
let measurementPollingInterval = null;

function startMeasurementPolling() {
    // Poll every 5 seconds
    measurementPollingInterval = setInterval(updateMeasurements, 5000);
    console.log("Measurement polling started");
}

function stopMeasurementPolling() {
    if (measurementPollingInterval) {
        clearInterval(measurementPollingInterval);
        measurementPollingInterval = null;
        console.log("Measurement polling stopped");
    }
}

async function updateMeasurements() {
    try {
        // Fetch latest measurements
        const response = await fetchWithCacheBusting('/api/measurements/latest');
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        
        // Update UI with measurements
        updateMeasurementsUI(data);
        
        // If Alpine.js is available, update the measurements in the Alpine component
        if (window.Alpine) {
            const controlPanel = Alpine.store('controlPanel');
            if (controlPanel && typeof controlPanel.updateMeasurementsFromPolling === 'function') {
                controlPanel.updateMeasurementsFromPolling(data);
            }
        }
    } catch (error) {
        console.error("Error updating measurements:", error);
    }
}

function updateMeasurementsUI(data) {
    // Update temperature display
    const tempElement = document.querySelector('.temperature-value');
    if (tempElement && data.temperature) {
        tempElement.textContent = `${data.temperature} °C`;
    }
    
    // Update humidity display
    const humidityElement = document.querySelector('.humidity-value');
    if (humidityElement && data.humidity) {
        humidityElement.textContent = `${data.humidity} %`;
    }
    
    // Update CO2 display
    const co2Element = document.querySelector('.co2-value');
    if (co2Element && data.co2) {
        co2Element.textContent = `${data.co2} ppm`;
    }
    
    // Update source indicators
    const sourceElements = document.querySelectorAll('.measurement-source');
    sourceElements.forEach(element => {
        if (data.source === 'sensor') {
            element.textContent = 'Live';
            element.className = 'measurement-source text-green-500 text-xs';
        } else if (data.source === 'cache') {
            element.textContent = 'Cached';
            element.className = 'measurement-source text-yellow-500 text-xs';
        } else if (data.source === 'influxdb') {
            element.textContent = 'Database';
            element.className = 'measurement-source text-blue-500 text-xs';
        }
    });
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