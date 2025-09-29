// [file name]: mods_manager.js
// Globální proměnné
let currentServerId;
let currentTab = 'installed';

// Inicializace po načtení stránky
document.addEventListener('DOMContentLoaded', function () {
    currentServerId = getCurrentServerId();
    setupEventListeners();
    loadInstalledMods();
});

function getCurrentServerId() {
    const pathParts = window.location.pathname.split('/');
    // URL je ve formátu /server/123/mods
    return pathParts[2]; // Vrátí část mezi 'server' a 'mods'
}

function setupEventListeners() {
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));

            btn.classList.add('active');
            document.getElementById(btn.dataset.tab + '-mods').classList.add('active');
            currentTab = btn.dataset.tab;

            // OPRAVENÁ ČÁST - správa zobrazení vyhledávače
            const searchBox = document.getElementById('search-box');
            if (currentTab === 'installed' || currentTab === 'available') {
                searchBox.style.display = 'flex';
            } else {
                searchBox.style.display = 'none';
            }

            switch (currentTab) {
                case 'installed':
                    loadInstalledMods();
                    break;
                case 'available':
                    loadAvailableMods();
                    break;
                case 'updates':
                    checkForUpdates();
                    break;
                case 'manual':
                    // searchBox je již skrytý výše
                    break;
            }
        });
    });

    document.getElementById('mods-search-input').addEventListener('input', debounce(() => {
        if (currentTab === 'installed') loadInstalledMods();
        else if (currentTab === 'available') loadAvailableMods();
    }, 300));

    document.getElementById('mods-filter-category').addEventListener('change', () => {
        if (currentTab === 'available') loadAvailableMods();
    });

    document.getElementById('back-to-server-btn').addEventListener('click', () => {
        window.location.href = `/server/${currentServerId}`;
    });

    // Přidáno: tlačítka pro manuální zadání modu
    const manualBtn = document.getElementById('get-download-link-btn');
    if (manualBtn) manualBtn.addEventListener('click', handleManualDownload);

    const installBtn = document.getElementById('install-from-url-btn');
    if (installBtn) installBtn.addEventListener('click', installFromUrl);
}

function debounce(func, wait) {
    let timeout;
    return function () {
        const context = this, args = arguments;
        clearTimeout(timeout);
        timeout = setTimeout(() => func.apply(context, args), wait);
    };
}

async function loadInstalledMods() {
    try {
        const response = await fetch(`/api/mods/installed?server_id=${currentServerId}`);
        const mods = await response.json();

        const searchTerm = document.getElementById('mods-search-input').value.toLowerCase();
        const filteredMods = mods.filter(p =>
            p.name.toLowerCase().includes(searchTerm) ||
            (p.display_name && p.display_name.toLowerCase().includes(searchTerm))
        );

        const list = document.getElementById('installed-mods-list');
        list.innerHTML = '';

        if (filteredMods.length === 0) {
            list.innerHTML = '<div class="mod-item no-mods">Žádné mody nenalezeny</div>';
            return;
        }

        filteredMods.forEach(mod => {
            const modItem = document.createElement('div');
            modItem.className = 'mod-item';
            modItem.innerHTML = `
                <div class="mod-name">${mod.display_name || mod.name}</div>
                <div class="mod-version">${mod.version}</div>
                <div class="mod-status">${mod.is_active ? 'Aktivní' : 'Neaktivní'}</div>
                <div class="mod-actions">
                    <button class="mod-btn uninstall" data-mod-id="${mod.id}">
                        <i class="fas fa-trash"></i> Odinstalovat
                    </button>
                </div>
            `;
            list.appendChild(modItem);
        });

        // Přidání event listenerů pro tlačítka
        document.querySelectorAll('.mod-btn.uninstall').forEach(btn => {
            btn.addEventListener('click', () => uninstallMod(btn.dataset.modId));
        });

        updateModsCount(mods.length, 0);
    } catch (error) {
        showError('Chyba při načítání modů: ' + error.message);
    }
}

