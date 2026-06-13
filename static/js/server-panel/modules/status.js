// Modul pro správu stavu serveru
import { api, eventBus, EVENTS } from '../core/index.js';
import { getCurrentServerId } from '../core/utils.js';

class StatusManager {
    constructor() {
        this.serverId = getCurrentServerId();
        this.currentStatus = null;
        this.lastPlayerList = [];
        this.updateInterval = null;
    }

    /**
     * Inicializuje správu stavu
     */
    async init() {
        if (!this.serverId) {
            console.error('Nelze inicializovat StatusManager - chybějící serverId');
            return;
        }

        this.setupEventListeners();
        await this.loadServerInfo();  
        await this.updateStatus();
        this.startAutoUpdate();
    }

    /**
     * Nastaví event listenery pro tlačítka
     */
    setupEventListeners() {
        document.getElementById('start-btn')?.addEventListener('click', () => this.startServer());
        document.getElementById('stop-btn')?.addEventListener('click', () => this.stopServer());
        document.getElementById('restart-btn')?.addEventListener('click', () => this.restartServer());
    }

    /**
     * Aktualizuje stav serveru
     */
    async updateStatus() {
        try {
            const statusData = await api.getServerStatus(this.serverId);

            // Kontrola změny stavu
            const oldStatus = this.currentStatus?.status;
            const newStatus = statusData.status;

            if (oldStatus && oldStatus !== newStatus) {
                eventBus.emit(EVENTS.SERVER_STATUS_CHANGED, {
                    oldStatus,
                    newStatus,
                    data: statusData
                });
            }

            this.currentStatus = statusData;
            this.updateUI(statusData);
            this.updatePlayerList(statusData.player_names || []);

            eventBus.emit(EVENTS.SERVER_STATUS_UPDATED, statusData);

        } catch (error) {
            console.error('Chyba při načítání stavu:', error);
            eventBus.emit(EVENTS.ERROR_OCCURRED, {
                module: 'status',
                error
            });
        }
    }

    /**
     * Aktualizuje UI podle stavu serveru
     * @param {Object} data 
     */
    updateUI(data) {
        const indicator = document.querySelector('.status-indicator');
        const statusText = document.querySelector('.status-text');

        if (!indicator || !statusText) return;

        if (data.status === 'running') {
            indicator.className = 'status-indicator online';
            statusText.textContent = 'Online';

            // Aktualizace metrik
            this.updateMetric('ram-usage', data.ram_used_mb || '-');
            this.updateMetric('cpu-usage', data.cpu_percent || '0');
            this.updateMetric('cpu-max', data.cpu_max || '');
            this.updateMetric('player-count', data.players || '0');
            this.updateMetric('player-count-display', data.players || '0');
        } else {
            indicator.className = 'status-indicator offline';
            statusText.textContent = 'Offline';

            // Reset metrik
            this.updateMetric('ram-usage', '-');
            this.updateMetric('cpu-usage', data.cpu_percent || '-');
            this.updateMetric('player-count', '-');
            this.updateMetric('player-count-display', '0');
        }
    }

    /**
     * Aktualizuje konkrétní metrik element
     * @param {string} elementId 
     * @param {string} value 
     */
    updateMetric(elementId, value) {
        const element = document.getElementById(elementId);
        if (element) {
            element.textContent = value;
        }
    }

    /**
     * Aktualizuje seznam hráčů
     * @param {string[]} players 
     */
    updatePlayerList(players) {
        // Rychlé porovnání – pokud se seznam nezměnil, nic nedělej
        if (this.arraysEqual(players, this.lastPlayerList)) {
            return;
        }

        this.lastPlayerList = players;

        const table = document.getElementById('online-players-table');
        const tbody = document.getElementById('online-players-list');
        const noPlayersMsg = document.getElementById('no-players-message');

        if (!tbody || !noPlayersMsg) return;

        // Vymaž starý obsah
        tbody.innerHTML = '';

        if (players.length > 0) {
            if (table) table.style.display = 'table';
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
            if (table) table.style.display = 'none';
            noPlayersMsg.style.display = 'block';
        }
    }

