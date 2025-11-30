// Získání server_id z URL nebo z localStorage (fallback)
function getCurrentServerId() {
    const pathParts = window.location.pathname.split('/');
    const serverIdFromUrl = pathParts[2]; // /server/<id> => část na indexu 2

    if (serverIdFromUrl && !isNaN(serverIdFromUrl)) {
        return parseInt(serverIdFromUrl);
    }
    const lastServerId = localStorage.getItem('current_server_id');
    if (lastServerId && !isNaN(lastServerId)) {
        return parseInt(lastServerId);
    }
    console.error('Nelze získat server_id z URL:', window.location.pathname);
    return null;
}

// === ZÁKLADNÍ PROMĚNNÉ ===
let currentModpacks = [];

// Tlačítko zpět na dashboard
function setupBackButton() {
    const btn = document.getElementById('back-btn');
    if (btn) {
        btn.addEventListener('click', () => {
            window.location.href = '/dashboard';
        });
    }
}

// === DETEKCE BUILD TYPE ===

function getServerBuildType() {
    const pathParts = window.location.pathname.split('/');
    const serverId = pathParts[2];
    return localStorage.getItem(`server_${serverId}_build_type`) || 'UNKNOWN';
}

function isModServer(buildType) {
    const modBuilds = [
        'FABRIC', 'FORGE', 'NEOFORGE', 'QUILT', 'BABRIC', 'BTA',
        'JAVA_AGENT', 'LEGACY_FABRIC', 'LITELOADER', 'MODLOADER',
        'NILLOADER', 'ORNITHE', 'RIFT', 'RISUGAMI'
    ];
    return modBuilds.includes(buildType.toUpperCase());
}

function isPluginServer(buildType) {
    const pluginBuilds = [
        'BUKKIT', 'FOLIA', 'PAPER', 'PURPUR', 'SPIGOT', 'SPONGE'
    ];
    return pluginBuilds.includes(buildType.toUpperCase());
}

// === HLAVNÍ FUNKCE PRO SPRÁVU ZOBRAZENÍ MODŮ / PLUGINŮ ===
async function manageServerComponents() {
    const serverId = getCurrentServerId();
    let buildType;

    try {
        const response = await fetch(`/api/server/build-type?server_id=${serverId}`);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        buildType = data.build_type;
        localStorage.setItem(`server_${serverId}_build_type`, data.build_type);
    } catch (error) {
        console.error('Chyba při získávání build type:', error);
        buildType = getServerBuildType(); // fallback
    }

    const modsSection = document.querySelector('.mods-quickview');
    const pluginsSection = document.querySelector('.plugins-quickview');
    const clientToolsSection = document.querySelector('.client-tools-section');
    const modpacksSection = document.querySelector('.modpacks-management-section');

    // === MÓDOVÝ SERVER ===
    if (isModServer(buildType)) {
        if (modsSection) modsSection.style.display = 'block';
        if (pluginsSection) pluginsSection.style.display = 'none';
        if (clientToolsSection) clientToolsSection.style.display = 'block';
        if (modpacksSection) modpacksSection.style.display = 'block';

        try {
            await loadInstalledModsQuickview();
            await initModpacksManagement();
        } catch (error) {
            console.error('Chyba při načítání modů:', error);
        }

        if (typeof initClientTools === 'function') {
            initClientTools(serverId);
        }

        // === PLUGINOVÝ SERVER ===
    } else if (isPluginServer(buildType)) {
        if (modsSection) modsSection.style.display = 'none';
        if (pluginsSection) pluginsSection.style.display = 'block';
        if (clientToolsSection) clientToolsSection.style.display = 'none';
        if (modpacksSection) modpacksSection.style.display = 'none';

        try {
            await loadQuickViewPlugins();
        } catch (error) {
            console.error('Chyba při načítání pluginů:', error);
        }

        // === NEZNÁMÝ BUILD ===
    } else {
        console.warn('Neznámý typ buildu:', buildType);
        if (modsSection) modsSection.style.display = 'none';
        if (pluginsSection) pluginsSection.style.display = 'none';
        if (clientToolsSection) clientToolsSection.style.display = 'none';
        if (modpacksSection) modpacksSection.style.display = 'none';
    }
}

// === NAČTENÍ TYPŮ SERVERU ===
async function loadServerBuildType() {
    try {
        const response = await fetch(`/api/server/build-type?server_id=${getCurrentServerId()}`);
        const data = await response.json();
        localStorage.setItem(`server_${getCurrentServerId()}_build_type`, data.build_type);
        manageServerComponents();
    } catch (error) {
        console.error('Chyba při načítání typu serveru:', error);
        manageServerComponents(); // fallback
    }
}

// === NAČTENÍ INFO O SERVERU ===
async function loadServerInfo() {
    const serverId = getCurrentServerId();
    try {
        const response = await fetch(`/api/server/info?server_id=${serverId}`);
        const data = await response.json();

        if (data.error) {
            console.error("Chyba při získávání informací o serveru:", data.error);
            return;
        }

        document.getElementById('server-loader').textContent = data.server_loader || '-';
        document.getElementById('mc-version').textContent = data.mc_version || '-';
    } catch (error) {
        console.error("Chyba při načítání informací o serveru:", error);
    }
}

