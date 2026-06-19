// Modul pro správu záloh
import { API_ENDPOINTS } from '../core/constants.js';
import { api } from '../core/api.js';
import { eventBus, EVENTS } from '../core/event-bus.js';
import { getCurrentServerId, formatSize } from '../core/utils.js';

class BackupManager {
    constructor() {
        this.serverId = getCurrentServerId();
        this.diskUpdateInterval = null;
    }

    /**
     * Inicializuje správu záloh
     */
    async init() {
        if (!this.serverId) {
            console.error('Nelze inicializovat BackupManager - chybějící serverId');
            return;
        }

        this.setupEventListeners();
        await this.loadBackups();
        await this.updateDiskUsage();
        this.startDiskUsageUpdate();
    }

    /**
     * Nastaví event listenery
     */
    setupEventListeners() {
        // Tlačítko pro vytvoření zálohy
        const createBtn = document.getElementById('create-backup-btn');
        if (createBtn) {
            createBtn.addEventListener('click', () => this.createBackup());
        }
    }

    /**
     * Načte seznam záloh
     */
    async loadBackups() {
        try {
            const backups = await api.get(`${API_ENDPOINTS.SERVER_BACKUPS}?server_id=${this.serverId}`);
            const backupList = document.getElementById('backup-list');
            
            if (!backupList) return;

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
                btn.addEventListener('click', () => this.restoreBackup(btn.dataset.name));
            });

            document.querySelectorAll('.delete-btn').forEach(btn => {
                btn.addEventListener('click', () => this.deleteBackup(btn.dataset.name));
            });

