// Modul pro správu konzole serveru
import { api } from '../core/api.js';
import { eventBus, EVENTS } from '../core/event-bus.js';
import { getCurrentServerId } from '../core/utils.js';

class ConsoleManager {
    constructor() {
        this.serverId = getCurrentServerId();
        this.lastLogContent = "";
        this.lastServerStatus = "";
        this.logUpdateInterval = null;
    }

    /**
     * Inicializuje správu konzole
     */
    async init() {
        if (!this.serverId) {
            console.error('Nelze inicializovat ConsoleManager - chybějící serverId');
            return;
        }

        this.setupEventListeners();
        this.setupTabs();
        await this.loadLogs();
        this.startAutoUpdate();
    }

    /**
     * Nastaví základní event listenery
     */
    setupEventListeners() {
        // Odesílání příkazů
        const sendCommandBtn = document.getElementById('sendCommand');
        const consoleInput = document.getElementById('console-input');
        
        if (sendCommandBtn) {
            sendCommandBtn.addEventListener('click', () => this.sendCommand());
        }
        
        if (consoleInput) {
            consoleInput.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') this.sendCommand();
            });
        }

        // Tlačítko pro přidání nové záložky
        const addButton = document.getElementById('add-log-tab');
        if (addButton) {
            addButton.addEventListener('click', () => this.showOldLogsDialog());
        }
    }

    /**
     * Nastaví záložkový systém
     */
    setupTabs() {
        const tabContainer = document.querySelector('.console-tabs');
        const addButton = document.getElementById('add-log-tab');

        if (!tabContainer || !addButton) {
            console.warn("Konzolová sekce nebyla nalezena na této stránce.");
            return;
        }

        // Přepínání mezi záložkami
        tabContainer.addEventListener('click', e => {
            const tab = e.target.closest('.tab');
            if (!tab || tab.classList.contains('tab-add')) return;

            const target = tab.dataset.tab;
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            tab.classList.add('active');
            document.getElementById(`tab-${target}`).classList.add('active');
        });

        // Zavírání záložek
        tabContainer.addEventListener('click', e => {
            if (e.target.classList.contains('tab-close')) {
                const tab = e.target.closest('.tab');
                const tabId = tab.dataset.tab;
                const content = document.getElementById(`tab-${tabId}`);
                tab.remove();
                content?.remove();

                // Vrať se na hlavní konzoli
                document.querySelector('.tab[data-tab="main"]')?.classList.add('active');
                document.getElementById('tab-main')?.classList.add('active');
            }
        });

        // Zavření modálního dialogu
        document.getElementById('closeLogDialog')?.addEventListener('click', () => {
            document.getElementById('logDialog').classList.add('hidden');
        });
    }

    /**
     * Načte logy serveru
     */
    async loadLogs() {
        const logBox = document.getElementById('log-output');
        if (!logBox) return;

        const isAtBottom = logBox.scrollHeight - logBox.scrollTop - logBox.clientHeight < 50;

        try {
            // Zjištění stavu serveru
            const statusData = await api.getServerStatus(this.serverId);
            const currentStatus = statusData.status || "unknown";

            // Pokud došlo k vypnutí serveru -> smaž log
            if (currentStatus === "stopped" && this.lastServerStatus !== "stopped") {
                logBox.innerHTML = "";
                this.lastLogContent = "";
            }
            this.lastServerStatus = currentStatus;

            // Načtení logů
            const logData = await api.getServerLogs(this.serverId, 200);
            const newLog = logData.html || logData.text || "";

            // Aktualizuj jen pokud se obsah změnil
            if (newLog !== this.lastLogContent) {
                logBox.innerHTML = newLog;
                this.lastLogContent = newLog;
                if (isAtBottom) {
                    logBox.scrollTop = logBox.scrollHeight;
                }
            }

        } catch (error) {
            console.error("Chyba při načítání logů:", error);
            eventBus.emit(EVENTS.ERROR_OCCURRED, {
                module: 'console',
                error
            });
        }
    }

    /**
     * Odešle příkaz na server
     */
    async sendCommand() {
        const input = document.getElementById('console-input');
        const command = input?.value.trim();
        
        if (!command || !this.serverId) return;

        try {
            await api.sendCommand(this.serverId, command);
            input.value = '';
            
            // Počkej a načti nové logy
            setTimeout(() => this.loadLogs(), 1000);
            
        } catch (error) {
            console.error("Chyba při odesílání příkazu:", error);
            eventBus.emit(EVENTS.ERROR_OCCURRED, {
                module: 'console',
                error
            });
        }
    }

    /**
     * Zobrazí dialog s výběrem starých logů
     */
    async showOldLogsDialog() {
        try {
            const logs = await api.getOldLogs(this.serverId);
            const dialog = document.getElementById('logDialog');
            const listContainer = document.getElementById('logList');
            
            if (!dialog || !listContainer) return;

            listContainer.innerHTML = '';

            if (!logs.length) {
                listContainer.innerHTML = '<p style="color:#ccc;text-align:center;">Žádné staré logy nebyly nalezeny.</p>';
            } else {
                logs.forEach(file => {
                    const item = document.createElement('div');
                    item.className = 'log-item';
                    item.textContent = file;
                    item.addEventListener('click', async () => {
                        await this.openOldLog(file);
                        dialog.classList.add('hidden');
                    });
                    listContainer.appendChild(item);
                });
            }

            dialog.classList.remove('hidden');

        } catch (error) {
            console.error("Chyba při načítání starých logů:", error);
            eventBus.emit(EVENTS.ERROR_OCCURRED, {
                module: 'console',
                error
            });
        }
    }

    /**
     * Otevře starý log v nové záložce
     * @param {string} filename 
     */
    async openOldLog(filename) {
        try {
            const logData = await fetch(`/api/server/old-logs/view?server_id=${this.serverId}&filename=${encodeURIComponent(filename)}`)
                .then(r => r.json());

            const tabId = `old-${Date.now()}`;
            const tabContainer = document.querySelector('.console-tabs');

            if (!tabContainer) return;

            // Vytvoř novou záložku
            const tab = document.createElement('div');
            tab.className = 'tab';
            tab.dataset.tab = tabId;
            tab.innerHTML = `${filename} <span class="tab-close">✖</span>`;
            
            const addButton = document.getElementById('add-log-tab');
            tabContainer.insertBefore(tab, addButton);

            // Vytvoř obsah záložky
            const content = document.createElement('div');
            content.className = 'tab-content';
            content.id = `tab-${tabId}`;
            content.innerHTML = `<pre class="console-output">${logData.content}</pre>`;
            
            const tabContentContainer = document.getElementById('console-tab-content');
            if (tabContentContainer) {
                tabContentContainer.appendChild(content);
            }

            // Aktivuj novou záložku
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            tab.classList.add('active');
            content.classList.add('active');

        } catch (error) {
            console.error("Chyba při otevírání starého logu:", error);
            eventBus.emit(EVENTS.ERROR_OCCURRED, {
                module: 'console',
                error
            });
        }
    }

    /**
     * Spustí automatickou aktualizaci logů
     */
    startAutoUpdate() {
        // Zastav existující interval
        if (this.logUpdateInterval) {
            clearInterval(this.logUpdateInterval);
        }
        
        // Spustí nový interval (každých 4 sekundy)
        this.logUpdateInterval = setInterval(() => {
            this.loadLogs();
        }, 4000);
    }

    /**
     * Zastaví automatickou aktualizaci
     */
    stopAutoUpdate() {
        if (this.logUpdateInterval) {
            clearInterval(this.logUpdateInterval);
            this.logUpdateInterval = null;
        }
    }

    /**
     * Vyčistí zdroje
     */
    cleanup() {
        this.stopAutoUpdate();
    }
}

// Export instance
export const consoleManager = new ConsoleManager();