// === INICIALIZACE ===
document.addEventListener('DOMContentLoaded', function () {
    const serverId = getCurrentServerId();
    setupBackButton();
    loadServerBuildType();
    loadServerInfo();
    //updateStatus();

    async function updateStatus() {
        try {
            const response = await fetch(`/api/server/status?server_id=${serverId}`);
            const data = await response.json();

            const indicator = document.querySelector('.status-indicator');
            const statusText = document.querySelector('.status-text');

            if (data.status === 'running') {
                indicator.className = 'status-indicator online';
                statusText.textContent = 'Online';
                document.getElementById('ram-usage').textContent = data.ram_used_mb || '-';
                document.getElementById('cpu-usage').textContent = data.cpu_percent || '0';
                document.getElementById('cpu-max').textContent = data.cpu_max || '';
                document.getElementById('player-count').textContent = data.players || '0';
                document.getElementById('player-count-display').textContent = data.players || '0';
                updatePlayerList(data.player_names || []);
            } else {
                indicator.className = 'status-indicator offline';
                statusText.textContent = 'Offline';
                document.getElementById('ram-usage').textContent = '-';
                document.getElementById('cpu-usage').textContent = data.cpu_percent || '-';
                document.getElementById('player-count').textContent = '-';
                document.getElementById('player-count-display').textContent = '0';
                updatePlayerList([]);
            }
        } catch (error) {
            console.error('Chyba při načítání stavu:', error);
        }
    }

    let lastPlayerList = [];

    function updatePlayerList(players) {
        const table = document.getElementById('online-players-table');
        const tbody = document.getElementById('online-players-list');
        const noPlayersMsg = document.getElementById('no-players-message');

        // Rychlé porovnání – pokud se seznam nezměnil, nic nedělej
        if (arraysEqual(players, lastPlayerList)) {
            return; // Žádná změna, nevykonáváme nic
        }

        // Ulož nový seznam jako poslední známý
        lastPlayerList = players;

        // Vymaž starý obsah
        tbody.innerHTML = '';

        if (players.length > 0) {
            table.style.display = 'table';
            noPlayersMsg.style.display = 'none';

            players.forEach((player, index) => {
                const row = document.createElement('tr');
                row.innerHTML = `
                <td>${index + 1}</td>
                <td>${player}</td>
            `;
                tbody.appendChild(row);
            });
        } else {
            table.style.display = 'none';
            noPlayersMsg.style.display = 'block';
        }
    }

    function arraysEqual(a, b) {
        if (a.length !== b.length) return false;
        for (let i = 0; i < a.length; i++) {
            if (a[i] !== b[i]) return false;
        }
        return true;
    }

    // Start serveru
    document.getElementById('start-btn').addEventListener('click', async () => {
        try {
            const response = await fetch(`/api/server/start?server_id=${serverId}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            });
            const result = await response.json();

            if (result.success) {
                alert('Server se spouští...');
                setTimeout(updateStatus, 3000);
            } else {
                alert('Chyba při spouštění serveru!');
            }
        } catch (error) {
            console.error('Chyba:', error);
            alert('Chyba při komunikaci se serverem');
        }
    });

    // Stop serveru
    document.getElementById('stop-btn').addEventListener('click', async () => {
        if (!confirm('Opravdu chcete vypnout server? Všichni hráči budou odpojeni.')) {
            return;
        }

        try {
            const response = await fetch(`/api/server/stop?server_id=${serverId}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            });
            const result = await response.json();

            if (result.success) {
                alert('Server se vypíná...');
                setTimeout(updateStatus, 5000);
            } else {
                alert(result.error || 'Chyba při vypínání serveru!');
            }
        } catch (error) {
            console.error('Chyba:', error);
            alert('Chyba při komunikaci se serverem');
        }
    });

    // Restart serveru
    document.getElementById('restart-btn').addEventListener('click', async () => {
        if (!confirm('Opravdu chcete restartovat server? Všichni hráči budou odpojeni.')) {
            return;
        }

        try {
            const response = await fetch(`/api/server/restart?server_id=${serverId}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            });
            const result = await response.json();

            if (result.success) {
                alert('Server se restartuje...');
                setTimeout(updateStatus, 8000);
            } else {
                alert(result.error || 'Chyba při restartu serveru!');
            }
        } catch (error) {
            console.error('Chyba:', error);
            alert('Chyba při komunikaci se serverem');
        }
    });

    // Prvotní načtení stavu
    updateStatus();
    // Automatická aktualizace každých 10 sekund
    setInterval(updateStatus, 10000);
});

// ====== Automatické načítání hlavních logů (vylepšená verze) ======
let lastLogContent = "";
let lastServerStatus = "";


document.addEventListener('DOMContentLoaded', () => {
    const tabContainer = document.querySelector('.console-tabs');
    const tabContentContainer = document.getElementById('console-tab-content');
    const addButton = document.getElementById('add-log-tab');
    const logBox = document.getElementById('log-output');

    if (!tabContainer || !addButton || !logBox) {
        console.warn("Konzolová sekce nebyla nalezena na této stránce.");
        return;
    }

    // ====== Automatické načítání hlavních logů ======
    async function loadLogs() {
        const serverId = getCurrentServerId();
        const logBox = document.getElementById("log-output");
        const isAtBottom = logBox.scrollHeight - logBox.scrollTop - logBox.clientHeight < 50;

        try {
            // zjištění stavu serveru
            const statusRes = await fetch(`/api/server/status?server_id=${serverId}`);
            const statusData = await statusRes.json();

            const currentStatus = statusData.status || "unknown";
            // pokud došlo k vypnutí serveru -> smaž log
            if (currentStatus === "stopped" && lastServerStatus !== "stopped") {
                logBox.innerHTML = "";
                lastLogContent = "";
            }
            lastServerStatus = currentStatus;

            // načtení logů
            const res = await fetch(`/api/server/logs?server_id=${serverId}&lines=200`);
            const data = await res.json();
            const newLog = data.html || data.text || "";

            // aktualizuj jen pokud se obsah změnil
            if (newLog !== lastLogContent) {
                logBox.innerHTML = newLog;
                lastLogContent = newLog;
                if (isAtBottom) logBox.scrollTop = logBox.scrollHeight;
            }

        } catch (err) {
            console.error("Chyba při načítání logů:", err);
        }
    }

    // Místo pevného intervalu 3000 ms – mírně delší interval, abychom šetřili přenosy
    setInterval(loadLogs, 4000);
    loadLogs();

    // ====== Přepínání mezi záložkami ======
    tabContainer.addEventListener('click', e => {
        const tab = e.target.closest('.tab');
        if (!tab || tab.classList.contains('tab-add')) return;

        const target = tab.dataset.tab;
        document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
        document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
        tab.classList.add('active');
        document.getElementById(`tab-${target}`).classList.add('active');
    });

    // ====== PŘIDÁNÍ NOVÉ ZÁLOŽKY (výběr logu přes modální dialog) ======
    addButton.addEventListener('click', async () => {
        const serverId = getCurrentServerId();
        const response = await fetch(`/api/server/old-logs?server_id=${serverId}`);
        const logs = await response.json();

        const dialog = document.getElementById('logDialog');
        const listContainer = document.getElementById('logList');
        listContainer.innerHTML = '';

        if (!logs.length) {
            listContainer.innerHTML = '<p style="color:#ccc;text-align:center;">Žádné staré logy nebyly nalezeny.</p>';
        } else {
            logs.forEach(file => {
                const item = document.createElement('div');
                item.className = 'log-item';
                item.textContent = file;
                item.addEventListener('click', async () => {
                    await openOldLog(file, serverId);
                    dialog.classList.add('hidden');
                });
                listContainer.appendChild(item);
            });
        }

        dialog.classList.remove('hidden');
    });

    // ====== Zavření modálního dialogu ======
    document.getElementById('closeLogDialog').addEventListener('click', () => {
        document.getElementById('logDialog').classList.add('hidden');
    });

    // ====== Načtení starého logu (otevře záložku) ======
    async function openOldLog(filename, serverId) {
        const logData = await fetch(`/api/server/old-logs/view?server_id=${serverId}&filename=${encodeURIComponent(filename)}`)
            .then(r => r.json());

        const tabId = `old-${Date.now()}`;

        const tab = document.createElement('div');
        tab.className = 'tab';
        tab.dataset.tab = tabId;
        tab.innerHTML = `${filename} <span class="tab-close">✖</span>`;
        tabContainer.insertBefore(tab, addButton);

        const content = document.createElement('div');
        content.className = 'tab-content';
        content.id = `tab-${tabId}`;
        content.innerHTML = `<pre class="console-output">${logData.content}</pre>`;
        tabContentContainer.appendChild(content);

        document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
        document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
        tab.classList.add('active');
        content.classList.add('active');
    }

    // ====== Zavírání záložek ======
    tabContainer.addEventListener('click', e => {
        if (e.target.classList.contains('tab-close')) {
            const tab = e.target.closest('.tab');
            const tabId = tab.dataset.tab;
            const content = document.getElementById(`tab-${tabId}`);
            tab.remove();
            content.remove();

            // vrať se na hlavní konzoli
            document.querySelector('.tab[data-tab="main"]').classList.add('active');
            document.getElementById('tab-main').classList.add('active');
        }
    });

    // ====== Odesílání příkazů ======
    document.getElementById('sendCommand').addEventListener('click', sendCommand);
    document.getElementById('console-input').addEventListener('keypress', e => {
        if (e.key === 'Enter') sendCommand();
    });

    async function sendCommand() {
        const input = document.getElementById('console-input');
        const command = input.value.trim();
        const serverId = getCurrentServerId();
        if (!command) return;

        try {
            await fetch(`/api/server/command?server_id=${serverId}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ command })
            });
            input.value = '';
        } catch (err) {
            console.error("Chyba při odesílání příkazu:", err);
        }
    }
});


// Backup management functions
async function loadBackups() {
    const serverId = getCurrentServerId();
    try {
        const response = await fetch(`/api/server/backups?server_id=${serverId}`);
        const backups = await response.json();

        const backupList = document.getElementById('backup-list');
        backupList.innerHTML = '';

        if (backups.length === 0) {
            backupList.innerHTML = '<p>Žádné zálohy nebyly nalezeny</p>';
            return;
        }

        backups.forEach(backup => {
            const backupItem = document.createElement('div');
            backupItem.className = 'backup-item';
            backupItem.innerHTML = `
                <div class="backup-info">
                    <strong>${backup.name}</strong>
                    <div>Vytvořeno: ${backup.date}</div>
                    <div>Velikost: ${backup.size_mb} MB</div>
                </div>
                <div class="backup-actions">
                    <button class="btn btn-sm btn-success restore-btn" data-name="${backup.name}">
                        <i class="fas fa-undo"></i> Obnovit
                    </button>
                    <button class="btn btn-sm btn-danger delete-btn" data-name="${backup.name}">
                        <i class="fas fa-trash"></i> Smazat
                    </button>
                </div>
            `;
            backupList.appendChild(backupItem);
        });

        // Přidání event listenerů pro tlačítka
        document.querySelectorAll('.restore-btn').forEach(btn => {
            btn.addEventListener('click', () => restoreBackup(btn.dataset.name));
        });

        document.querySelectorAll('.delete-btn').forEach(btn => {
            btn.addEventListener('click', () => deleteBackup(btn.dataset.name));
        });
    } catch (error) {
        console.error('Chyba při načítání záloh:', error);
    }
}

// Vytvoření zálohy
async function createBackup() {
    const backupBtn = document.getElementById('create-backup-btn');
    const serverId = getCurrentServerId();
    backupBtn.disabled = true;

    try {
        const statusData = await (await fetch(`/api/server/status?server_id=${serverId}`)).json();
        if (statusData.status === 'running') {
            alert('Server musí být vypnutý pro vytvoření zálohy');
            return;
        }

        const result = await (await fetch(`/api/server/backup/create?server_id=${serverId}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                name: document.getElementById('backup-name').value.trim() || undefined
            })
        })).json();

        if (result.success) {
            await Promise.all([loadBackups(), updateDiskUsage()]);
            alert('Záloha vytvořena');
        } else {
            throw new Error(result.error || 'Neznámá chyba');
        }
    } catch (error) {
        console.error('Chyba:', error);
        alert(`Chyba: ${error.message}`);
    } finally {
        backupBtn.disabled = false;
    }
}

async function restoreBackup(backupName) {
    if (!confirm(`Opravdu chcete obnovit zálohu "${backupName}"? Současný svět bude přepsán.`)) {
        return;
    }
    const serverId = getCurrentServerId();
    try {
        const response = await fetch(`/api/server/backup/restore?server_id=${serverId}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ name: backupName })
        });

        const result = await response.json();

        if (result.success) {
            alert('Záloha byla úspěšně obnovena. Můžete spustit server.');
        } else {
            alert('Chyba při obnovování zálohy: ' + (result.error || 'Neznámá chyba'));
        }
    } catch (error) {
        console.error('Chyba:', error);
        alert('Chyba při komunikaci se serverem');
    }
}

