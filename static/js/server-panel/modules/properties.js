import { API_ENDPOINTS } from '../core/constants.js';
import { eventBus, EVENTS } from '../core/event-bus.js';
import { getCurrentServerId } from '../core/utils.js';

const PROPERTY_GROUPS = [
    {
        title: 'Herni pravidla',
        fields: [
            ['motd', 'MOTD'],
            ['gamemode', 'Herni mod'],
            ['difficulty', 'Obtiznost'],
            ['hardcore', 'Hardcore'],
            ['force-gamemode', 'Vynutit herni mod'],
            ['pvp', 'PvP']
        ]
    },
    {
        title: 'Hraci a pristup',
        fields: [
            ['max-players', 'Max hracu'],
            ['online-mode', 'Online mode'],
            ['white-list', 'Whitelist'],
            ['enforce-whitelist', 'Vynutit whitelist'],
            ['player-idle-timeout', 'AFK timeout']
        ]
    },
    {
        title: 'Vykon a svet',
        fields: [
            ['view-distance', 'View distance'],
            ['simulation-distance', 'Simulation distance'],
            ['spawn-protection', 'Spawn protection'],
            ['allow-flight', 'Povolit flight'],
            ['enable-command-block', 'Command blocky'],
            ['level-seed', 'Seed sveta'],
            ['level-name', 'Slozka sveta']
        ]
    }
];

const PROPERTY_TOOLTIPS = {
    'motd': 'Nazev serveru zobrazeny v seznamu serveru.',
    'max-players': 'Maximalni pocet hracu.',
    'difficulty': 'Obtiznost (peaceful, easy, normal, hard).',
    'gamemode': 'Vychozi herni mod (survival, creative, adventure, spectator).',
    'force-gamemode': 'Zda se hracum pri pripojeni vynuti vychozi mod.',
    'pvp': 'Zapnuti/vypnuti PvP.',
    'view-distance': 'Vzdalenost vykreslovani chunku.',
    'simulation-distance': 'Vzdalenost simulace entit a redstonu.',
    'player-idle-timeout': 'Automaticke odpojeni AFK hracu.',
    'spawn-protection': 'Ochrana spawnu pred stavenim.',
    'white-list': 'Zapnuti whitelistu.',
    'enforce-whitelist': 'Okamzite vykopnuti hracu mimo whitelist.',
    'online-mode': 'Overovani Mojang uctu.',
    'allow-flight': 'Povoleni letani (nutne pro nektere pluginy a mody).',
    'enable-command-block': 'Povoleni command blocku.',
    'level-seed': 'Seed sveta (pred vytvorenim sveta).',
    'level-name': 'Nazev slozky sveta.'
};

class PropertiesManager {
    constructor() {
        this.serverId = getCurrentServerId();
        this.fields = {};
        this.properties = {};
    }

    async init() {
        if (!this.serverId) {
            console.error('Nelze inicializovat PropertiesManager - chybejici serverId');
            return;
        }

        this.setupEventListeners();
        await this.loadProperties();
    }

    setupEventListeners() {
        document.getElementById('server-properties-save')?.addEventListener('click', () => this.saveProperties());
        document.getElementById('server-properties-reload')?.addEventListener('click', () => this.loadProperties());
    }

    async loadProperties() {
        const form = document.getElementById('server-properties-form');
        const status = document.getElementById('server-properties-status');
        if (!form) return;

        this.setStatus('Nacitam nastaveni...', 'info');

        try {
            const response = await fetch(`${API_ENDPOINTS.SERVER_PROPERTIES}?server_id=${this.serverId}`);
            const data = await response.json();

            if (!response.ok || !data.success) {
                throw new Error(data.error || `HTTP ${response.status}`);
            }

            this.fields = data.fields || {};
            this.properties = data.properties || {};
            this.renderForm();
            this.setMeta(data);
            this.setStatus('Nastaveni nacteno', 'success');
        } catch (error) {
            console.error('Chyba pri nacitani server.properties:', error);
            form.innerHTML = `
                <div class="properties-empty">
                    <i class="fas fa-file-circle-exclamation"></i>
                    <strong>server.properties se nepodarilo nacist</strong>
                    <span>${this.escapeHtml(error.message)}</span>
                </div>
            `;
            if (status) this.setStatus('Chyba pri nacitani nastaveni', 'error');
        }
    }

