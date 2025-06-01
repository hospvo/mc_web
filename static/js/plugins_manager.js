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

    // Reset UI state
    resultDiv.style.display = 'none';
    installBtn.style.display = 'none';
    resultContent.innerHTML = '';
    showStatus('Zpracovávám URL...');

    // Validate input
    if (!url) {
        showError('Prosím zadejte URL pluginu z Modrinth');
        return;
    }

    try {
        let downloadUrl, pluginName;

        // Validate Modrinth URL
        const slugMatch = url.match(/modrinth\.com\/plugin\/([^\/]+)/);
        if (!slugMatch) {
            throw new Error('Neplatný Modrinth odkaz. Očekávám formát "https://modrinth.com/plugin/nazev-pluginu"');
        }

        const slug = slugMatch[1];
        
        // Get plugin info
        const pluginRes = await fetch(`https://api.modrinth.com/v2/project/${slug}`);
        if (!pluginRes.ok) throw new Error('Modrinth plugin nenalezen');
        const pluginData = await pluginRes.json();
        pluginName = pluginData.title || slug;

        // Get versions
        const versionRes = await fetch(`https://api.modrinth.com/v2/project/${slug}/version`);
        if (!versionRes.ok) throw new Error('Chyba při načítání verzí');
        const versions = await versionRes.json();
        
        if (!versions.length) throw new Error('Nenalezeny žádné verze pluginu');
        
        // Find compatible version (Paper, Purpur, Spigot)
        const compatibleVersion = versions.find(v => 
            v.loaders.includes('paper') || v.loaders.includes('purpur') || v.loaders.includes('spigot')
        ) || versions[0];
        
        if (!compatibleVersion.files?.[0]?.url) {
            throw new Error('Nepodařilo se získat download URL');
        }
        
        downloadUrl = compatibleVersion.files[0].url;

        // Display results
        resultContent.innerHTML = `
            <p class="success-message"><i class="fas fa-check-circle"></i> Úspěšně nalezen download URL</p>
            <p><strong>Plugin:</strong> ${escapeHtml(pluginName)}</p>
            <p><strong>Download URL:</strong></p>
            <input type="text" value="${escapeHtml(downloadUrl)}" readonly class="download-url">
            <button onclick="copyToClipboard('${escapeHtml(downloadUrl)}')" class="copy-btn">
                <i class="fas fa-copy"></i> Kopírovat URL
            </button>
        `;

        // Store data for installation
        resultDiv.dataset.downloadUrl = downloadUrl;
        resultDiv.dataset.pluginName = pluginName;

        // Show results and install button
        installBtn.style.display = 'inline-block';
        resultDiv.style.display = 'block';
        showSuccess('Download URL úspěšně získána');

    } catch (err) {
        console.error('Chyba při zpracování URL:', err);
        resultContent.innerHTML = `
            <p class="error-message"><i class="fas fa-exclamation-circle"></i> ${escapeHtml(err.message)}</p>
        `;
        resultDiv.style.display = 'block';
        showError('Chyba: ' + err.message);
    }
}

async function installFromUrl() {
    const resultDiv = document.getElementById('result-display');
    const downloadUrl = resultDiv.dataset.downloadUrl;
    const pluginName = resultDiv.dataset.pluginName || 'Manuálně přidaný plugin';

    if (!downloadUrl) {
        showError('Neplatná download URL');
        return;
    }

    if (!confirm(`Opravdu chcete nainstalovat plugin "${pluginName}"?`)) {
        return;
    }

    try {
        showStatus('Instaluji plugin...');
        
        const response = await fetch(`/api/plugins/install-from-url?server_id=${currentServerId}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                download_url: downloadUrl,
                plugin_name: pluginName,
                server_id: currentServerId
            })
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.error || `HTTP chyba: ${response.status}`);
        }

        const result = await response.json();
        
        if (result.success) {
            showSuccess(`Plugin "${pluginName}" byl úspěšně nainstalován. Restartujte server pro aplikování změn.`);
            // Refresh installed plugins list
            loadInstalledPlugins();
        } else {
            throw new Error(result.error || 'Neznámá chyba při instalaci');
        }
    } catch (err) {
        console.error('Instalace selhala:', err);
        showError('Chyba při instalaci: ' + (err.message || 'Neznámá chyba'));
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

// Make available globally
window.copyToClipboard = copyToClipboard;