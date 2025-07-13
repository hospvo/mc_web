// Globální proměnné
let currentServerId;
let currentTab = 'installed';

// Inicializace po načtení stránky
document.addEventListener('DOMContentLoaded', function() {
    currentServerId = getCurrentServerId();
    setupEventListeners();
    loadInstalledPlugins();
});

function getCurrentServerId() {
    const pathParts = window.location.pathname.split('/');
    // URL je ve formátu /server/123/plugins
    return pathParts[2]; // Vrátí část mezi 'server' a 'plugins'
}

function setupEventListeners() {
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));

            btn.classList.add('active');
            document.getElementById(btn.dataset.tab + '-plugins').classList.add('active');
            currentTab = btn.dataset.tab;

            switch(currentTab) {
                case 'installed':
                    loadInstalledPlugins();
                    break;
                case 'available':
                    loadAvailablePlugins();
                    break;
                case 'updates':
                    checkForUpdates();
                    break;
                case 'manual':
                    document.getElementById('search-box').style.display = 'none';
                    break;
                default:
                    document.getElementById('search-box').style.display = 'flex';
            }
        });
    });

    document.getElementById('plugins-search-input').addEventListener('input', debounce(() => {
        if(currentTab === 'installed') loadInstalledPlugins();
        else if(currentTab === 'available') loadAvailablePlugins();
    }, 300));

    document.getElementById('plugins-filter-category').addEventListener('change', () => {
        if(currentTab === 'available') loadAvailablePlugins();
    });

    document.getElementById('back-to-server-btn').addEventListener('click', () => {
        window.location.href = `/server/${currentServerId}`;
    });

    // Přidáno: tlačítka pro manuální zadání pluginu
    const manualBtn = document.getElementById('get-download-link-btn');
    if (manualBtn) manualBtn.addEventListener('click', handleManualDownload);

    const installBtn = document.getElementById('install-from-url-btn');
    if (installBtn) installBtn.addEventListener('click', installFromUrl);
}

function debounce(func, wait) {
    let timeout;
    return function() {
        const context = this, args = arguments;
        clearTimeout(timeout);
        timeout = setTimeout(() => func.apply(context, args), wait);
    };
}

async function loadInstalledPlugins() {
    try {
        const response = await fetch(`/api/plugins/installed?server_id=${currentServerId}`);
        const plugins = await response.json();
        
        const searchTerm = document.getElementById('plugins-search-input').value.toLowerCase();
        const filteredPlugins = plugins.filter(p => 
            p.name.toLowerCase().includes(searchTerm) || 
            (p.display_name && p.display_name.toLowerCase().includes(searchTerm))
        );
        
        const list = document.getElementById('installed-plugins-list');
        list.innerHTML = '';
        
        if (filteredPlugins.length === 0) {
            list.innerHTML = '<div class="plugin-item no-plugins">Žádné pluginy nenalezeny</div>';
            return;
        }
        
        filteredPlugins.forEach(plugin => {
            const pluginItem = document.createElement('div');
            pluginItem.className = 'plugin-item';
            pluginItem.innerHTML = `
                <div class="plugin-name">${plugin.display_name || plugin.name}</div>
                <div class="plugin-version">${plugin.version}</div>
                <div class="plugin-status">${plugin.is_active ? 'Aktivní' : 'Neaktivní'}</div>
                <div class="plugin-actions">
                    <button class="plugin-btn uninstall" data-plugin-id="${plugin.id}">
                        <i class="fas fa-trash"></i> Odinstalovat
                    </button>
                </div>
            `;
            list.appendChild(pluginItem);
        });
        
        // Přidání event listenerů pro tlačítka
        document.querySelectorAll('.plugin-btn.uninstall').forEach(btn => {
            btn.addEventListener('click', () => uninstallPlugin(btn.dataset.pluginId));
        });
        
        updatePluginsCount(plugins.length, 0);
    } catch (error) {
        showError('Chyba při načítání pluginů: ' + error.message);
    }
}