// Mazání zálohy
async function deleteBackup(backupName) {
    const serverId = getCurrentServerId();
    if (!confirm(`Smazat zálohu "${backupName}"?`)) return;

    try {
        const result = await (await fetch(`/api/server/backup/delete?server_id=${serverId}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name: backupName })
        })).json();

        if (result.success) {
            await Promise.all([loadBackups(), updateDiskUsage()]);
            alert('Záloha smazána');
        } else {
            throw new Error(result.error || 'Neznámá chyba');
        }
    } catch (error) {
        console.error('Chyba:', error);
        alert(`Chyba: ${error.message}`);
    }
}

// Funkce pro formátování velikosti
function formatSize(bytes) {
    if (bytes === 0) return '0 B';
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(1024));
    return parseFloat((bytes / Math.pow(1024, i)).toFixed(2)) + ' ' + sizes[i];
}

async function updateDiskUsage() {
    const serverId = getCurrentServerId();
    try {
        const response = await fetch(`/api/server/disk-usage?server_id=${serverId}`);
        const data = await response.json();

        const serverBar = document.getElementById('server-usage-bar');
        const backupBar = document.getElementById('backup-usage-bar');

        serverBar.style.width = `${data.server_percent}%`;
        backupBar.style.width = `${data.backup_percent}%`;

        const usedPercent = Math.min(100, data.server_percent + data.backup_percent);
        document.documentElement.style.setProperty('--used-percent', `${usedPercent}%`);

        document.getElementById('server-usage-text').textContent =
            `${formatSize(data.server_size)} (${data.server_percent.toFixed(1)}%)`;

        document.getElementById('backup-usage-text').textContent =
            `${formatSize(data.backup_size)} (${data.backup_percent.toFixed(1)}%) - ${data.backup_count} záloh`;

        document.getElementById('total-usage-text').textContent =
            `${formatSize(data.total_size)} / ${formatSize(data.max_capacity)}`;

        document.getElementById('backup-count').textContent = data.backup_count;

        serverBar.title = `Server: ${data.server_percent.toFixed(1)}%`;
        backupBar.title = `Zálohy: ${data.backup_percent.toFixed(1)}%`;
    } catch (error) {
        console.error('Chyba při načítání využití disku:', error);
    }
}

// Přidejte volání této funkce při načtení stránky
document.addEventListener('DOMContentLoaded', function () {
    updateDiskUsage();
    setInterval(updateDiskUsage, 60000);
    loadServerInfo();
});

// Event listeners
document.getElementById('create-backup-btn').addEventListener('click', createBackup);

// Načtení záloh při startu
document.addEventListener('DOMContentLoaded', loadBackups);

async function loadAdminPanel() {
    const serverId = getCurrentServerId();
    try {
        const response = await fetch(`/api/server/admins?server_id=${serverId}`);
        const data = await response.json();

        if (data.is_owner) {
            document.getElementById('admin-management-panel').style.display = 'block';

            const list = document.getElementById('admin-list');
            list.innerHTML = '';

            data.admins.forEach(admin => {
                const li = document.createElement('li');
                li.className = 'list-group-item d-flex justify-content-between align-items-center';
                li.innerHTML = `${admin.email} <button class="btn btn-sm btn-danger" onclick="removeAdmin(${admin.user_id})">Odebrat</button>`;
                list.appendChild(li);
            });
        }
    } catch (err) {
        console.error('Chyba při načítání adminů:', err);
    }
}

document.getElementById('add-admin-btn').addEventListener('click', async () => {
    const email = document.getElementById('admin-email-input').value;
    if (!email) return alert('Zadej email admina');

    const serverId = getCurrentServerId();
    const response = await fetch(`/api/server/admins/add?server_id=${serverId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email })
    });

    const result = await response.json();
    if (result.success) {
        alert('Admin přidán');
        document.getElementById('admin-email-input').value = '';
        loadAdminPanel();
    } else {
        alert(result.message || 'Nepodařilo se přidat admina');
    }
});