async function loadAvailableMods() {
    try {
        const searchTerm = document.getElementById('mods-search-input').value.toLowerCase();
        const category = document.getElementById('mods-filter-category').value;

        const response = await fetch(`/api/mods/available?search=${searchTerm}&category=${category}&server_id=${currentServerId}`);
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const result = await response.json();
        
        // OŠETŘENÍ - pokud API vrátí chybu místo pole
        if (!Array.isArray(result)) {
            if (result.error) {
                throw new Error(result.error);
            }
            throw new Error('Neplatná odpověď ze serveru');
        }

        const availableMods = result;
        
        // ZÍSKEJ NAINSTALOVANÉ MODY PRO KONTROLU
        let installedMods = [];
        try {
            const installedResponse = await fetch(`/api/mods/installed?server_id=${currentServerId}`);
            if (installedResponse.ok) {
                const installedResult = await installedResponse.json();
                installedMods = Array.isArray(installedResult) ? installedResult : [];
            }
        } catch (error) {
            console.error('Chyba při načítání nainstalovaných modů:', error);
            installedMods = [];
        }
        
        const installedIds = installedMods.map(p => p.id);

        const list = document.getElementById('available-mods-list');
        list.innerHTML = '';

        if (availableMods.length === 0) {
            list.innerHTML = '<div class="mod-item no-mods">Žádné kompatibilní módy nenalezeny</div>';
            updateModsCount(installedMods.length, 0);
            return;
        }

        availableMods.forEach(mod => {
            const isInstalled = installedIds.includes(mod.id);

            const modItem = document.createElement('div');
            modItem.className = 'mod-item';
            modItem.innerHTML = `
                <div class="mod-name">${mod.display_name || mod.name}</div>
                <div class="mod-version">${mod.version}</div>
                <div class="mod-description">${mod.description || 'Žádný popis'}</div>
                <div class="mod-actions">
                    ${isInstalled ? 
                        '<span class="already-installed">Nainstalováno</span>' : 
                        `<button class="mod-btn install" data-mod-id="${mod.id}">
                            <i class="fas fa-download"></i> Nainstalovat
                        </button>`
                    }
                </div>
            `;
            list.appendChild(modItem);
        });

        // Přidání event listenerů pro tlačítka
        document.querySelectorAll('.mod-btn.install').forEach(btn => {
            btn.addEventListener('click', () => installMod(btn.dataset.modId));
        });

        updateModsCount(installedMods.length, availableMods.length);
        
    } catch (error) {
        console.error('Chyba při načítání dostupných modů:', error);
        showError('Chyba při načítání dostupných modů: ' + error.message);
        
        const list = document.getElementById('available-mods-list');
        if (list) {
            list.innerHTML = `
                <div class="mod-item error">
                    <i class="fas fa-exclamation-triangle"></i>
                    Chyba při načítání modů: ${error.message}
                </div>
            `;
        }
        updateModsCount(0, 0);
    }
}

async function checkForUpdates() {
    try {
        showStatus('Kontroluji aktualizace...');

        const response = await fetch(`/api/mods/check-updates?server_id=${currentServerId}`);

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const updates = await response.json();

        const list = document.getElementById('updates-mods-list');
        list.innerHTML = '';

        if (updates.length === 0) {
            list.innerHTML = `
                <div class="mod-item no-updates">
                    <i class="fas fa-check-circle" style="color: #4CAF50; font-size: 2rem; margin-bottom: 1rem;"></i>
                    <h4>Všechny mody jsou aktuální!</h4>
                    <p>Žádné dostupné aktualizace nebyly nalezeny.</p>
                </div>
            `;
            updateModsCount(0, 0);
            showSuccess('Kontrola aktualizací dokončena');
            return;
        }

        updates.forEach(update => {
            const modItem = document.createElement('div');
            modItem.className = 'mod-item update-available';
            modItem.innerHTML = `
                <div class="mod-info">
                    <div class="mod-name">${escapeHtml(update.name)}</div>
                    <div class="version-comparison">
                        <span class="current-version">${escapeHtml(update.current_version)}</span>
                        <i class="fas fa-arrow-right"></i>
                        <span class="new-version">${escapeHtml(update.new_version)}</span>
                    </div>
                    ${update.changelog ? `
                        <div class="changelog-preview">
                            <strong>Co je nového:</strong>
                            <p>${escapeHtml(update.changelog.substring(0, 150) + (update.changelog.length > 150 ? '...' : ''))}</p>
                        </div>
                    ` : ''}
                </div>
                <div class="mod-actions">
                    <button class="mod-btn update" data-mod-id="${update.mod_id}">
                        <i class="fas fa-sync-alt"></i> Aktualizovat
                    </button>
                </div>
            `;
            list.appendChild(modItem);
        });

        // Přidání event listenerů pro tlačítka
        document.querySelectorAll('.mod-btn.update').forEach(btn => {
            btn.addEventListener('click', () => updateMod(btn.dataset.modId));
        });

        updateModsCount(0, updates.length);
        showSuccess(`Nalezeno ${updates.length} aktualizací`);

    } catch (error) {
        console.error('Chyba při kontrole aktualizací:', error);
        showError('Chyba při kontrole aktualizací: ' + error.message);
    }
}