async function loadAvailablePlugins() {
    try {
        const searchTerm = document.getElementById('plugins-search-input').value.toLowerCase();
        const category = document.getElementById('plugins-filter-category').value;
        
        const response = await fetch(`/api/plugins/available?search=${searchTerm}&category=${category}`);
        const plugins = await response.json();
        
        // Získat nainstalované pluginy pro kontrolu
        const installedResponse = await fetch(`/api/plugins/installed?server_id=${currentServerId}`);
        const installedPlugins = await installedResponse.json();
        const installedIds = installedPlugins.map(p => p.id);
        
        const list = document.getElementById('available-plugins-list');
        list.innerHTML = '';
        
        if (plugins.length === 0) {
            list.innerHTML = '<div class="plugin-item no-plugins">Žádné pluginy nenalezeny</div>';
            return;
        }
        
        plugins.forEach(plugin => {
            const isInstalled = installedIds.includes(plugin.id);
            
            const pluginItem = document.createElement('div');
            pluginItem.className = 'plugin-item';
            pluginItem.innerHTML = `
                <div class="plugin-name">${plugin.display_name || plugin.name}</div>
                <div class="plugin-version">${plugin.version}</div>
                <div class="plugin-description">${plugin.description || 'Žádný popis'}</div>
                <div class="plugin-actions">
                    ${isInstalled ? 
                        '<span class="already-installed">Nainstalováno</span>' : 
                        `<button class="plugin-btn install" data-plugin-id="${plugin.id}">
                            <i class="fas fa-download"></i> Nainstalovat
                        </button>`
                    }
                </div>
            `;
            list.appendChild(pluginItem);
        });
        
        // Přidání event listenerů pro tlačítka
        document.querySelectorAll('.plugin-btn.install').forEach(btn => {
            btn.addEventListener('click', () => installPlugin(btn.dataset.pluginId));
        });
        
        updatePluginsCount(installedPlugins.length, plugins.length);
    } catch (error) {
        showError('Chyba při načítání dostupných pluginů: ' + error.message);
    }
}

async function checkForUpdates() {
    try {
        const response = await fetch(`/api/plugins/check-updates?server_id=${currentServerId}`);
        const updates = await response.json();
        
        const list = document.getElementById('updates-plugins-list');
        list.innerHTML = '';
        
        if (updates.length === 0) {
            list.innerHTML = '<div class="plugin-item no-updates">Všechny pluginy jsou aktuální</div>';
            updatePluginsCount(0, 0);
            return;
        }
        
        updates.forEach(update => {
            const pluginItem = document.createElement('div');
            pluginItem.className = 'plugin-item';
            pluginItem.innerHTML = `
                <div class="plugin-name">${update.name}</div>
                <div class="plugin-version">${update.current_version}</div>
                <div class="plugin-version new-version">${update.new_version}</div>
                <div class="plugin-actions">
                    <button class="plugin-btn update" data-plugin-id="${update.plugin_id}">
                        <i class="fas fa-sync-alt"></i> Aktualizovat
                    </button>
                </div>
            `;
            list.appendChild(pluginItem);
        });
        
        // Přidání event listenerů pro tlačítka
        document.querySelectorAll('.plugin-btn.update').forEach(btn => {
            btn.addEventListener('click', () => updatePlugin(btn.dataset.pluginId));
        });
        
        updatePluginsCount(0, updates.length);
    } catch (error) {
        showError('Chyba při kontrole aktualizací: ' + error.message);
    }
}

async function installPlugin(pluginId) {
    if (!confirm('Opravdu chcete nainstalovat tento plugin?')) return;
    
    try {
        const response = await fetch(`/api/plugins/install?server_id=${currentServerId}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ plugin_id: pluginId })
        });
        
        const result = await response.json();
        
        if (result.success) {
            showSuccess('Plugin byl úspěšně nainstalován. Restartujte server pro aplikování změn.');
            loadAvailablePlugins();
            loadInstalledPlugins();
        } else {
            showError(result.error || 'Neznámá chyba při instalaci');
        }
    } catch (error) {
        showError('Chyba při instalaci: ' + error.message);
    }
}

async function uninstallPlugin(pluginId) {
    if (!confirm('Opravdu chcete odinstalovat tento plugin?')) return;
    
    try {
        const response = await fetch(`/api/plugins/uninstall?server_id=${currentServerId}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ plugin_id: pluginId })
        });
        
        const result = await response.json();
        
        if (result.success) {
            showSuccess('Plugin byl úspěšně odinstalován. Restartujte server pro aplikování změn.');
            loadInstalledPlugins();
            loadAvailablePlugins();
        } else {
            showError(result.error || 'Neznámá chyba při odinstalaci');
        }
    } catch (error) {
        showError('Chyba při odinstalaci: ' + error.message);
    }
}

