// Přidejte tuto funkci pro získání server_id z URL
function getCurrentServerId() {
    const pathParts = window.location.pathname.split('/');
    return pathParts[2]; // /server/<id> => část na indexu 2
}

// Přidejte na začátek souboru (pod getCurrentServerId)
function setupBackButton() {
    document.getElementById('back-btn').addEventListener('click', () => {
        window.location.href = '/dashboard';
    });
}

// Funkce pro detekci typu serveru
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

// Hlavní funkce pro správu zobrazení modů/pluginů
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
        
        // Uložit do localStorage pro budoucí použití
        localStorage.setItem(`server_${serverId}_build_type`, data.build_type);
    } catch (error) {
        console.error('Chyba při získávání build type:', error);
        buildType = getServerBuildType(); // fallback na localStorage
    }
    
    const modsSection = document.querySelector('.mods-quickview');
    const pluginsSection = document.querySelector('.plugins-quickview');

    if (isModServer(buildType)) {
        // Zobrazit pouze módy
        if (modsSection) modsSection.style.display = 'block';
        if (pluginsSection) pluginsSection.style.display = 'none';
        
        // Načíst módy
        try {
            await loadInstalledModsQuickview();
        } catch (error) {
            console.error('Chyba při načítání modů:', error);
        }
    } else if (isPluginServer(buildType)) {
        // Zobrazit pouze pluginy
        if (modsSection) modsSection.style.display = 'none';
        if (pluginsSection) pluginsSection.style.display = 'block';
        
        // Načíst pluginy
        try {
            await loadQuickViewPlugins();
        } catch (error) {
            console.error('Chyba při načítání pluginů:', error);
        }
    } else {
        // Neznámý build - skrýt obojí
        console.warn('Neznámý typ buildu:', buildType);
        if (modsSection) modsSection.style.display = 'none';
        if (pluginsSection) pluginsSection.style.display = 'none';
    }
}

// Načtení typu serveru při inicializaci
async function loadServerBuildType() {
    try {
        const response = await fetch(`/api/server/build-type?server_id=${getCurrentServerId()}`);
        const data = await response.json();
        
        // Uložit do localStorage pro budoucí použití
        localStorage.setItem(`server_${getCurrentServerId()}_build_type`, data.build_type);
        
        // Spravovat zobrazení komponent
        manageServerComponents();
        
    } catch (error) {
        console.error('Chyba při načítání typu serveru:', error);
        // Fallback - zkusit detekovat z URL
        manageServerComponents();
    }
}

document.addEventListener('DOMContentLoaded', function () {
    const serverId = getCurrentServerId();
    setupBackButton();
    updateStatus();

    // Načíst typ serveru a podle toho zobrazit komponenty
    loadServerBuildType();

    // Funkce pro aktualizaci stavu
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

                // Update player list
                updatePlayerList(data.player_names || []);
            } else {
                indicator.className = 'status-indicator offline';
                statusText.textContent = 'Offline';
                document.getElementById('ram-usage').textContent = '-';
                document.getElementById('cpu-usage').textContent = data.cpu_percent || '-';
                document.getElementById('player-count').textContent = '-';
                document.getElementById('player-count-display').textContent = '0';

                // Clear player list when server is offline
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

function loadLogs() {
    const serverId = getCurrentServerId();
    fetch(`/api/server/logs?server_id=${serverId}&lines=100`)
        .then(res => res.json())
        .then(data => {
            const logBox = document.getElementById("log-output");
            // Zde použijeme innerHTML, abychom vykreslili HTML s barvami
            logBox.innerHTML = data.html;
            logBox.scrollTop = logBox.scrollHeight;
        })
        .catch(error => {
            console.error('Chyba při načítání logů:', error);
        });
}

setInterval(loadLogs, 3000);
loadLogs();

function sendCommand() {
    const cmdInput = document.getElementById("console-input");
    const command = cmdInput.value.trim();
    const serverId = getCurrentServerId();
    if (!command) return;

    fetch(`/api/server/command?server_id=${serverId}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ command })
    }).then(() => {
        cmdInput.value = '';
        loadLogs();
    });
}

// Odeslání příkazu při stisknutí Enteru
document.getElementById('console-input').addEventListener('keydown', function (event) {
    if (event.key === 'Enter') {
        sendCommand();
    }
});

// Odeslání příkazu kliknutím na tlačítko
document.getElementById('sendCommand').addEventListener('click', sendCommand);

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

document.addEventListener('DOMContentLoaded', function() {
    // ... existující kód ...
    
    // Přesměrování na správu modů/pluginů
    document.getElementById('manage-mods-btn').addEventListener('click', () => {
        window.location.href = `/server/${getCurrentServerId()}/mods`;
    });
    
    document.getElementById('manage-plugins-btn').addEventListener('click', () => {
        window.location.href = `/server/${getCurrentServerId()}/plugins`;
    });
});