async function removeAdmin(user_id) {
    if (!confirm('Opravdu chceš odebrat tohoto admina?')) return;

    const serverId = getCurrentServerId();
    const response = await fetch(`/api/server/admins/remove?server_id=${serverId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id })
    });

    const result = await response.json();
    if (result.success) {
        alert('Admin odebrán');
        loadAdminPanel();
    } else {
        alert(result.message || 'Chyba při odebírání admina');
    }
}

// server_panel.js - opravte funkci initPlayerAccessManagement
function initPlayerAccessManagement() {
    const generateBtn = document.getElementById('generate-code-btn');
    const playerAccessPanel = document.getElementById('player-access-management');

    if (!playerAccessPanel) {
        console.log('Player access management panel nebyl nalezen');
        return;
    }

    // Zkontrolovat, zda je uživatel admin
    const serverId = getCurrentServerId();
    if (!serverId) {
        console.error('Nelze inicializovat správu přístupových kódů - chybějící serverId');
        return;
    }

    checkAdminAccess(serverId).then(isAdmin => {
        if (isAdmin) {
            playerAccessPanel.style.display = 'block';

            if (generateBtn) {
                generateBtn.addEventListener('click', generateAccessCode);
                loadAccessCodes();
            }
        }
    });
}

async function generateAccessCode() {
    const serverId = getCurrentServerId();
    const expiresHours = document.getElementById('expires-hours').value;
    const maxUsesInput = document.getElementById('max-uses');
    const maxUses = maxUsesInput.value ? parseInt(maxUsesInput.value) : null;

    if (!serverId) {
        alert('Chyba: Nelze získat ID serveru');
        return;
    }

    const generateBtn = document.getElementById('generate-code-btn');
    const originalText = generateBtn.innerHTML;

    try {
        generateBtn.disabled = true;
        generateBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Generuji...';

        const response = await fetch('/api/server/player-access/generate-code', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                server_id: serverId,
                expires_hours: parseInt(expiresHours),
                max_uses: maxUses
            })
        });

        const result = await response.json();

        if (result.success) {
            const resultDiv = document.getElementById('generated-code-result');
            const expiresText = result.expires_at ?
                `Platný do: ${new Date(result.expires_at).toLocaleString('cs-CZ')}` :
                'Neomezená platnost';
            const usesText = result.max_uses ?
                `Maximální počet použití: ${result.max_uses}` :
                'Neomezený počet použití';

            resultDiv.innerHTML = `
                <strong><i class="fas fa-key"></i> Nový přístupový kód:</strong><br>
                <span style="font-size: 1.4rem; color: #28a745;">${result.code}</span><br>
                <small>${expiresText}<br>${usesText}</small>
            `;
            resultDiv.style.display = 'block';

            // Skrýt výsledek po 30 sekundách
            setTimeout(() => {
                resultDiv.style.display = 'none';
            }, 30000);

            // Resetovat formulář
            maxUsesInput.value = '';

            // Načíst aktualizovaný seznam kódů
            await loadAccessCodes();

        } else {
            throw new Error(result.error || 'Neznámá chyba při generování kódu');
        }

    } catch (error) {
        console.error('Chyba při generování kódu:', error);
        alert(`Chyba při generování kódu: ${error.message}`);
    } finally {
        generateBtn.disabled = false;
        generateBtn.innerHTML = originalText;
    }
}

async function loadAccessCodes() {
    const serverId = getCurrentServerId();

    if (!serverId) {
        console.error('Nelze načíst přístupové kódy - chybějící serverId');
        return;
    }

    try {
        const response = await fetch(`/api/server/player-access/codes?server_id=${serverId}`);

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const codes = await response.json();

        const listContainer = document.getElementById('access-codes-list');
        if (!listContainer) return;

        listContainer.innerHTML = '';

        if (codes.length === 0) {
            listContainer.innerHTML = `
                <div class="text-center text-muted py-4">
                    <i class="fas fa-key fa-2x mb-3" style="color: #6c757d;"></i>
                    <p class="mb-0">Žádné přístupové kódy</p>
                    <small>Vygenerujte první kód pomocí tlačítka výše</small>
                </div>
            `;
            return;
        }

        // Rozdělit kódy na aktivní a neaktivní
        const activeCodes = codes.filter(code => code.is_active);
        const inactiveCodes = codes.filter(code => !code.is_active);

        // Zobrazit aktivní kódy
        if (activeCodes.length > 0) {
            activeCodes.forEach(code => {
                const codeElement = createCodeElement(code, true);
                listContainer.appendChild(codeElement);
            });
        } else {
            listContainer.innerHTML += `
                <div class="text-center text-muted py-3">
                    <i class="fas fa-info-circle"></i>
                    Žádné aktivní kódy
                </div>
            `;
        }

        // Zobrazit neaktivní kódy s rozbalovací sekcí
        if (inactiveCodes.length > 0) {
            const inactiveSection = createInactiveCodesSection(inactiveCodes);
            listContainer.appendChild(inactiveSection);
        }

    } catch (error) {
        console.error('Chyba při načítání kódů:', error);
        const listContainer = document.getElementById('access-codes-list');
        if (listContainer) {
            listContainer.innerHTML = `
                <div class="alert alert-danger">
                    <i class="fas fa-exclamation-triangle"></i> 
                    Chyba při načítání přístupových kódů: ${error.message}
                </div>
            `;
        }
    }
}

// Nová funkce pro vytvoření rozbalovací sekce neaktivních kódů
function createInactiveCodesSection(inactiveCodes) {
    const section = document.createElement('div');
    section.className = 'inactive-codes-section mt-4';

    const header = document.createElement('div');
    header.className = 'inactive-codes-header';
    header.innerHTML = `
        <h6>
            <i class="fas fa-history"></i>
            Neaktivní kódy (${inactiveCodes.length})
            <i class="fas fa-chevron-down toggle-icon"></i>
        </h6>
    `;

    const content = document.createElement('div');
    content.className = 'inactive-codes-content';
    content.style.display = 'none'; // Skryté na začátku

    // Přidat neaktivní kódy do obsahu
    inactiveCodes.forEach(code => {
        const codeElement = createCodeElement(code, false);
        content.appendChild(codeElement);
    });

    // Přidat funkci rozbalení/sbalení
    header.addEventListener('click', function () {
        const isExpanded = content.style.display === 'block';
        content.style.display = isExpanded ? 'none' : 'block';
        header.classList.toggle('expanded', !isExpanded);
    });

    section.appendChild(header);
    section.appendChild(content);

    return section;
}

// Upravená funkce createCodeElement - vrátíme původní font
function createCodeElement(code, isActive) {
    const codeElement = document.createElement('div');
    codeElement.className = `access-code-item mb-2 p-3 border rounded ${isActive ? 'border-success' : 'border-secondary'}`;

    const expiresText = code.expires_at ?
        `Platný do: ${new Date(code.expires_at).toLocaleString('cs-CZ')}` :
        'Neomezená platnost';

    const usesText = code.max_uses ?
        `Použito: ${code.use_count}/${code.max_uses}` :
        `Použito: ${code.use_count}×`;

    const statusBadge = isActive ?
        '<span class="badge badge-success ml-2">Aktivní</span>' :
        '<span class="badge badge-secondary ml-2">Neaktivní</span>';

    codeElement.innerHTML = `
        <div class="d-flex justify-content-between align-items-start">
            <div class="flex-grow-1">
                <div class="d-flex align-items-center mb-1">
                    <strong class="text-primary" style="font-size: 1.1rem; font-weight: 600; letter-spacing: 1px;">${code.code}</strong>
                    ${statusBadge}
                </div>
                <div class="text-muted">
                    <div class="small">${expiresText}</div>
                    <div class="small">${usesText} • Vytvořen: ${new Date(code.created_at).toLocaleString('cs-CZ')}</div>
                </div>
            </div>
            ${isActive ? `
            <button class="btn btn-sm revoke-code-btn ml-3" data-code-id="${code.id}" title="Zrušit platnost kódu">
                <i class="fas fa-ban"></i> Zrušit
            </button>
            ` : ''}
        </div>
    `;

    // Přidat event listener pro aktivní kódy
    if (isActive) {
        const revokeBtn = codeElement.querySelector('.revoke-code-btn');
        revokeBtn.addEventListener('click', function () {
            const codeId = this.dataset.codeId;
            revokeAccessCode(codeId);
        });
    }

    return codeElement;
}

// Pomocná funkce pro vytvoření elementu kódu
function createCodeElement(code, isActive) {
    const codeElement = document.createElement('div');
    codeElement.className = `access-code-item mb-2 p-3 border rounded ${isActive ? 'border-primary' : 'border-secondary'}`;
    codeElement.style.opacity = isActive ? '1' : '0.6';

    const expiresText = code.expires_at ?
        `Platný do: ${new Date(code.expires_at).toLocaleString('cs-CZ')}` :
        'Neomezená platnost';

    const usesText = code.max_uses ?
        `Použito: ${code.use_count}/${code.max_uses}` :
        `Použito: ${code.use_count}×`;

    const statusBadge = isActive ?
        '<span class="badge badge-success ml-2">Aktivní</span>' :
        '<span class="badge badge-secondary ml-2">Neaktivní</span>';

    codeElement.innerHTML = `
        <div class="d-flex justify-content-between align-items-center">
            <div class="flex-grow-1">
                <div class="d-flex align-items-center mb-1">
                    <strong class="text-primary font-monospace" style="font-size: 1.1rem;">${code.code}</strong>
                    ${statusBadge}
                </div>
                <div class="text-muted small">
                    <div>${expiresText}</div>
                    <div>${usesText} • Vytvořen: ${new Date(code.created_at).toLocaleString('cs-CZ')}</div>
                </div>
            </div>
            ${isActive ? `
            <button class="btn btn-sm revoke-code-btn ml-3" data-code-id="${code.id}">
                <i class="fas fa-ban"></i> Zrušit
            </button>
            ` : ''}
        </div>
    `;

    // Přidat event listener pro aktivní kódy
    if (isActive) {
        const revokeBtn = codeElement.querySelector('.revoke-code-btn');
        revokeBtn.addEventListener('click', function () {
            const codeId = this.dataset.codeId;
            revokeAccessCode(codeId);
        });
    }

    return codeElement;
}

// server_panel.js - vylepšete funkci revokeAccessCode
async function revokeAccessCode(codeId) {
    if (!codeId) {
        console.error('Chybějící codeId pro zrušení kódu');
        return;
    }

    // Najdeme kód v seznamu pro zobrazení informace
    const codeElement = document.querySelector(`.revoke-code-btn[data-code-id="${codeId}"]`);
    const codeText = codeElement ? codeElement.closest('.access-code-item').querySelector('.text-primary').textContent : 'kód';

    if (!confirm(`Opravdu chcete zrušit přístupový kód "${codeText}"?\n\nTato akce je nevratná a kód již nebude možné použít.`)) {
        return;
    }

    const originalButton = codeElement;
    const originalHtml = originalButton.innerHTML;

    try {
        originalButton.disabled = true;
        originalButton.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';

        const response = await fetch('/api/server/player-access/revoke-code', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ code_id: parseInt(codeId) })
        });

        const result = await response.json();

        if (result.success) {
            // Zobrazit potvrzení
            showMessage('success', `Přístupový kód "${codeText}" byl úspěšně zrušen`);

            // Načíst aktualizovaný seznam kódů
            await loadAccessCodes();

        } else {
            throw new Error(result.error || 'Neznámá chyba při rušení kódu');
        }

    } catch (error) {
        console.error('Chyba při rušení kódu:', error);
        showMessage('error', `Chyba při rušení kódu: ${error.message}`);

        // Obnovit tlačítko
        originalButton.disabled = false;
        originalButton.innerHTML = originalHtml;
    }
}

// Pomocná funkce pro zobrazení zpráv
function showMessage(type, text) {
    const resultDiv = document.getElementById('generated-code-result');
    const icon = type === 'success' ? 'fa-check' : 'fa-times';
    const alertClass = type === 'success' ? 'alert-success' : 'alert-danger';

    resultDiv.innerHTML = `<i class="fas ${icon}"></i> ${text}`;
    resultDiv.className = `alert ${alertClass}`;
    resultDiv.style.display = 'block';

    // Skrýt zprávu po 5 sekundách
    setTimeout(() => {
        resultDiv.style.display = 'none';
    }, 5000);
}

// Volání v DOMContentLoaded
document.addEventListener('DOMContentLoaded', function () {
    // ... existující kód ...
    initPlayerAccessManagement();
});

document.addEventListener('DOMContentLoaded', loadAdminPanel);

async function loadQuickViewPlugins() {
    const serverId = getCurrentServerId();
    try {
        const response = await fetch(`/api/plugins/installed?server_id=${serverId}`);

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const result = await response.json();

        // Ošetření případu, kdy API vrátí chybu místo pole pluginů
        if (!Array.isArray(result)) {
            if (result.error) {
                throw new Error(result.error);
            }
            throw new Error('Neplatná odpověď ze serveru');
        }

        const plugins = result;
        const list = document.getElementById('installed-plugins-quickview');
        if (!list) return;

        list.innerHTML = '';

        if (plugins.length === 0) {
            list.innerHTML = '<div class="quickview-plugin-item">Žádné pluginy</div>';
            return;
        }

        // Zobrazíme pouze prvních 5 pluginů
        plugins.slice(0, 5).forEach(plugin => {
            const pluginItem = document.createElement('div');
            pluginItem.className = 'quickview-plugin-item';
            pluginItem.innerHTML = `
                <span class="quickview-plugin-name">${plugin.display_name || plugin.name}</span>
                <span class="quickview-plugin-version">v${plugin.version}</span>
            `;
            list.appendChild(pluginItem);
        });

        // Pokud je pluginů více než 5, zobrazíme počítadlo
        if (plugins.length > 5) {
            const moreItem = document.createElement('div');
            moreItem.className = 'quickview-plugin-item';
            moreItem.innerHTML = `
                <span>+ ${plugins.length - 5} dalších</span>
            `;
            list.appendChild(moreItem);
        }
    } catch (error) {
        console.error('Chyba při načítání pluginů:', error);
        const list = document.getElementById('installed-plugins-quickview');
        if (list) {
            list.innerHTML = `
                <div class="quickview-plugin-item error">
                    <i class="fas fa-exclamation-triangle"></i>
                    Chyba při načítání pluginů: ${error.message}
                </div>
            `;
        }
    }
}


async function loadInstalledModsQuickview() {
    try {
        const response = await fetch(`/api/mods/installed?server_id=${getCurrentServerId()}`);

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const result = await response.json();

        // Ošetření případu, kdy API vrátí chybu místo pole modů
        if (!Array.isArray(result)) {
            if (result.error) {
                throw new Error(result.error);
            }
            throw new Error('Neplatná odpověď ze serveru');
        }

        const mods = result;
        const list = document.getElementById('installed-mods-quickview');
        if (!list) return;

        list.innerHTML = '';

        if (mods.length === 0) {
            list.innerHTML = `
                <div class="no-mods">
                    <i class="fas fa-box-open"></i>
                    <p>Žádné módy nenalezeny</p>
                </div>
            `;
            return;
        }

        // Zobrazíme pouze prvních 5 modů pro rychlý náhled
        const displayMods = mods.slice(0, 5);

        displayMods.forEach(mod => {
            const modItem = document.createElement('div');
            modItem.className = 'quickview-mod-item';
            modItem.innerHTML = `
                <span class="quickview-mod-name">${mod.display_name || mod.name}</span>
                <span class="quickview-mod-version">${mod.version}</span>
            `;
            list.appendChild(modItem);
        });

        // Pokud je více než 5 modů, zobrazíme indikátor
        if (mods.length > 5) {
            const moreItem = document.createElement('div');
            moreItem.className = 'quickview-mod-item';
            moreItem.innerHTML = `
                <span class="quickview-mod-name">+ ${mods.length - 5} dalších modů</span>
                <span class="quickview-mod-version">...</span>
            `;
            moreItem.style.opacity = '0.7';
            moreItem.style.fontStyle = 'italic';
            list.appendChild(moreItem);
        }

    } catch (error) {
        console.error('Chyba při načítání modů:', error);
        const list = document.getElementById('installed-mods-quickview');
        if (list) {
            list.innerHTML = `
                <div class="no-mods">
                    <i class="fas fa-exclamation-triangle"></i>
                    <p>Chyba při načítání modů: ${error.message}</p>
                </div>
            `;
        }
    }
}

document.addEventListener('DOMContentLoaded', function () {
    // ... existující kód ...

    // Přesměrování na správu modů/pluginů
    document.getElementById('manage-mods-btn').addEventListener('click', () => {
        window.location.href = `/server/${getCurrentServerId()}/mods`;
    });

    document.getElementById('manage-plugins-btn').addEventListener('click', () => {
        window.location.href = `/server/${getCurrentServerId()}/plugins`;
    });
});

// Inicializace nástrojů pro klienta (sjednocená verze)
function initClientTools(serverId) {
    const container = document.getElementById('client-tools-container');
    if (!container) {
        console.warn('Container #client-tools-container nebyl nalezen');
        return;
    }

    // Vyčistit kontejner
    container.innerHTML = '';

    const tools = [
        {
            id: 'client-pack',
            icon: 'fa-file-archive',
            title: 'Klientský balíček modů',
            description: 'Stáhněte si všechny módy, které potřebujete pro připojení k tomuto serveru. Balíček obsahuje kompletní sadu modů ve správných verzích.',
            buttonText: 'Stáhnout ZIP',
            buttonClass: 'btn-success',
            onClick: async function () {
                const statusElement = document.getElementById(`${this.id}-status`);
                const originalText = this.buttonElement.textContent;

                try {
                    statusElement.textContent = 'Připravuji ZIP balíček...';
                    statusElement.className = 'tool-status info';
                    this.buttonElement.disabled = true;
                    this.buttonElement.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Připravuji...';

                    const response = await fetch(`/api/mods/client-pack/download?server_id=${serverId}`);
                    if (!response.ok) throw new Error(`HTTP ${response.status}: ${response.statusText}`);

                    const blob = await response.blob();
                    if (blob.size === 0) throw new Error('Obdržen prázdný soubor');

                    // Vytvoření a stažení souboru
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = `${serverId}_client_mods.zip`;
                    document.body.appendChild(a);
                    a.click();
                    document.body.removeChild(a);
                    URL.revokeObjectURL(url);

                    statusElement.textContent = `ZIP balíček úspěšně stažen (${(blob.size / 1024 / 1024).toFixed(2)} MB)`;
                    statusElement.className = 'tool-status success';

                } catch (error) {
                    console.error('Chyba při stahování klientského balíčku:', error);
                    statusElement.textContent = `Chyba při stahování: ${error.message}`;
                    statusElement.className = 'tool-status error';
                } finally {
                    this.buttonElement.disabled = false;
                    this.buttonElement.innerHTML = originalText;

                    // Automaticky skrýt status zprávu po 10 sekundách
                    setTimeout(() => {
                        statusElement.textContent = '';
                        statusElement.className = 'tool-status';
                    }, 10000);
                }
            }
        },
        {
            id: 'modpacks',
            icon: 'fa-cubes',
            title: 'Modpacky serveru',
            description: 'Vyberte si z modpacků vytvořených administrátory serveru. Každý modpack obsahuje pečlivě vybrané módy pro specifické herní zážitky.',
            buttonText: 'Zobrazit modpacky',
            buttonClass: 'btn-info',
            onClick: async function () {
                await showModpacksSelection(serverId);
            }
        }
    ];

    // Vykreslení karet nástrojů
    tools.forEach(tool => {
        const card = document.createElement('div');
        card.className = 'tool-card';
        card.innerHTML = `
            <h5><i class="fas ${tool.icon}"></i> ${tool.title}</h5>
            <p>${tool.description}</p>
            <button class="btn ${tool.buttonClass}" id="tool-btn-${tool.id}">
                ${tool.buttonText}
            </button>
            <div id="${tool.id}-status" class="tool-status"></div>
        `;
        container.appendChild(card);

        const button = document.getElementById(`tool-btn-${tool.id}`);
        tool.buttonElement = button;
        button.addEventListener('click', tool.onClick.bind(tool));
    });

    console.log(`Client tools initialized for server ${serverId}`);
}

/* ================================
   MODPACK SELECTION MODAL
================================ */
async function showModpacksSelection(serverId) {
    try {
        const response = await fetch(`/api/modpacks/list?server_id=${serverId}`);
        if (!response.ok) throw new Error('Chyba při načítání modpacků');

        const modpacks = await response.json();

        if (modpacks.length === 0) {
            alert('Pro tento server nejsou k dispozici žádné modpacky.');
            return;
        }

        // Modální okno
        const modal = document.createElement('div');
        modal.className = 'modpack-selection-modal';
        modal.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.5);
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 1000;
        `;

        modal.innerHTML = `
            <div style="background: white; padding: 2rem; border-radius: 8px; max-width: 600px; width: 90%; max-height: 80vh; overflow-y: auto;">
                <h4><i class="fas fa-cubes"></i> Vyberte modpack ke stažení</h4>
                <div class="modpacks-selection-list">
                    ${modpacks.map(pack => `
                        <div class="modpack-tool-card">
                            <h5>${pack.name}</h5>
                            ${pack.description ? `<p>${pack.description}</p>` : ''}
                            <div class="modpack-tool-stats">
                                <span><i class="fas fa-cube"></i> ${pack.mod_count} módů</span>
                                <span><i class="fas fa-download"></i> ${pack.download_count} stažení</span>
                                <span><i class="fas fa-hdd"></i> ${formatSize(pack.file_size)}</span>
                            </div>
                            <button class="btn btn-success download-modpack-selection" data-pack-id="${pack.id}">
                                <i class="fas fa-download"></i> Stáhnout tento modpack
                            </button>
                        </div>
                    `).join('')}
                    <div style="text-align: center; margin-top: 1rem;">
                        <button class="btn btn-danger" id="close-modpack-selection" 
                            style="background: linear-gradient(135deg, #e74c3c, #c0392f); color: white; border: none; padding: 0.5rem 1.5rem; border-radius: 6px; font-weight: 600;">
                            Zavřít
                        </button>
                    </div>
    </div>
`;

        document.body.appendChild(modal);

        // Zavření
        modal.querySelector('#close-modpack-selection').addEventListener('click', () => {
            document.body.removeChild(modal);
        });

        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                document.body.removeChild(modal);
            }
        });

        // Stahování vybraného modpacku
        modal.querySelectorAll('.download-modpack-selection').forEach(btn => {
            btn.addEventListener('click', async (e) => {
                const packId = e.target.closest('.download-modpack-selection').dataset.packId;
                document.body.removeChild(modal);
                await downloadModpack(packId);
            });
        });

    } catch (error) {
        console.error('Chyba při načítání modpacků:', error);
        alert('Chyba při načítání modpacků.');
    }
}