async function updatePlugin(pluginId) {
    if (!confirm('Opravdu chcete aktualizovat tento plugin?')) return;
    
    try {
        // Zde byste volali API pro aktualizaci
        // Toto je pouze příklad
        showSuccess('Plugin byl úspěšně aktualizován. Restartujte server pro aplikování změn.');
        checkForUpdates();
        loadInstalledPlugins();
    } catch (error) {
        showError('Chyba při aktualizaci: ' + error.message);
    }
}

function updatePluginsCount(installedCount, updatesCount) {
    document.getElementById('plugins-count').textContent = installedCount;
    document.getElementById('updates-count').textContent = updatesCount;
}

function showSuccess(message) {
    const statusBar = document.getElementById('plugins-status-message');
    statusBar.textContent = message;
    statusBar.style.color = '#48bb78';
    setTimeout(() => {
        statusBar.textContent = 'Připraveno';
        statusBar.style.color = '';
    }, 3000);
}

function showError(message) {
    const statusBar = document.getElementById('plugins-status-message');
    statusBar.textContent = message;
    statusBar.style.color = '#f56565';
}


async function handleManualDownload() {
    const url = document.getElementById('plugin-url-input').value.trim();
    const resultDiv = document.getElementById('result-display');
    const resultContent = resultDiv.querySelector('.result-content');
    const installBtn = document.getElementById('install-from-url-btn');

    resultDiv.style.display = 'none';
    installBtn.style.display = 'none';
    resultContent.innerHTML = '';
    showStatus('Získávám informace o pluginu...');

    if (!url) {
        showError('Prosím zadejte URL pluginu z Modrinth');
        return;
    }

    try {
        const response = await fetch('/api/plugins/get-download-info', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                url: url,
                server_id: currentServerId
            })
        });

        const result = await response.json();
        if (!result.success) throw new Error(result.error || 'Chyba při zpracování pluginu.');

        const { plugin_name, download_url, info, compatible, reason } = result;
        const loaders = (info.latest_version?.loaders || []).join(', ');
        const versions = (info.latest_version?.game_versions || []).join(', ');

        let html = `
            <p class="success-message"><i class="fas fa-check-circle"></i> Plugin nalezen</p>
            <p><strong>Plugin:</strong> ${escapeHtml(plugin_name)}</p>
            <p><strong>Kompatibilita:</strong></p>
            <ul>
                <li><strong>Loadery:</strong> ${escapeHtml(loaders || 'Neznámo')}</li>
                <li><strong>Minecraft verze:</strong> ${escapeHtml(versions || 'Neznámo')}</li>
            </ul>
        `;

        if (!compatible) {
            html += `<p class="error-message"><i class="fas fa-exclamation-triangle"></i> ${escapeHtml(reason || 'Plugin není kompatibilní se serverem')}</p>
                     <button onclick="installFromUrl(true)" class="force-install-btn">
                        <i class="fas fa-exclamation-circle"></i> Přesto nainstalovat
                     </button>`;
        } else {
            installBtn.style.display = 'inline-block';
        }

        html += `
            <p><strong>Download URL:</strong></p>
            <input type="text" value="${escapeHtml(download_url)}" readonly class="download-url">
            <button onclick="copyToClipboard('${escapeHtml(download_url)}')" class="copy-btn">
                <i class="fas fa-copy"></i> Kopírovat URL
            </button>
        `;

        resultContent.innerHTML = html;
        resultDiv.dataset.url = url;
        resultDiv.dataset.downloadUrl = download_url;
        resultDiv.dataset.pluginName = plugin_name;
        resultDiv.style.display = 'block';

        showSuccess('Informace o pluginu načteny');
    } catch (err) {
        console.error('Chyba při zpracování URL:', err);
        resultContent.innerHTML = `<p class="error-message"><i class="fas fa-exclamation-circle"></i> ${escapeHtml(err.message)}</p>`;
        resultDiv.style.display = 'block';
        showError('Chyba: ' + err.message);
    }
}


