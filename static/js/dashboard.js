// dashboard.js
document.addEventListener('DOMContentLoaded', function() {
    console.log('Dashboard loaded - starting optimized server monitoring');

    // Aktualizace stavů serverů
    updateAllServersStatus();
    setInterval(updateAllServersStatus, 10000);

    // Připojení k serveru pomocí kódu
    const joinBtn = document.getElementById('join-server-btn');
    const codeInput = document.getElementById('access-code-input');

    if (joinBtn && codeInput) {
        joinBtn.addEventListener('click', joinServerWithCode);
        codeInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') joinServerWithCode();
        });

        // Automaticky převést na uppercase
        codeInput.addEventListener('input', function() {
            this.value = this.value.toUpperCase();
        });
    }
});

/* ---- STAVY SERVERŮ ---- */
async function updateAllServersStatus() {
    try {
        // Nastav stav "načítám" jen pokud ještě není Online/Offline
        document.querySelectorAll('.server-status').forEach(statusElement => {
            const text = statusElement.querySelector('.status-text');
            if (text && text.textContent === '') {
                const indicator = statusElement.querySelector('.status-indicator');
                indicator.className = 'status-indicator status-loading';
                text.textContent = 'Kontroluji...';
            }
        });

        const response = await fetch('/api/servers/status');
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);

        const allStatuses = await response.json();

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

        // Pokud selže fetch, jen jednou označ všechny jako neaktivní
        document.querySelectorAll('.server-status').forEach(statusElement => {
            const text = statusElement.querySelector('.status-text');
            if (text && text.textContent !== 'Offline') {
                showError(statusElement, 'Chyba');
            }
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

/* ---- PŘIPOJENÍ POMOCÍ KÓDU ---- */
async function joinServerWithCode() {
    const codeInput = document.getElementById('access-code-input');
    const code = codeInput.value.trim().toUpperCase();

    if (!code || code.length !== 6) {
        alert('Zadejte platný 6-místný kód');
        return;
    }

    const btn = document.getElementById('join-server-btn');
    const originalText = btn.innerHTML;

    try {
        btn.disabled = true;
        btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Připojování...';

        const response = await fetch('/api/player/join-with-code', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ access_code: code })
        });

        const result = await response.json();

        if (result.success) {
            alert(`Úspěšně jste se připojili k serveru: ${result.server_name}`);
            codeInput.value = '';

            // 🔁 NOVINKA: přesměrování do player pohledu, pokud server_id existuje
            if (result.server_id) {
                window.location.href = `/server/${result.server_id}/player`;
            } else {
                setTimeout(() => window.location.reload(), 1000);
            }

        } else {
            alert(`Chyba: ${result.error}`);
        }

    } catch (error) {
        console.error('Chyba při připojování:', error);
        alert('Chyba při připojování k serveru');
    } finally {
        btn.disabled = false;
        btn.innerHTML = originalText;
    }
}