/* ================================
   Pomocné funkce
================================ */
function formatSize(bytes) {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / 1024 / 1024).toFixed(2)} MB`;
}

async function downloadModpack(packId) {
    try {
        const response = await fetch(`/api/modpacks/download?id=${packId}`);
        if (!response.ok) throw new Error(`HTTP ${response.status}: ${response.statusText}`);

        const blob = await response.blob();
        if (blob.size === 0) throw new Error('Obdržen prázdný soubor');

        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `modpack_${packId}.zip`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);

    } catch (error) {
        console.error('Chyba při stahování modpacku:', error);
        alert('Nepodařilo se stáhnout modpack.');
    }
}



// Inicializace správy modpacků
async function initModpacksManagement() {
    const serverId = getCurrentServerId();

    try {
        await loadAvailableMods();
        await loadModpacksList();
        setupModpacksEventListeners();
        setupExpandableSections(); // Inicializace rozbalovacích sekcí
        console.log('Modpacks management initialized for server', serverId);
    } catch (error) {
        console.error('Chyba při inicializaci modpacků:', error);
    }
}




// Načtení dostupných módů pro checkboxy
async function loadAvailableMods() {
    const serverId = getCurrentServerId();
    try {
        const response = await fetch(`/api/mods/installed?server_id=${serverId}`);
        if (!response.ok) throw new Error('Chyba při načítání módů');

        const mods = await response.json();
        const checklist = document.getElementById('mods-checklist');
        if (!checklist) {
            console.warn('Element #mods-checklist nebyl nalezen');
            return;
        }

        checklist.innerHTML = '';

        if (mods.length === 0) {
            checklist.innerHTML = '<div class="text-muted">Na serveru nejsou nainstalovány žádné módy</div>';
            return;
        }

        mods.forEach(mod => {
            const modItem = document.createElement('div');
            modItem.className = 'mod-checkbox-item';
            modItem.innerHTML = `
                <input type="checkbox" id="mod-${mod.id}" value="${mod.id}" class="mod-checkbox">
                <div class="mod-info">
                    <span class="mod-name">${mod.display_name}</span>
                    <span class="mod-version">v${mod.version}</span>
                    ${mod.description ? `<div class="mod-description">${mod.description}</div>` : ''}
                </div>
            `;
            checklist.appendChild(modItem);
        });

    } catch (error) {
        console.error('Chyba při načítání módů:', error);
        const checklist = document.getElementById('mods-checklist');
        if (checklist) {
            checklist.innerHTML = '<div class="text-danger">Chyba při načítání módů</div>';
        }
    }
}

// Inicializace rozbalovacích sekcí
function setupExpandableSections() {
    const sectionHeaders = document.querySelectorAll('.section-header');

    sectionHeaders.forEach(header => {
        header.addEventListener('click', function () {
            const section = this.dataset.section;
            const content = document.getElementById(`${section}-content`);
            const icon = this.querySelector('.toggle-icon');

            if (content.style.display === 'none') {
                content.style.display = 'block';
                this.classList.add('expanded');
            } else {
                content.style.display = 'none';
                this.classList.remove('expanded');
            }
        });
    });
}

// Upravené načtení seznamu modpacků s editací
async function loadModpacksList() {
    const serverId = getCurrentServerId();
    try {
        const response = await fetch(`/api/modpacks/list?server_id=${serverId}`);
        if (!response.ok) throw new Error('Chyba při načítání modpacků');

        const modpacks = await response.json();
        currentModpacks = modpacks;
        const listContainer = document.getElementById('modpacks-list');

        if (!listContainer) {
            console.warn('Element #modpacks-list nebyl nalezen');
            return;
        }

        if (modpacks.length === 0) {
            listContainer.innerHTML = '<div class="text-muted">Zatím nebyly vytvořeny žádné modpacky</div>';
            return;
        }

        listContainer.innerHTML = '';
        modpacks.forEach(pack => {
            const packElement = document.createElement('div');
            packElement.className = 'modpack-item';
            packElement.id = `modpack-${pack.id}`;
            packElement.innerHTML = `
                <div class="modpack-header">
                    <div>
                        <h5 class="modpack-title">${pack.name}</h5>
                        <div class="modpack-meta">
                            Vytvořil ${pack.author} • ${pack.created_at}
                        </div>
                    </div>
                    <div class="modpack-actions">
                        <button class="btn btn-sm btn-primary edit-modpack-btn" data-pack-id="${pack.id}">
                            <i class="fas fa-edit"></i> Upravit
                        </button>
                        <button class="btn btn-sm btn-danger delete-modpack-btn" data-pack-id="${pack.id}">
                            <i class="fas fa-trash"></i> Smazat
                        </button>
                    </div>
                </div>
                ${pack.description ? `<div class="modpack-description">${pack.description}</div>` : ''}
                <div class="modpack-stats">
                    <span class="modpack-stat">
                        <i class="fas fa-cube"></i> ${pack.mod_count} módů
                    </span>
                    <span class="modpack-stat">
                        <i class="fas fa-download"></i> ${pack.download_count} stažení
                    </span>
                    <span class="modpack-stat">
                        <i class="fas fa-hdd"></i> ${formatSize(pack.file_size)}
                    </span>
                </div>
                <div class="modpack-mods-preview">
                    <h6>Obsažené módy:</h6>
                    <div class="mods-preview-list">
                        ${pack.mods.slice(0, 8).map(mod =>
                `<span class="mod-badge">${mod.name} v${mod.version}</span>`
            ).join('')}
                        ${pack.mods.length > 8 ? `<span class="mod-badge">+${pack.mods.length - 8} dalších</span>` : ''}
                    </div>
                </div>
                <div id="edit-form-${pack.id}" class="edit-modpack-form" style="display: none;">
                    <!-- Editovací formulář se načte dynamicky -->
                </div>
            `;
            listContainer.appendChild(packElement);
        });

    } catch (error) {
        console.error('Chyba při načítání modpacků:', error);
        const listContainer = document.getElementById('modpacks-list');
        if (listContainer) {
            listContainer.innerHTML = '<div class="text-danger">Chyba při načítání modpacků</div>';
        }
    }
}

// Upravené event listenery s editací
function setupModpacksEventListeners() {
    // Vytvoření modpacku
    const createBtn = document.getElementById('create-modpack-btn');
    if (createBtn) {
        createBtn.addEventListener('click', createModpack);
    }

    // Delegované event listenery pro seznam modpacků
    const modpacksList = document.getElementById('modpacks-list');
    if (modpacksList) {
        modpacksList.addEventListener('click', function (e) {
            // Editace modpacku
            if (e.target.closest('.edit-modpack-btn')) {
                const packId = e.target.closest('.edit-modpack-btn').dataset.packId;
                toggleEditModpack(packId);
            }

            // Smazat modpack
            if (e.target.closest('.delete-modpack-btn')) {
                const packId = e.target.closest('.delete-modpack-btn').dataset.packId;
                deleteModpack(packId);
            }

            // Uložení editace
            if (e.target.closest('.save-edit-btn')) {
                const packId = e.target.closest('.save-edit-btn').dataset.packId;
                saveModpackEdit(packId);
            }

            // Zrušení editace
            if (e.target.closest('.cancel-edit-btn')) {
                const packId = e.target.closest('.cancel-edit-btn').dataset.packId;
                cancelModpackEdit(packId);
            }
        });
    }
}

// Vytvoření nového modpacku
async function createModpack() {
    const serverId = getCurrentServerId();
    const nameInput = document.getElementById('modpack-name');
    const descriptionInput = document.getElementById('modpack-description');

    if (!nameInput || !descriptionInput) {
        alert('Formulář pro vytváření modpacků není k dispozici');
        return;
    }

    const name = nameInput.value.trim();
    const description = descriptionInput.value.trim();

    if (!name) {
        alert('Zadejte název modpacku');
        return;
    }

    // Získat vybrané módy
    const selectedMods = Array.from(document.querySelectorAll('.mod-checkbox:checked'))
        .map(checkbox => parseInt(checkbox.value));

    if (selectedMods.length === 0) {
        alert('Vyberte alespoň jeden mód pro modpack');
        return;
    }

    const createBtn = document.getElementById('create-modpack-btn');
    const originalText = createBtn.innerHTML;

    try {
        createBtn.disabled = true;
        createBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Vytvářím...';

        const response = await fetch('/api/modpacks/create', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                server_id: serverId,
                name: name,
                description: description,
                mod_ids: selectedMods
            })
        });

        const result = await response.json();

        if (result.success) {
            alert(`Modpack "${name}" byl úspěšně vytvořen!`);
            // Resetovat formulář
            nameInput.value = '';
            descriptionInput.value = '';
            document.querySelectorAll('.mod-checkbox').forEach(cb => cb.checked = false);
            // Načíst aktualizovaný seznam
            await loadModpacksList();
        } else {
            throw new Error(result.error || 'Neznámá chyba');
        }

    } catch (error) {
        console.error('Chyba při vytváření modpacku:', error);
        alert(`Chyba: ${error.message}`);
    } finally {
        createBtn.disabled = false;
        createBtn.innerHTML = originalText;
    }
}


// Přepnutí do režimu editace modpacku
async function toggleEditModpack(packId) {
    const packElement = document.getElementById(`modpack-${packId}`);
    const editForm = document.getElementById(`edit-form-${packId}`);

    if (!packElement || !editForm) return;

    // Pokud už je v režimu editace, zrušit
    if (packElement.classList.contains('modpack-editing')) {
        cancelModpackEdit(packId);
        return;
    }

    try {
        // Načíst data modpacku
        const pack = currentModpacks.find(p => p.id == packId);
        if (!pack) return;

        // Načíst dostupné módy pro checkboxy
        const availableMods = await loadModsForEditing();

        // Vytvořit editovací formulář
        editForm.innerHTML = `
            <h5><i class="fas fa-edit"></i> Úprava modpacku</h5>
            <div class="form-group">
                <label for="edit-name-${packId}">Název:</label>
                <input type="text" id="edit-name-${packId}" class="form-control" value="${pack.name}">
            </div>
            <div class="form-group">
                <label for="edit-description-${packId}">Popis:</label>
                <textarea id="edit-description-${packId}" class="form-control" rows="2">${pack.description || ''}</textarea>
            </div>
            <div class="form-group">
                <label>Vyberte módy:</label>
                <div class="mods-edit-checklist" id="edit-mods-${packId}">
                    ${availableMods.map(mod => `
                        <div class="mod-checkbox-item">
                            <input type="checkbox" id="edit-mod-${mod.id}-${packId}" 
                                   value="${mod.id}" ${pack.mods.some(m => m.id === mod.id) ? 'checked' : ''}
                                   class="mod-checkbox">
                            <div class="mod-info">
                                <span class="mod-name">${mod.display_name}</span>
                                <span class="mod-version">v${mod.version}</span>
                                ${mod.description ? `<div class="mod-description">${mod.description}</div>` : ''}
                            </div>
                        </div>
                    `).join('')}
                </div>
            </div>
            <div class="modpack-edit-actions">
                <button class="btn btn-success save-edit-btn" data-pack-id="${packId}">
                    <i class="fas fa-save"></i> Uložit změny
                </button>
                <button class="btn btn-secondary cancel-edit-btn" data-pack-id="${packId}">
                    <i class="fas fa-times"></i> Zrušit
                </button>
            </div>
        `;

        // Zobrazit editovací formulář
        editForm.style.display = 'block';
        packElement.classList.add('modpack-editing');

        // Skrýt hlavní akce během editace
        const actions = packElement.querySelector('.modpack-actions');
        if (actions) {
            actions.style.opacity = '0.5';
            actions.style.pointerEvents = 'none';
        }

    } catch (error) {
        console.error('Chyba při přípravě editace:', error);
        alert('Chyba při přípravě editace modpacku');
    }
}

// Načtení módů pro editaci
async function loadModsForEditing() {
    const serverId = getCurrentServerId();
    try {
        const response = await fetch(`/api/mods/installed?server_id=${serverId}`);
        if (!response.ok) throw new Error('Chyba při načítání módů');
        return await response.json();
    } catch (error) {
        console.error('Chyba při načítání módů pro editaci:', error);
        return [];
    }
}

// Uložení změn modpacku
async function saveModpackEdit(packId) {
    const nameInput = document.getElementById(`edit-name-${packId}`);
    const descriptionInput = document.getElementById(`edit-description-${packId}`);

    if (!nameInput) return;

    const name = nameInput.value.trim();
    const description = descriptionInput.value.trim();

    if (!name) {
        alert('Zadejte název modpacku');
        return;
    }

    // Získat vybrané módy
    const selectedMods = Array.from(document.querySelectorAll(`#edit-mods-${packId} .mod-checkbox:checked`))
        .map(checkbox => parseInt(checkbox.value));

    if (selectedMods.length === 0) {
        alert('Vyberte alespoň jeden mód pro modpack');
        return;
    }

    const saveBtn = document.querySelector(`.save-edit-btn[data-pack-id="${packId}"]`);
    const originalText = saveBtn.innerHTML;

    try {
        saveBtn.disabled = true;
        saveBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Ukládám...';

        const response = await fetch(`/api/modpacks/update/${packId}`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                name: name,
                description: description,
                mod_ids: selectedMods
            })
        });

        const result = await response.json();

        if (result.success) {
            alert('Modpack byl úspěšně aktualizován!');
            await loadModpacksList(); // Znovu načíst seznam
        } else {
            throw new Error(result.error || 'Neznámá chyba');
        }

    } catch (error) {
        console.error('Chyba při ukládání změn:', error);
        alert(`Chyba: ${error.message}`);
    } finally {
        saveBtn.disabled = false;
        saveBtn.innerHTML = originalText;
    }
}

