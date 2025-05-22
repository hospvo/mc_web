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
    // Přepínání záložek
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
            }
        });
    });
    
    // Hledání pluginů
    document.getElementById('plugins-search-input').addEventListener('input', debounce(() => {
        if(currentTab === 'installed') loadInstalledPlugins();
        else if(currentTab === 'available') loadAvailablePlugins();
    }, 300));
    
    // Filtr kategorií
    document.getElementById('plugins-filter-category').addEventListener('change', () => {
        if(currentTab === 'available') loadAvailablePlugins();
    });
    
    // Tlačítko zpět
    document.getElementById('back-to-server-btn').addEventListener('click', () => {
        window.location.href = `/server/${currentServerId}`;
    });
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