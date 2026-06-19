// Hlavní entry point pro server panel
import { statusManager } from './modules/status.js';
import { consoleManager } from './modules/console.js';
import { backupManager } from './modules/backups.js';
import { modpacksManager } from './modules/modpacks.js';
import { noticesManager } from './modules/notices.js';
import { ClientTools, ExpandableSections } from './ui/components.js';
import { notificationManager } from './ui/notifications.js';
import { getCurrentServerId } from './core/utils.js';
import { api } from './core/api.js';
import { API_ENDPOINTS } from './core/constants.js';
import { playerAccessManager } from './modules/player-access.js';
import { adminManager } from './modules/admin.js';
import { propertiesManager } from './modules/properties.js';

class ServerPanel {
    constructor() {
        this.serverId = getCurrentServerId();
        this.modules = [];
    }

    /**
     * Inicializuje celý server panel
     */
    async init() {
        if (!this.serverId) {
            console.error('Nelze inicializovat ServerPanel - chybějící serverId');
            return;
        }

        console.log(`Initializing Server Panel for server ${this.serverId}`);

        // Nastav základní UI
        this.setupBackButton();

        // Načti informace o serveru
        await this.loadServerInfo();

        // Načti build type a spravuj komponenty
        await this.manageServerComponents();

        // Nastav rozbalovací sekce TEĎ (před inicializací modulů!)
        ExpandableSections.init();

        // Inicializuj moduly
        await this.initModules();

    }

