document.addEventListener('DOMContentLoaded', function() {
    const updateStatus = async () => {
        const res = await fetch('/api/server/status');
        const data = await res.json();
        
        const indicator = document.querySelector('.status-indicator');
        const statusText = document.querySelector('.status-text');
        
        if (data.status === 'running') {
            indicator.className = 'status-indicator online';
            statusText.textContent = 'Online';
            document.getElementById('ram-usage').textContent = data.ram_used_mb || '-';
            document.getElementById('player-count').textContent = data.players || '0';
        } else {
            indicator.className = 'status-indicator offline';
            statusText.textContent = 'Offline';
        }
    };

    // Ovládací tlačítka
    document.getElementById('start-btn')?.addEventListener('click', async () => {
        await fetch('/api/server/start', { method: 'POST' });
        setTimeout(updateStatus, 2000);
    });

    setInterval(updateStatus, 5000);
    updateStatus();
});