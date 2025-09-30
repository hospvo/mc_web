// dashboard.js - optimalizovaná verze
document.addEventListener('DOMContentLoaded', function() {
    console.log('Dashboard loaded - starting optimized server monitoring');
    updateAllServersStatus();
    setInterval(updateAllServersStatus, 10000);
});

async function updateAllServersStatus() {
    try {
        console.log('Fetching all servers status...');
        
        // Nastavit všechny indikátory na loading
        document.querySelectorAll('.server-status').forEach(statusElement => {
            const indicator = statusElement.querySelector('.status-indicator');
            const text = statusElement.querySelector('.status-text');
            indicator.className = 'status-indicator status-loading';
            text.textContent = 'Kontroluji...';
        });
        
        // Jeden API call pro všechny servery
        const response = await fetch('/api/servers/status');
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const allStatuses = await response.json();
        console.log('All servers status:', allStatuses);
        
        // Aktualizovat všechny servery najednou
        document.querySelectorAll('.server-status').forEach(statusElement => {
            const serverId = statusElement.dataset.serverId;
            const status = allStatuses[serverId];
            
            if (status) {
                updateServerUI(statusElement, status);
            } else {
                showError(statusElement, 'Nenalezen');
            }
        });
        
    } catch (error) {
        console.error('Chyba při načítání stavů serverů:', error);
        document.querySelectorAll('.server-status').forEach(statusElement => {
            showError(statusElement, 'Chyba');
        });
    }
}

function updateServerUI(statusElement, statusData) {
    const indicator = statusElement.querySelector('.status-indicator');
    const text = statusElement.querySelector('.status-text');
    
    if (statusData.status === 'running') {
        indicator.className = 'status-indicator status-online';
        text.textContent = 'Online';
    } else if (statusData.status === 'stopped') {
        indicator.className = 'status-indicator status-offline';
        text.textContent = 'Offline';
    } else {
        indicator.className = 'status-indicator status-offline';
        text.textContent = statusData.status || 'Neznámý';
    }
}

function showError(statusElement, message) {
    const indicator = statusElement.querySelector('.status-indicator');
    const text = statusElement.querySelector('.status-text');
    indicator.className = 'status-indicator status-offline';
    text.textContent = message;
}