    /**
     * Nastaví tlačítko zpět na dashboard
     */
    setupBackButton() {
        const btn = document.getElementById('back-btn');
        if (btn) {
            btn.addEventListener('click', () => {
                window.location.href = '/dashboard';
            });
        }
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

        } catch (error) {
            console.error("Chyba při načítání informací o serveru:", error);
        }
    }

    /**
     * Spravuje komponenty podle typu serveru
     */
    async manageServerComponents() {
        try {
            const buildTypeResponse = await fetch(`/api/server/build-type?server_id=${this.serverId}`);
            const buildTypeData = await buildTypeResponse.json();
            const buildType = buildTypeData.build_type;

            localStorage.setItem(`server_${this.serverId}_build_type`, buildType);

            this.toggleComponentsByBuildType(buildType);

            // PO zobrazení komponentů inicializovat tlačítka
            this.setupManagementButtons();

        } catch (error) {
            console.error('Chyba při získávání build type:', error);
            const fallbackBuildType = localStorage.getItem(`server_${this.serverId}_build_type`) || 'UNKNOWN';
            this.toggleComponentsByBuildType(fallbackBuildType);
            this.setupManagementButtons(); // I při fallbacku
        }
    }

    /**
     * Zobrazí/skryje komponenty podle typu serveru
     * @param {string} buildType 
     */
    toggleComponentsByBuildType(buildType) {
        const modBuilds = ['FABRIC', 'FORGE', 'NEOFORGE', 'QUILT', 'BABRIC', 'BTA', 'JAVA_AGENT',
            'LEGACY_FABRIC', 'LITELOADER', 'MODLOADER', 'NILLOADER', 'ORNITHE', 'RIFT', 'RISUGAMI'];
        const pluginBuilds = ['BUKKIT', 'FOLIA', 'PAPER', 'PURPUR', 'SPIGOT', 'SPONGE'];

        const modsSection = document.querySelector('.mods-quickview');
        const pluginsSection = document.querySelector('.plugins-quickview');
        const clientToolsSection = document.querySelector('.client-tools-section');
        const modpacksSection = document.querySelector('.modpacks-management-section');

        const upperBuildType = buildType.toUpperCase();

        if (modBuilds.includes(upperBuildType)) {
            // Módový server
            if (modsSection) modsSection.style.display = 'block';
            if (pluginsSection) pluginsSection.style.display = 'none';
            if (clientToolsSection) clientToolsSection.style.display = 'block';
            if (modpacksSection) modpacksSection.style.display = 'block';

            // Načti módy a inicializuj nástroje
            this.loadModsQuickview();
            ClientTools.init(this.serverId);

        } else if (pluginBuilds.includes(upperBuildType)) {
            // Pluginový server
            if (modsSection) modsSection.style.display = 'none';
            if (pluginsSection) pluginsSection.style.display = 'block';
            if (clientToolsSection) clientToolsSection.style.display = 'none';
            if (modpacksSection) modpacksSection.style.display = 'none';

            // Načti pluginy
            this.loadQuickViewPlugins();

        } else {
            // Neznámý build
            console.warn('Neznámý typ buildu:', buildType);
            if (modsSection) modsSection.style.display = 'none';
            if (pluginsSection) pluginsSection.style.display = 'none';
            if (clientToolsSection) clientToolsSection.style.display = 'none';
            if (modpacksSection) modpacksSection.style.display = 'none';
        }
    }

    /**
     * Inicializuje jednotlivé moduly
     */
    async initModules() {
        const modulePromises = [];

        // Status manager
        if (document.getElementById('start-btn')) {
            modulePromises.push(statusManager.init());
            this.modules.push(statusManager);
        }

        // Console manager
        if (document.querySelector('.console-section')) {
            modulePromises.push(consoleManager.init());
            this.modules.push(consoleManager);
        }

        // Backup manager
        if (document.querySelector('.backup-panel')) {
            modulePromises.push(backupManager.init());
            this.modules.push(backupManager);
        }

        // Server properties manager
        if (document.getElementById('server-properties-panel')) {
            modulePromises.push(propertiesManager.init());
            this.modules.push(propertiesManager);
        }

        // Modpacks manager
        const modpacksSection = document.querySelector('.modpacks-management-section');
        if (modpacksSection && modpacksSection.style.display !== 'none') {
            modulePromises.push(modpacksManager.init());
            this.modules.push(modpacksManager);
        }

        // Notices manager
        if (document.querySelector('.player-info-section')) {
            modulePromises.push(noticesManager.init());
            this.modules.push(noticesManager);
        }

        // Player Access manager
        if (document.getElementById('player-access-management')) {
            modulePromises.push(playerAccessManager.init());
            this.modules.push(playerAccessManager);
        }

        // Admin manager
        if (document.getElementById('admin-management-panel')) {
            modulePromises.push(adminManager.init());
            this.modules.push(adminManager);
        }

        await Promise.all(modulePromises);
    }

    /**
     * Načte rychlý náhled modů
     */
    async loadModsQuickview() {
        try {
            const response = await fetch(`${API_ENDPOINTS.MODS_INSTALLED}?server_id=${this.serverId}`);

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const result = await response.json();

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

    /**
     * Načte rychlý náhled pluginů
     */
    async loadQuickViewPlugins() {
        try {
            const response = await fetch(`${API_ENDPOINTS.PLUGINS_INSTALLED}?server_id=${this.serverId}`);

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const result = await response.json();

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

            plugins.slice(0, 5).forEach(plugin => {
                const pluginItem = document.createElement('div');
                pluginItem.className = 'quickview-plugin-item';
                pluginItem.innerHTML = `
                    <span class="quickview-plugin-name">${plugin.display_name || plugin.name}</span>
                    <span class="quickview-plugin-version">v${plugin.version}</span>
                `;
                list.appendChild(pluginItem);
            });

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

    setupManagementButtons() {
        // Správa modů (pro mod servery)
        const manageModsBtn = document.getElementById('manage-mods-btn');
        if (manageModsBtn) {
            console.log('Setting up manage-mods button');
            manageModsBtn.addEventListener('click', () => {
                window.location.href = `/server/${this.serverId}/mods`;
            });
        }

        // Správa pluginů (pro plugin servery)
        const managePluginsBtn = document.getElementById('manage-plugins-btn');
        if (managePluginsBtn) {
            console.log('Setting up manage-plugins button');
            managePluginsBtn.addEventListener('click', () => {
                window.location.href = `/server/${this.serverId}/plugins`;
            });
        }
    }

    /**
     * Vyčistí všechny moduly
     */
    cleanup() {
        this.modules.forEach(module => {
            if (module.cleanup && typeof module.cleanup === 'function') {
                module.cleanup();
            }
        });
        this.modules = [];
    }
}

// Inicializace po načtení DOM
document.addEventListener('DOMContentLoaded', async () => {
    const serverPanel = new ServerPanel();
    await serverPanel.init();

    // Pro debugging
    window.serverPanel = serverPanel;
});