            eventBus.emit(EVENTS.BACKUPS_UPDATED, backups);

        } catch (error) {
            console.error('Chyba při načítání záloh:', error);
            eventBus.emit(EVENTS.ERROR_OCCURRED, {
                module: 'backups',
                error
            });
        }
    }

    /**
     * Vytvoří novou zálohu
     */
    async createBackup() {
        const backupBtn = document.getElementById('create-backup-btn');
        const nameInput = document.getElementById('backup-name');
        
        if (!backupBtn) return;

        const originalText = backupBtn.innerHTML;
        backupBtn.disabled = true;

        try {
            // Zkontroluj zda je server vypnutý
            const statusData = await api.getServerStatus(this.serverId);
            if (statusData.status === 'running') {
                eventBus.emit(EVENTS.NOTIFICATION_SHOW, {
                    type: 'warning',
                    message: 'Server musí být vypnutý pro vytvoření zálohy'
                });
                return;
            }

            const result = await api.post(API_ENDPOINTS.SERVER_BACKUP_CREATE, {
                server_id: this.serverId,
                name: nameInput?.value.trim() || undefined
            });

            if (result.success) {
                await Promise.all([this.loadBackups(), this.updateDiskUsage()]);
                eventBus.emit(EVENTS.NOTIFICATION_SHOW, {
                    type: 'success',
                    message: 'Záloha vytvořena'
                });
                
                if (nameInput) {
                    nameInput.value = '';
                }
            } else {
                throw new Error(result.error || 'Neznámá chyba');
            }

        } catch (error) {
            console.error('Chyba při vytváření zálohy:', error);
            eventBus.emit(EVENTS.NOTIFICATION_SHOW, {
                type: 'error',
                message: `Chyba: ${error.message}`
            });
        } finally {
            backupBtn.disabled = false;
            backupBtn.innerHTML = originalText;
        }
    }

    /**
     * Obnoví zálohu
     * @param {string} backupName 
     */
    async restoreBackup(backupName) {
        if (!confirm(`Opravdu chcete obnovit zálohu "${backupName}"? Současný svět bude přepsán.`)) {
            return;
        }

        try {
            const result = await api.post(API_ENDPOINTS.SERVER_BACKUP_RESTORE, {
                server_id: this.serverId,
                name: backupName
            });

            if (result.success) {
                eventBus.emit(EVENTS.NOTIFICATION_SHOW, {
                    type: 'success',
                    message: 'Záloha byla úspěšně obnovena. Můžete spustit server.'
                });
            } else {
                throw new Error(result.error || 'Neznámá chyba');
            }

        } catch (error) {
            console.error('Chyba při obnovování zálohy:', error);
            eventBus.emit(EVENTS.NOTIFICATION_SHOW, {
                type: 'error',
                message: `Chyba při obnovování zálohy: ${error.message}`
            });
        }
    }

    /**
     * Smaže zálohu
     * @param {string} backupName 
     */
    async deleteBackup(backupName) {
        if (!confirm(`Smazat zálohu "${backupName}"?`)) return;

        try {
            const result = await api.post(API_ENDPOINTS.SERVER_BACKUP_DELETE, {
                server_id: this.serverId,
                name: backupName
            });

            if (result.success) {
                await Promise.all([this.loadBackups(), this.updateDiskUsage()]);
                eventBus.emit(EVENTS.NOTIFICATION_SHOW, {
                    type: 'success',
                    message: 'Záloha smazána'
                });
            } else {
                throw new Error(result.error || 'Neznámá chyba');
            }

        } catch (error) {
            console.error('Chyba při mazání zálohy:', error);
            eventBus.emit(EVENTS.NOTIFICATION_SHOW, {
                type: 'error',
                message: `Chyba: ${error.message}`
            });
        }
    }

    /**
     * Aktualizuje využití disku
     */
    async updateDiskUsage() {
        try {
            const data = await api.get(`${API_ENDPOINTS.SERVER_DISK_USAGE}?server_id=${this.serverId}`);
            
            const serverBar = document.getElementById('server-usage-bar');
            const backupBar = document.getElementById('backup-usage-bar');

            if (serverBar) serverBar.style.width = `${data.server_percent}%`;
            if (backupBar) backupBar.style.width = `${data.backup_percent}%`;

            const usedPercent = Math.min(100, data.server_percent + data.backup_percent);
            document.documentElement.style.setProperty('--used-percent', `${usedPercent}%`);

            this.updateTextElement('server-usage-text', 
                `${formatSize(data.server_size)} (${data.server_percent.toFixed(1)}%)`);
            this.updateTextElement('backup-usage-text', 
                `${formatSize(data.backup_size)} (${data.backup_percent.toFixed(1)}%) - ${data.backup_count} záloh`);
            this.updateTextElement('total-usage-text', 
                `${formatSize(data.total_size)} / ${formatSize(data.max_capacity)}`);
            this.updateTextElement('backup-count', data.backup_count.toString());

            if (serverBar) serverBar.title = `Server: ${data.server_percent.toFixed(1)}%`;
            if (backupBar) backupBar.title = `Zálohy: ${data.backup_percent.toFixed(1)}%`;

        } catch (error) {
            console.error('Chyba při načítání využití disku:', error);
            eventBus.emit(EVENTS.ERROR_OCCURRED, {
                module: 'backups',
                error
            });
        }
    }

    /**
     * Spustí automatickou aktualizaci využití disku
     */
    startDiskUsageUpdate() {
        if (this.diskUpdateInterval) {
            clearInterval(this.diskUpdateInterval);
        }
        
        this.diskUpdateInterval = setInterval(() => {
            this.updateDiskUsage();
        }, 60000);
    }

    /**
     * Zastaví automatickou aktualizaci využití disku
     */
    stopDiskUsageUpdate() {
        if (this.diskUpdateInterval) {
            clearInterval(this.diskUpdateInterval);
            this.diskUpdateInterval = null;
        }
    }

    /**
     * Aktualizuje textový element
     * @param {string} elementId 
     * @param {string} value 
     */
    updateTextElement(elementId, value) {
        const element = document.getElementById(elementId);
        if (element) {
            element.textContent = value;
        }
    }

    /**
     * Vyčistí zdroje
     */
    cleanup() {
        this.stopDiskUsageUpdate();
    }
}

// Export instance
export const backupManager = new BackupManager();
