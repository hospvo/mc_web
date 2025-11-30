
// Získání server_id
function getCurrentServerId() {
    return SERVER_ID;
}

// Tlačítko zpět na dashboard
function setupBackButton() {
    const btn = document.getElementById('back-btn');
    if (btn) {
        btn.addEventListener('click', () => {
            window.location.href = '/dashboard';
        });
    }
}

// Načtení informací o serveru
async function loadServerInfo() {
    const serverId = getCurrentServerId();
    try {
        const response = await fetch(`/api/player/server/info?server_id=${serverId}`);
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

// Status serveru
async function updateStatus() {
    const serverId = getCurrentServerId();
    try {
        const response = await fetch(`/api/player/server/status?server_id=${serverId}`);
        const data = await response.json();

        if (data.error) {
            console.error('Chyba při načítání stavu:', data.error);
            return;
        }

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

// Aktualizace seznamu hráčů
let lastPlayerList = [];

function updatePlayerList(players) {
    const table = document.getElementById('online-players-table');
    const tbody = document.getElementById('online-players-list');
    const noPlayersMsg = document.getElementById('no-players-message');

    if (arraysEqual(players, lastPlayerList)) {
        return;
    }

    lastPlayerList = players;
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

// Načtení oznámení
async function loadNotices() {
    const serverId = getCurrentServerId();
    try {
        const response = await fetch(`/api/player/notices?server_id=${serverId}`);
        if (!response.ok) throw new Error('Chyba při načítání oznámení');

        const notices = await response.json();
        
        // Ošetření případu, kdy API vrátí error místo seznamu oznámení
        if (notices.error) {
            throw new Error(notices.error);
        }

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
            
            noticeElement.innerHTML = `
                <div class="notice-header">
                    <div>
                        <h5 class="notice-title">
                            ${notice.is_pinned ? '<i class="fas fa-thumbtack"></i>' : ''}
                            ${notice.title}
                            <span class="notice-badge badge-${notice.type}">
                                ${getNoticeTypeLabel(notice.type)}
                            </span>
                        </h5>
                        <div class="notice-meta">
                            ${notice.author} • ${notice.created_at}
                        </div>
                    </div>
                </div>
                <div class="notice-content formatted">
                    ${formatNoticeContent(notice.content)}
                </div>
            `;
            container.appendChild(noticeElement);
        });
    } catch (error) {
        console.error('Chyba při načítání oznámení:', error);
        const container = document.getElementById('notices-container');
        if (container) {
            container.innerHTML = '<div class="text-danger">Chyba při načítání oznámení: ' + error.message + '</div>';
        }
    }
}

// Formátování obsahu oznámení
function formatNoticeContent(text) {
    if (!text) return '';

    return text
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.*?)\*/g, '<em>$1</em>')
        .replace(/`(.*?)`/g, '<code>$1</code>')
        .replace(/\[(.*?)\]\((.*?)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>')
        .replace(/\n/g, '<br>');
}

function getNoticeTypeLabel(type) {
    return {
        info: 'Informace',
        warning: 'Varování',
        important: 'Důležité',
        update: 'Aktualizace'
    }[type] || type;
}

// Nástroje pro hráče - uprav URL v onClick funkcích
function initClientTools() {
    const serverId = getCurrentServerId();
    const container = document.getElementById('client-tools-container');
    
    if (!container) {
        console.warn('Container #client-tools-container nebyl nalezen');
        return;
    }

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

                    // ZMĚNA: Použij player endpoint
                    const response = await fetch(`/api/player/mods/client-pack/download?server_id=${serverId}`);
                    if (!response.ok) throw new Error(`HTTP ${response.status}: ${response.statusText}`);

                    const blob = await response.blob();
                    if (blob.size === 0) throw new Error('Obdržen prázdný soubor');

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
}

// Výběr modpacků
async function showModpacksSelection(serverId) {
    try {
        const response = await fetch(`/api/modpacks/list?server_id=${serverId}`);
        if (!response.ok) throw new Error('Chyba při načítání modpacků');

        const modpacks = await response.json();

        if (modpacks.length === 0) {
            alert('Pro tento server nejsou k dispozici žádné modpacky.');
            return;
        }

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
                            style="background: linear-gradient(135deg, #e74c3c, #c0392b); color: white; border: none; padding: 0.5rem 1.5rem; border-radius: 6px; font-weight: 600;">
                            Zavřít
                        </button>
                    </div>
                </div>
            </div>
        `;

        document.body.appendChild(modal);

        modal.querySelector('#close-modpack-selection').addEventListener('click', () => {
            document.body.removeChild(modal);
        });

        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                document.body.removeChild(modal);
            }
        });

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

function formatSize(bytes) {
    if (bytes === 0) return '0 B';
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / 1024 / 1024).toFixed(2)} MB`;
}

async function downloadModpack(packId) {
    try {
        // ZMĚNA: Použij player endpoint
        const response = await fetch(`/api/player/modpacks/download/${packId}`);
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
        alert('Nepodařilo se stáhnout modpack: ' + error.message);
    }
}

// Načtení modů pro rychlý náhled
async function loadInstalledModsQuickview() {
    try {
        const response = await fetch(`/api/player/mods/installed?server_id=${getCurrentServerId()}`);
        if (!response.ok) return;

        const result = await response.json();
        
        // Ošetření případu, kdy API vrátí error
        if (result.error) {
            console.warn('Chyba při načítání modů:', result.error);
            return;
        }

        if (!Array.isArray(result)) return;

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
    }
}

// Odeslání nahlášení
async function sendReport() {
    const message = document.getElementById('report-message').value.trim();
    const feedback = document.getElementById('report-feedback');

    if (!message) {
        feedback.textContent = 'Zpráva nesmí být prázdná.';
        feedback.className = 'text-danger';
        return;
    }

    const btn = document.getElementById('send-report');
    const originalText = btn.innerHTML;

    try {
        btn.disabled = true;
        btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Odesílám...';
        feedback.textContent = '';
        feedback.className = '';

        const response = await fetch('/api/player/report', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                server_id: getCurrentServerId(), 
                message: message 
            })
        });

        const result = await response.json();

        if (result.success) {
            feedback.textContent = result.message || 'Nahlášení bylo úspěšně odesláno.';
            feedback.className = 'text-success';
            document.getElementById('report-message').value = '';
        } else {
            throw new Error(result.error || 'Neznámá chyba');
        }

    } catch (error) {
        console.error('Chyba při odesílání nahlášení:', error);
        feedback.textContent = `Chyba: ${error.message}`;
        feedback.className = 'text-danger';
    } finally {
        btn.disabled = false;
        btn.innerHTML = originalText;
    }
}

// Detekce typu serveru a zobrazení příslušných sekcí
async function manageServerComponents() {
    const serverId = getCurrentServerId();
    let buildType;

    try {
        const response = await fetch(`/api/player/server/build-type?server_id=${serverId}`);
        if (response.ok) {
            const data = await response.json();
            buildType = data.build_type;
        }
    } catch (error) {
        console.error('Chyba při získávání build type:', error);
    }

    const modsSection = document.querySelector('.mods-quickview');
    
    // Zobrazit sekci modů pouze pro mod servery
    if (buildType && isModServer(buildType)) {
        if (modsSection) modsSection.style.display = 'block';
        await loadInstalledModsQuickview();
    }
}

function isModServer(buildType) {
    const modBuilds = [
        'FABRIC', 'FORGE', 'NEOFORGE', 'QUILT', 'BABRIC', 'BTA',
        'JAVA_AGENT', 'LEGACY_FABRIC', 'LITELOADER', 'MODLOADER',
        'NILLOADER', 'ORNITHE', 'RIFT', 'RISUGAMI'
    ];
    return modBuilds.includes(buildType.toUpperCase());
}

// Inicializace
document.addEventListener('DOMContentLoaded', function () {
    setupBackButton();
    loadServerInfo();
    updateStatus();
    loadNotices();
    initClientTools();
    manageServerComponents();

    // Event listener pro odeslání nahlášení
    document.getElementById('send-report').addEventListener('click', sendReport);
    document.getElementById('report-message').addEventListener('keypress', function (e) {
        if (e.key === 'Enter' && e.ctrlKey) {
            sendReport();
        }
    });

    // Automatická aktualizace stavu každých 10 sekund
    setInterval(updateStatus, 10000);
});