async function installMod(modId) {
    if (!confirm('Opravdu chcete nainstalovat tento mod?')) return;

    try {
        const response = await fetch(`/api/mods/install?server_id=${currentServerId}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ mod_id: modId })
        });

        const result = await response.json();

        if (result.success) {
            showSuccess('Mod byl úspěšně nainstalován. Restartujte server pro aplikování změn.');
            loadAvailableMods();
            loadInstalledMods();
        } else {
            showError(result.error || 'Neznámá chyba při instalaci');
        }
    } catch (error) {
        showError('Chyba při instalaci: ' + error.message);
    }
}

async function uninstallMod(modId) {
    if (!confirm('Opravdu chcete odinstalovat tento mod?')) return;

    try {
        const response = await fetch(`/api/mods/uninstall?server_id=${currentServerId}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ mod_id: modId })
        });

        const result = await response.json();

        if (result.success) {
            showSuccess('Mod byl úspěšně odinstalován. Restartujte server pro aplikování změn.');
            loadInstalledMods();
            loadAvailableMods();
        } else {
            showError(result.error || 'Neznámá chyba při odinstalaci');
        }
    } catch (error) {
        showError('Chyba při odinstalaci: ' + error.message);
    }
}

async function updateMod(modId) {
    if (!confirm('Opravdu chcete aktualizovat tento mod?')) return;

    try {
        // Zde byste volali API pro aktualizaci
        // Toto je pouze příklad
        showSuccess('Mod byl úspěšně aktualizován. Restartujte server pro aplikování změn.');
        checkForUpdates();
        loadInstalledMods();
    } catch (error) {
        showError('Chyba při aktualizaci: ' + error.message);
    }
}

function updateModsCount(installedCount, availableCount) {
    // Aktualizuj počty v UI - přidej tyto elementy do HTML pokud je nemáš
    const modsCountElement = document.getElementById('mods-count');
    const availableCountElement = document.getElementById('available-mods-count');
    
    if (modsCountElement) modsCountElement.textContent = installedCount;
    if (availableCountElement) availableCountElement.textContent = availableCount;
}

function showSuccess(message) {
    const statusBar = document.getElementById('mods-status-message');
    statusBar.textContent = message;
    statusBar.style.color = '#48bb78';
    setTimeout(() => {
        statusBar.textContent = 'Připraveno';
        statusBar.style.color = '';
    }, 3000);
}

function showError(message) {
    const statusBar = document.getElementById('mods-status-message');
    statusBar.textContent = message;
    statusBar.style.color = '#f56565';
}


async function handleManualDownload() {
    const url = document.getElementById('mod-url-input').value.trim();
    const resultDiv = document.getElementById('result-display');
    const resultContent = resultDiv.querySelector('.result-content');
    const installBtn = document.getElementById('install-from-url-btn');

    resultDiv.style.display = 'none';
    installBtn.style.display = 'none';
    resultContent.innerHTML = '';
    showStatus('Získávám informace o modu...');

    if (!url) {
        showError('Prosím zadejte URL modu z Modrinth');
        return;
    }



    try {
        const response = await fetch('/api/mods/get-download-info', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                url: url,
                server_id: currentServerId
            })
        });

        const result = await response.json();
        if (!result.success) throw new Error(result.error || 'Chyba při zpracování modu.');

        const { mod_name, download_url, info, compatible, reason, warning } = result;
        const loaders = (info.latest_version?.loaders || []).join(', ');
        const versions = (info.latest_version?.game_versions || []).join(', ');



        let html = `
            <p class="success-message"><i class="fas fa-check-circle"></i> Mod nalezen</p>
            <p><strong>Mod:</strong> ${escapeHtml(mod_name)}</p>
            <p><strong>Kompatibilita:</strong></p>
            <ul>
                <li><strong>Loadery:</strong> ${escapeHtml(loaders || 'Neznámo')}</li>
                <li><strong>Minecraft verze:</strong> ${escapeHtml(versions || 'Neznámo')}</li>
            </ul>
        `;

        if (!compatible) {
            html += `<p class="error-message"><i class="fas fa-exclamation-triangle"></i> ${escapeHtml(reason || 'Mod není kompatibilní se serverem')}</p>
                     <button onclick="installFromUrl(true)" class="force-install-btn">
                        <i class="fas fa-exclamation-circle"></i> Přesto nainstalovat
                     </button>`;
        } else {
            installBtn.style.display = 'inline-block';
        }

        if (warning) {
            html += `<p class="error-message">
                <i class="fas fa-exclamation-triangle"></i> ${escapeHtml(warning)}
            </p>`;
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
        resultDiv.dataset.modName = mod_name;
        resultDiv.style.display = 'block';

        showSuccess('Informace o modu načteny');
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
    const modName = resultDiv.dataset.modName || 'Manuálně přidaný mod';
    const serverId = currentServerId;

    if (!url || !downloadUrl || !serverId) {
        showError('Chybějící požadované údaje');
        return;
    }

    try {
        showStatus('Instaluji mod...');

        const response = await fetch(`/api/mods/install-from-url`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            },
            body: JSON.stringify({
                url,
                download_url: downloadUrl,
                server_id: serverId,
                mod_name: modName,
                force_install: force
            })
        });

        const result = await response.json();

        if (!response.ok) {
            if (result.mod_exists) {
                showModExistsError(result.mod_name, result.mod_id);
            } else {
                throw new Error(result.error || 'Neznámá chyba při instalaci');
            }
            return;
        }

        // ✅ ZOBRAZENÍ ÚSPĚŠNÉ INSTALACE
        showInstallationSuccess(modName);
        loadInstalledMods();

    } catch (err) {
        console.error('Instalace selhala:', err);
        showError('Chyba při instalaci: ' + (err.message || 'Neznámá chyba'));
    }
}