    /**
     * Spustí server
     */
    async startServer() {
        try {
            const result = await api.startServer(this.serverId);

            if (result.success) {
                eventBus.emit(EVENTS.SERVER_STARTED, result);
                eventBus.emit(EVENTS.NOTIFICATION_SHOW, {
                    type: 'success',
                    message: 'Server se spouští...'
                });

                // Počkej a aktualizuj stav
                setTimeout(() => this.updateStatus(), 3000);
            } else {
                throw new Error('Chyba při spouštění serveru');
            }
        } catch (error) {
            console.error('Chyba při spouštění serveru:', error);
            eventBus.emit(EVENTS.NOTIFICATION_SHOW, {
                type: 'error',
                message: 'Chyba při spouštění serveru!'
            });
        }
    }

    /**
     * Vypne server
     */
    async stopServer() {
        if (!confirm('Opravdu chcete vypnout server? Všichni hráči budou odpojeni.')) {
            return;
        }

        try {
            const result = await api.stopServer(this.serverId);

            if (result.success) {
                eventBus.emit(EVENTS.SERVER_STOPPED, result);
                eventBus.emit(EVENTS.NOTIFICATION_SHOW, {
                    type: 'success',
                    message: 'Server se vypíná...'
                });

                // Počkej a aktualizuj stav
                setTimeout(() => this.updateStatus(), 5000);
            } else {
                throw new Error(result.error || 'Chyba při vypínání serveru');
            }
        } catch (error) {
            console.error('Chyba při vypínání serveru:', error);
            eventBus.emit(EVENTS.NOTIFICATION_SHOW, {
                type: 'error',
                message: error.message || 'Chyba při vypínání serveru!'
            });
        }
    }

    /**
     * Restartuje server
     */
    async restartServer() {
        if (!confirm('Opravdu chcete restartovat server? Všichni hráči budou odpojeni.')) {
            return;
        }

        try {
            const result = await api.restartServer(this.serverId);

            if (result.success) {
                eventBus.emit(EVENTS.SERVER_RESTARTED, result);
                eventBus.emit(EVENTS.NOTIFICATION_SHOW, {
                    type: 'success',
                    message: 'Server se restartuje...'
                });

                // Počkej a aktualizuj stav
                setTimeout(() => this.updateStatus(), 8000);
            } else {
                throw new Error(result.error || 'Chyba při restartu serveru');
            }
        } catch (error) {
            console.error('Chyba při restartu serveru:', error);
            eventBus.emit(EVENTS.NOTIFICATION_SHOW, {
                type: 'error',
                message: error.message || 'Chyba při restartu serveru!'
            });
        }
    }

    /**
     * Spustí automatickou aktualizaci stavu
     */
    startAutoUpdate() {
        // Zastav existující interval
        if (this.updateInterval) {
            clearInterval(this.updateInterval);
        }

        // Spustí nový interval (každých 10 sekund)
        this.updateInterval = setInterval(() => {
            this.updateStatus();
        }, 10000);
    }

    /**
     * Načte informace o serveru
     */
    async loadServerInfo() {
        try {
            const serverInfo = await api.getServerInfo(this.serverId);

            if (serverInfo.error) {
                console.error("Chyba při získávání informací o serveru:", serverInfo.error);
                return;
            }

            // Aktualizuj UI
            const loaderElement = document.getElementById('server-loader');
            const versionElement = document.getElementById('mc-version');

            if (loaderElement) loaderElement.textContent = serverInfo.server_loader || '-';
            if (versionElement) versionElement.textContent = serverInfo.mc_version || '-';

            eventBus.emit(EVENTS.SERVER_INFO_UPDATED, serverInfo);

        } catch (error) {
            console.error("Chyba při načítání informací o serveru:", error);
            eventBus.emit(EVENTS.ERROR_OCCURRED, {
                module: 'status',
                error
            });
        }
    }

    /**
     * Zastaví automatickou aktualizaci
     */
    stopAutoUpdate() {
        if (this.updateInterval) {
            clearInterval(this.updateInterval);
            this.updateInterval = null;
        }
    }

    /**
     * Porovná dva pole
     * @param {Array} a 
     * @param {Array} b 
     * @returns {boolean}
     */
    arraysEqual(a, b) {
        if (a.length !== b.length) return false;
        for (let i = 0; i < a.length; i++) {
            if (a[i] !== b[i]) return false;
        }
        return true;
    }
}

// Export singleton instance
export const statusManager = new StatusManager();