// Zrušení editace
function cancelModpackEdit(packId) {
    const packElement = document.getElementById(`modpack-${packId}`);
    const editForm = document.getElementById(`edit-form-${packId}`);

    if (packElement && editForm) {
        packElement.classList.remove('modpack-editing');
        editForm.style.display = 'none';

        // Obnovit hlavní akce
        const actions = packElement.querySelector('.modpack-actions');
        if (actions) {
            actions.style.opacity = '1';
            actions.style.pointerEvents = 'auto';
        }
    }
}

// Smazání modpacku
async function deleteModpack(packId) {
    const pack = currentModpacks.find(p => p.id == packId);
    if (!pack) return;

    if (!confirm(`Opravdu chcete smazat modpack "${pack.name}"?`)) {
        return;
    }

    try {
        const response = await fetch(`/api/modpacks/delete/${packId}`, {
            method: 'DELETE'
        });

        const result = await response.json();

        if (result.success) {
            alert('Modpack byl smazán');
            await loadModpacksList();
        } else {
            throw new Error(result.error || 'Neznámá chyba');
        }

    } catch (error) {
        console.error('Chyba při mazání modpacku:', error);
        alert(`Chyba: ${error.message}`);
    }
}

// ===============================
//   INFORMACE PRO HRÁČE – MODUL
// ===============================