async function installFromUrl(force = false) {
    const resultDiv = document.getElementById('result-display');
    const url = resultDiv.dataset.url;
    const downloadUrl = resultDiv.dataset.downloadUrl;
    const pluginName = resultDiv.dataset.pluginName || 'Manuálně přidaný plugin';
    const serverId = currentServerId;

    if (!url || !downloadUrl || !serverId) {
        showError('Chybějící požadované údaje');
        return;
    }

    try {
        showStatus('Instaluji plugin...');

        const response = await fetch(`/api/plugins/install-from-url`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            },
            body: JSON.stringify({
                url,
                download_url: downloadUrl,
                server_id: serverId,
                plugin_name: pluginName,
                force_install: force
            })
        });

        const result = await response.json();

        if (!response.ok) {
            if (result.plugin_exists) {
                showPluginExistsError(result.plugin_name, result.plugin_id);
            } else {
                throw new Error(result.error || 'Neznámá chyba při instalaci');
            }
            return;
        }

        showSuccess(`Plugin "${pluginName}" byl úspěšně nainstalován. Restartujte server pro aplikování změn.`);
        loadInstalledPlugins();
    } catch (err) {
        console.error('Instalace selhala:', err);
        showError('Chyba při instalaci: ' + (err.message || 'Neznámá chyba'));
    }
}


// Nová funkce pro zobrazení informace o existujícím pluginu
function showPluginExistsError(pluginName, pluginId) {
    const resultDiv = document.getElementById('result-display');
    const resultContent = resultDiv.querySelector('.result-content');
    
    resultContent.innerHTML = `
        <div class="alert alert-warning">
            <i class="fas fa-exclamation-triangle"></i>
            <strong>Plugin již existuje:</strong> ${escapeHtml(pluginName)}
        </div>
        <p>Tento plugin je již nainstalován v systému.</p>
    `;
    
    resultDiv.style.display = 'block';
    showWarning('Plugin již existuje v systému');
}

// Funkce pro možnost přesto nainstalovat
function showInstallAnywayPrompt(pluginId, pluginName) {
    if (confirm(`Opravdu chcete přesto nainstalovat plugin "${pluginName}"?`)) {
        // Volání speciálního endpointu pro přepsání existujícího pluginu
        forceInstallPlugin(pluginId);
    }
}
// Helper functions
function isValidCustomUrl(url) {
    try {
        const urlObj = new URL(url);
        return urlObj.protocol.match(/^https?:$/) && 
               urlObj.pathname.match(/\.jar($|\?)/);
    } catch {
        return false;
    }
}

function extractPluginNameFromUrl(url) {
    try {
        const urlObj = new URL(url);
        return urlObj.pathname.split('/').pop().replace(/\.jar.*$/, '');
    } catch {
        return 'Neznámý plugin';
    }
}

function escapeHtml(unsafe) {
    return unsafe
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

function copyToClipboard(text) {
    navigator.clipboard.writeText(text)
        .then(() => showSuccess('URL zkopírována do schránky'))
        .catch(err => {
            console.error('Chyba při kopírování:', err);
            showError('Chyba při kopírování: ' + err.message);
        });
}
function showStatus(message) {
    // Implementace zobrazení stavové zprávy
    console.log("Status:", message);
    // Například:
    const statusElement = document.getElementById('status-message');
    if (statusElement) {
        statusElement.textContent = message;
        statusElement.style.display = 'block';
        statusElement.className = 'status-message status';
    }
}

function showSuccess(message) {
    console.log("Success:", message);
    // Podobně jako showStatus, ale s úspěšným stylingem
    const statusElement = document.getElementById('status-message');
    if (statusElement) {
        statusElement.textContent = message;
        statusElement.style.display = 'block';
        statusElement.className = 'status-message success';
    }
}

function showError(message) {
    console.error("Error:", message);
    // Podobně jako showStatus, ale s chybovým stylingem
    const statusElement = document.getElementById('status-message');
    if (statusElement) {
        statusElement.textContent = message;
        statusElement.style.display = 'block';
        statusElement.className = 'status-message error';
    }
}

function showWarning(message) {
    console.warn("Warning:", message);
    const statusElement = document.getElementById('status-message');
    if (statusElement) {
        statusElement.textContent = message;
        statusElement.style.display = 'block';
        statusElement.className = 'status-message warning';
    }
}

// Make available globally
window.copyToClipboard = copyToClipboard;