    renderForm() {
        const form = document.getElementById('server-properties-form');
        if (!form) return;

        form.innerHTML = PROPERTY_GROUPS.map(group => {
            const fields = group.fields
                .filter(([key]) => this.fields[key])
                .map(([key, label]) => this.renderField(key, label))
                .join('');

            if (!fields) return '';

            return `
                <fieldset class="properties-group">
                    <legend>${group.title}</legend>
                    <div class="properties-grid">${fields}</div>
                </fieldset>
            `;
        }).join('');
    }

    renderField(key, label) {
        const spec = this.fields[key];
        const value = this.properties[key] ?? spec.default ?? '';

        if (spec.type === 'bool') {
            return `
                <label class="property-toggle" title="${this.escapeHtml(PROPERTY_TOOLTIPS[key] || key)}">
                    <input type="checkbox" data-property-key="${key}" ${value === 'true' ? 'checked' : ''}>
                    <span>
                        <strong>${label}</strong>
                        <small>${key}</small>
                    </span>
                </label>
            `;
        }

        if (spec.type === 'select') {
            const options = (spec.choices || []).map(choice => `
                <option value="${choice}" ${choice === value ? 'selected' : ''}>${choice}</option>
            `).join('');
            return `
                <label class="property-field" title="${this.escapeHtml(PROPERTY_TOOLTIPS[key] || key)}">
                    <span>${label}</span>
                    <select class="form-control" data-property-key="${key}">${options}</select>
                    <small>${key}</small>
                </label>
            `;
        }

        const attrs = spec.type === 'int'
            ? `type="number" min="${spec.min}" max="${spec.max}" step="1"`
            : 'type="text"';

        return `
            <label class="property-field" title="${this.escapeHtml(PROPERTY_TOOLTIPS[key] || key)}">
                <span>${label}</span>
                <input class="form-control" ${attrs} value="${this.escapeHtml(value)}" data-property-key="${key}">
                <small>${key}</small>
            </label>
        `;
    }

    async saveProperties() {
        const saveBtn = document.getElementById('server-properties-save');
        const original = saveBtn?.innerHTML;
        if (saveBtn) {
            saveBtn.disabled = true;
            saveBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Ukladam...';
        }

        try {
            const properties = {};
            document.querySelectorAll('[data-property-key]').forEach(input => {
                const key = input.dataset.propertyKey;
                properties[key] = input.type === 'checkbox' ? input.checked : input.value;
            });

            const response = await fetch(API_ENDPOINTS.SERVER_PROPERTIES, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    server_id: this.serverId,
                    properties
                })
            });
            const data = await response.json();

            if (!response.ok || !data.success) {
                throw new Error(data.error || `HTTP ${response.status}`);
            }

            this.setStatus('Nastaveni ulozeno. Vetsina zmen se projevi po restartu serveru.', 'success');
            eventBus.emit(EVENTS.NOTIFICATION_SHOW, {
                type: 'success',
                message: 'server.properties ulozen'
            });
        } catch (error) {
            console.error('Chyba pri ukladani server.properties:', error);
            this.setStatus(`Chyba: ${error.message}`, 'error');
            eventBus.emit(EVENTS.NOTIFICATION_SHOW, {
                type: 'error',
                message: `Nastaveni se nepodarilo ulozit: ${error.message}`
            });
        } finally {
            if (saveBtn) {
                saveBtn.disabled = false;
                saveBtn.innerHTML = original;
            }
        }
    }

    setMeta(data) {
        const meta = document.getElementById('server-properties-meta');
        if (!meta) return;

        const updated = data.updated_at ? `Aktualizovano: ${data.updated_at}` : '';
        meta.textContent = [updated, data.path].filter(Boolean).join(' | ');
    }

    setStatus(message, type = 'info') {
        const status = document.getElementById('server-properties-status');
        if (!status) return;
        status.textContent = message;
        status.className = `properties-status ${type}`;
    }

    escapeHtml(value) {
        return String(value)
            .replaceAll('&', '&amp;')
            .replaceAll('<', '&lt;')
            .replaceAll('>', '&gt;')
            .replaceAll('"', '&quot;');
    }
}

export const propertiesManager = new PropertiesManager();
