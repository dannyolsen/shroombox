document.addEventListener('DOMContentLoaded', function() {
    const phaseSelect = document.getElementById('phase-select');
    
    // Load initial phase from settings
    fetch('/api/settings')
        .then(response => response.json())
        .then(data => {
            phaseSelect.value = data.environment.current_phase;
        })
        .catch(error => console.error('Error loading settings:', error));
    
    // Handle phase changes
    phaseSelect.addEventListener('change', function() {
        fetch('/api/settings')
            .then(response => response.json())
            .then(settings => {
                settings.environment.current_phase = this.value;
                return fetch('/api/settings', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(settings)
                });
            })
            .then(response => {
                if (response.ok) {
                    location.reload();
                } else {
                    throw new Error('Failed to update phase');
                }
            })
            .catch(error => {
                console.error('Error updating phase:', error);
                alert('Failed to update growth phase');
            });
    });
}); 