let currentNotices = [];

// Inicializace informační sekce
async function initPlayerInfoSection() {
    const serverId = getCurrentServerId();

    if (!serverId) {
        console.error('Nelze inicializovat player info sekci - chybějící serverId');
        return;
    }

    await loadNotices();
    setupNoticesEventListeners();
    initTextTools(); // toolbar pro vytváření oznámení

    // Zkontrolovat admin přístup pouze pokud máme serverId
    if (serverId) {
        await checkAdminAccessForNotices(serverId);
    }
}

// Nová pomocná funkce pro kontrolu admin přístupu pro oznámení
async function checkAdminAccessForNotices(serverId) {
    try {
        const response = await fetch(`/api/server/admins?server_id=${serverId}`);

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        const panel = document.getElementById('notice-management-panel');

        if (panel && data.is_owner) {
            panel.style.display = 'block';
        }
    } catch (err) {
        console.error('Chyba při kontrole práv pro oznámení:', err);
    }
}


// ===============================
//       NAČÍTÁNÍ OZNÁMENÍ
// ===============================
async function loadNotices() {
    const serverId = getCurrentServerId();
    try {
        const response = await fetch(`/api/notices?server_id=${serverId}`);
        if (!response.ok) throw new Error('Chyba při načítání oznámení');

        const notices = await response.json();
        currentNotices = notices;

        const container = document.getElementById('notices-container');
        if (!container) return;

        if (notices.length === 0) {
            container.innerHTML = '<div class="text-muted">Žádná oznámení</div>';
            return;
        }

        container.innerHTML = '';
        notices.forEach(notice => {
            const noticeElement = document.createElement('div');
            noticeElement.className = `notice-item ${notice.type} ${notice.is_pinned ? 'pinned' : ''}`;
            noticeElement.setAttribute('data-notice-id', notice.id);

            noticeElement.innerHTML = `
                <div class="notice-header">
                    <div>
                        <h5 class="notice-title">
                            ${notice.is_pinned ? '<i class="fas fa-thumbtack"></i>' : ''}
                            ${notice.title}
                            <span class="notice-badge badge-${notice.type}">
                                ${getNoticeTypeLabel(notice.type)}
                            </span>
                            ${!notice.is_active ? '<span class="badge badge-secondary">Skryté</span>' : ''}
                        </h5>
                        <div class="notice-meta">
                            ${notice.author} • ${notice.created_at}
                            ${notice.updated_at ? ` (upraveno ${notice.updated_at})` : ''}
                        </div>
                    </div>
                </div>
                <div class="notice-content formatted">
                    ${formatNoticeContent(notice.content)}
                </div>
                ${notice.can_edit ? `
                    <div class="notice-actions">
                        <button class="btn btn-sm btn-primary edit-notice-btn" data-notice-id="${notice.id}">
                            <i class="fas fa-edit"></i> Upravit
                        </button>
                        <button class="btn btn-sm btn-danger delete-notice-btn" data-notice-id="${notice.id}">
                            <i class="fas fa-trash"></i> Smazat
                        </button>
                        <button class="btn btn-sm btn-secondary toggle-notice-btn" 
                                data-notice-id="${notice.id}" 
                                data-active="${notice.is_active}">
                            <i class="fas ${notice.is_active ? 'fa-eye-slash' : 'fa-eye'}"></i> 
                            ${notice.is_active ? 'Skrýt' : 'Zobrazit'}
                        </button>
                    </div>
                ` : ''}
            `;
            container.appendChild(noticeElement);
        });
    } catch (error) {
        console.error('Chyba při načítání oznámení:', error);
        const container = document.getElementById('notices-container');
        if (container) {
            container.innerHTML = '<div class="text-danger">Chyba při načítání oznámení</div>';
        }
    }
}


// ===============================
//        TEXTOVÉ NÁSTROJE
// ===============================
function initTextTools() {
    const toolbar = document.querySelector('.text-toolbar');
    if (!toolbar) return;

    toolbar.addEventListener('click', function (e) {
        const btn = e.target.closest('.text-tool-btn');
        if (!btn) return;

        const tag = btn.dataset.tag;
        const textarea = document.getElementById('notice-content');
        if (textarea) applyTextFormatting(tag, textarea);
    });
}

