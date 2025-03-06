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
        
        fetchWithCacheBusting('/api/settings')
            .then(response => {
                if (!response.ok) throw new Error(`HTTP error ${response.status}`);
                return response.json();
            })
            .then(settings => {
                settings.environment.current_phase = this.value;
                return fetchWithCacheBusting('/api/settings', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(settings)
                });
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