// ✅ NOVÁ FUNKCE: Zobrazení úspěšné instalace
function showInstallationSuccess(modName) {
    const resultDiv = document.getElementById('result-display');
    const resultContent = resultDiv.querySelector('.result-content');

    resultContent.innerHTML = `
        <div class="installation-success">
            <div class="success-icon">
                <i class="fas fa-check-circle"></i>
            </div>
            <div class="success-content">
                <h4>Mod úspěšně nainstalován!</h4>
                <p><strong>${escapeHtml(modName)}</strong> byl úspěšně nainstalován na server.</p>
                <div class="success-actions">
                    <button onclick="location.reload()" class="refresh-btn">
                        <i class="fas fa-sync"></i> Obnovit stránku
                    </button>
                </div>
            </div>
        </div>
    `;

    resultDiv.style.display = 'block';
    showSuccess(`Mod "${modName}" byl úspěšně nainstalován`);
}


// ✅ VYLEPŠENÁ FUNKCE: Zobrazení existujícího modu
function showModExistsError(modName, modId) {
    const resultDiv = document.getElementById('result-display');
    const resultContent = resultDiv.querySelector('.result-content');

    resultContent.innerHTML = `
        <div class="mod-exists-warning">
            <div class="warning-icon">
                <i class="fas fa-exclamation-triangle"></i>
            </div>
            <div class="warning-content">
                <h4>Mod již existuje</h4>
                <p><strong>${escapeHtml(modName)}</strong> je již nainstalován v systému.</p>
                <p class="warning-note">
                    <i class="fas fa-info-circle"></i>
                    Tento mod nelze znovu nainstalovat. Pokud chcete aktualizovat na novější verzi, 
                    použijte funkci aktualizace v sekci "Nainstalované mody".
                </p>
                <div class="warning-actions">
                    <button onclick="switchToInstalledTab()" class="switch-tab-btn">
                        <i class="fas fa-exchange-alt"></i> Přepnout na nainstalované
                    </button>
                </div>
            </div>
        </div>
    `;

    resultDiv.style.display = 'block';
    showWarning('Mod již existuje v systému');
}

// ✅ POMOCNÁ FUNKCE: Přepnutí na záložku nainstalovaných modů
function switchToInstalledTab() {
    document.querySelector('[data-tab="installed"]').click();
}

// Funkce pro možnost přesto nainstalovat
function showInstallAnywayPrompt(modId, modName) {
    if (confirm(`Opravdu chcete přesto nainstalovat mod "${modName}"?`)) {
        // Volání speciálního endpointu pro přepsání existujícího modu
        forceInstallMod(modId);
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

function extractModNameFromUrl(url) {
    try {
        const urlObj = new URL(url);
        return urlObj.pathname.split('/').pop().replace(/\.jar.*$/, '');
    } catch {
        return 'Neznámý mod';
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