function applyTextFormatting(tag, textarea) {
    const start = textarea.selectionStart;
    const end = textarea.selectionEnd;
    const selected = textarea.value.substring(start, end);

    const formats = {
        'bold': { prefix: '**', suffix: '**', placeholder: 'tučný text' },
        'italic': { prefix: '*', suffix: '*', placeholder: 'kurzíva' },
        'underline': { prefix: '<u>', suffix: '</u>', placeholder: 'podtržený text' },
        'code': { prefix: '`', suffix: '`', placeholder: 'kód' },
        'link': { prefix: '[', suffix: '](https://example.com)', placeholder: 'odkaz' },
        'list-ul': { prefix: '- ', suffix: '', placeholder: 'položka seznamu' },
        'list-ol': { prefix: '1. ', suffix: '', placeholder: 'položka seznamu' }
    };

    const fmt = formats[tag];
    if (!fmt) return;

    const newText = fmt.prefix + (selected || fmt.placeholder) + fmt.suffix;
    textarea.value = textarea.value.substring(0, start) + newText + textarea.value.substring(end);

    const cursorPos = start + fmt.prefix.length;
    if (!selected) {
        textarea.setSelectionRange(cursorPos, cursorPos + fmt.placeholder.length);
    } else {
        textarea.setSelectionRange(cursorPos + selected.length + fmt.suffix.length, cursorPos + selected.length + fmt.suffix.length);
    }

    textarea.focus();
}


// ===============================
//     FORMÁTOVÁNÍ TEXTU
// ===============================
function formatNoticeContent(text) {
    if (!text) return '';

    return text
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.*?)\*/g, '<em>$1</em>')
        .replace(/<u>(.*?)<\/u>/g, '<u>$1</u>')
        .replace(/`(.*?)`/g, '<code>$1</code>')
        .replace(/\[(.*?)\]\((.*?)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>')
        .replace(/^[-*] (.*)$/gm, '<li>$1</li>')
        .replace(/(<li>.*<\/li>)/gs, '<ul>$1</ul>')
        .replace(/^\d+\. (.*)$/gm, '<li>$1</li>')
        .replace(/(<li>.*<\/li>)/gs, '<ol>$1</ol>')
        .replace(/\n/g, '<br>');
}


// ===============================
//        SPRÁVA OZNÁMENÍ
// ===============================
function setupNoticesEventListeners() {
    const createBtn = document.getElementById('create-notice-btn');
    if (createBtn) createBtn.addEventListener('click', createNotice);

    const noticesContainer = document.getElementById('notices-container');
    if (!noticesContainer) return;

    noticesContainer.addEventListener('click', async (e) => {
        const noticeId = e.target.closest('[data-notice-id]')?.dataset.noticeId;
        if (!noticeId) return;

        if (e.target.closest('.edit-notice-btn')) editNotice(noticeId);
        if (e.target.closest('.delete-notice-btn')) deleteNotice(noticeId);
        if (e.target.closest('.toggle-notice-btn')) {
            const isActive = e.target.closest('.toggle-notice-btn').dataset.active === 'true';
            toggleNotice(noticeId, !isActive);
        }
        if (e.target.closest('.save-edit-notice-btn')) saveNoticeEdit(noticeId);
        if (e.target.closest('.cancel-edit-notice-btn')) cancelNoticeEdit(noticeId);
    });
}


// ===============================
//       VYTVOŘENÍ OZNÁMENÍ
// ===============================
async function createNotice() {
    const serverId = getCurrentServerId();
    const title = document.getElementById('notice-title')?.value.trim();
    const content = document.getElementById('notice-content')?.value.trim();
    const type = document.getElementById('notice-type')?.value;
    const isPinned = document.getElementById('notice-pinned')?.checked;

    if (!title || !content) return alert('Vyplňte nadpis a obsah oznámení');

    const btn = document.getElementById('create-notice-btn');
    const original = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Vytvářím...';

    try {
        const res = await fetch('/api/notices/create', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ server_id: serverId, title, content, type, is_pinned: isPinned })
        });

        const result = await res.json();
        if (!result.success) throw new Error(result.error || 'Neznámá chyba');

        alert('Oznámení bylo vytvořeno');
        await loadNotices();
    } catch (err) {
        alert(`Chyba: ${err.message}`);
    } finally {
        btn.disabled = false;
        btn.innerHTML = original;
    }
}


// ===============================
//       EDITACE / MAZÁNÍ
// ===============================
async function editNotice(noticeId) {
    const notice = currentNotices.find(n => n.id == noticeId);
    if (!notice) return;

    document.querySelectorAll('.edit-notice-form').forEach(f => f.remove());
    const original = document.querySelector(`[data-notice-id="${noticeId}"]`);
    if (!original) return;

    const editForm = document.createElement('div');
    editForm.className = 'edit-notice-form';
    editForm.innerHTML = `
        <div class="card border-primary">
            <div class="card-header bg-primary text-white">
                <h6><i class="fas fa-edit"></i> Úprava oznámení</h6>
            </div>
            <div class="card-body">
                <input type="text" class="form-control mb-2 edit-notice-title" value="${notice.title}">
                
                <div class="text-toolbar mb-2">
                    <button class="btn btn-sm btn-outline-secondary text-tool-btn" data-tag="bold"><i class="fas fa-bold"></i></button>
                    <button class="btn btn-sm btn-outline-secondary text-tool-btn" data-tag="italic"><i class="fas fa-italic"></i></button>
                    <button class="btn btn-sm btn-outline-secondary text-tool-btn" data-tag="underline"><i class="fas fa-underline"></i></button>
                    <button class="btn btn-sm btn-outline-secondary text-tool-btn" data-tag="code"><i class="fas fa-code"></i></button>
                    <button class="btn btn-sm btn-outline-secondary text-tool-btn" data-tag="link"><i class="fas fa-link"></i></button>
                </div>

                <textarea class="form-control mb-3 edit-notice-content" rows="5">${notice.content}</textarea>

                <select class="form-control mb-2 edit-notice-type">
                    <option value="info" ${notice.type === 'info' ? 'selected' : ''}>ℹ️ Informace</option>
                    <option value="warning" ${notice.type === 'warning' ? 'selected' : ''}>⚠️ Varování</option>
                    <option value="important" ${notice.type === 'important' ? 'selected' : ''}>🔔 Důležité</option>
                    <option value="update" ${notice.type === 'update' ? 'selected' : ''}>🔄 Aktualizace</option>
                </select>

                <div class="form-check mb-2">
                    <input class="form-check-input edit-notice-pinned" type="checkbox" ${notice.is_pinned ? 'checked' : ''}> Připnout
                </div>
                <div class="form-check mb-3">
                    <input class="form-check-input edit-notice-active" type="checkbox" ${notice.is_active ? 'checked' : ''}> Aktivní
                </div>

                <button class="btn btn-success save-edit-notice-btn" data-notice-id="${noticeId}"><i class="fas fa-save"></i> Uložit</button>
                <button class="btn btn-secondary cancel-edit-notice-btn" data-notice-id="${noticeId}"><i class="fas fa-times"></i> Zrušit</button>
            </div>
        </div>
    `;

    original.style.display = 'none';
    original.parentNode.insertBefore(editForm, original);
    initTextToolsForElement(editForm);
}

function initTextToolsForElement(parent) {
    const toolbar = parent.querySelector('.text-toolbar');
    if (!toolbar) return;
    toolbar.addEventListener('click', e => {
        const btn = e.target.closest('.text-tool-btn');
        if (!btn) return;
        const tag = btn.dataset.tag;
        const textarea = parent.querySelector('textarea');
        applyTextFormatting(tag, textarea);
    });
}

async function saveNoticeEdit(noticeId) {
    const t = s => document.querySelector(`.edit-notice-${s}`);
    const data = {
        title: t('title').value.trim(),
        content: t('content').value.trim(),
        type: t('type').value,
        is_pinned: t('pinned').checked,
        is_active: t('active').checked
    };
    if (!data.title || !data.content) return alert('Vyplňte všechna pole.');

    try {
        const res = await fetch(`/api/notices/update/${noticeId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        const result = await res.json();
        if (!result.success) throw new Error(result.error);
        await loadNotices();
    } catch (err) {
        alert(`Chyba: ${err.message}`);
    }
}

function cancelNoticeEdit(noticeId) {
    const form = document.querySelector('.edit-notice-form');
    const notice = document.querySelector(`[data-notice-id="${noticeId}"]`);
    if (form) form.remove();
    if (notice) notice.style.display = 'block';
}

async function deleteNotice(id) {
    if (!confirm('Opravdu chcete smazat toto oznámení?')) return;
    try {
        const res = await fetch(`/api/notices/delete/${id}`, { method: 'DELETE' });
        const result = await res.json();
        if (!result.success) throw new Error(result.error);
        await loadNotices();
    } catch (err) {
        alert(`Chyba: ${err.message}`);
    }
}

async function toggleNotice(id, isActive) {
    try {
        await fetch(`/api/notices/update/${id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ is_active: isActive })
        });
        await loadNotices();
    } catch (err) {
        console.error(err);
    }
}


// ===============================
//      DOPLŇKOVÉ FUNKCE
// ===============================
async function checkAdminAccess(serverId) {
    try {
        const response = await fetch(`/api/server/admins?server_id=${serverId}`);
        const data = await response.json();

        // Získání aktuálního uživatele z localStorage nebo session
        const currentUser = JSON.parse(localStorage.getItem('current_user') || sessionStorage.getItem('current_user') || '{}');

        return data.is_owner || (data.admins && data.admins.some(admin => admin.user_id === currentUser.id));
    } catch (error) {
        console.error('Chyba při kontrole admin práv:', error);
        return false;
    }
}

function getNoticeTypeLabel(type) {
    return {
        info: 'Informace',
        warning: 'Varování',
        important: 'Důležité',
        update: 'Aktualizace'
    }[type] || type;
}
