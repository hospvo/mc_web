// Modul pro správu přístupových kódů pro hráče
import { API_ENDPOINTS } from '../core/constants.js';
import { eventBus, EVENTS } from '../core/event-bus.js';
import { getCurrentServerId, isAdmin } from '../core/utils.js';

class PlayerAccessManager {
    constructor() {
        this.serverId = getCurrentServerId();
    }

    /**
     * Inicializuje správu přístupových kódů
     */
    async init() {
        if (!this.serverId) {
            console.error('Nelze inicializovat PlayerAccessManager - chybějící serverId');
            return;
        }

        // Zkontrolovat, zda je uživatel admin
        const userIsAdmin = await isAdmin(this.serverId);
        if (!userIsAdmin) {
            console.log('Uživatel není admin, skrývám správu přístupových kódů');
            return;
        }

        this.setupEventListeners();
        await this.loadAccessCodes();
        
        // Zobrazit panel
        const playerAccessPanel = document.getElementById('player-access-management');
        if (playerAccessPanel) {
            playerAccessPanel.style.display = 'block';
        }
    }

    /**
     * Nastaví event listenery
     */
    setupEventListeners() {
        // Generování nového kódu
        const generateBtn = document.getElementById('generate-code-btn');
        if (generateBtn) {
            generateBtn.addEventListener('click', () => this.generateAccessCode());
        }
    }

    /**
     * Načte seznam přístupových kódů
     */
    async loadAccessCodes() {
        try {
            const response = await fetch(`${API_ENDPOINTS.PLAYER_ACCESS_CODES}?server_id=${this.serverId}`);
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const codes = await response.json();
            const listContainer = document.getElementById('access-codes-list');
            
            if (!listContainer) return;

            listContainer.innerHTML = '';

            if (codes.length === 0) {
                listContainer.innerHTML = `
                    <div class="text-center text-muted py-4">
                        <i class="fas fa-key fa-2x mb-3" style="color: #6c757d;"></i>
                        <p class="mb-0">Žádné přístupové kódy</p>
                        <small>Vygenerujte první kód pomocí tlačítka výše</small>
                    </div>
                `;
                return;
            }

            // Rozdělit kódy na aktivní a neaktivní
            const activeCodes = codes.filter(code => code.is_active);
            const inactiveCodes = codes.filter(code => !code.is_active);

            // Zobrazit aktivní kódy
            if (activeCodes.length > 0) {
                activeCodes.forEach(code => {
                    const codeElement = this.createCodeElement(code, true);
                    listContainer.appendChild(codeElement);
                });
            } else {
                listContainer.innerHTML += `
                    <div class="text-center text-muted py-3">
                        <i class="fas fa-info-circle"></i>
                        Žádné aktivní kódy
                    </div>
                `;
            }

            // Zobrazit neaktivní kódy s rozbalovací sekcí
            if (inactiveCodes.length > 0) {
                const inactiveSection = this.createInactiveCodesSection(inactiveCodes);
                listContainer.appendChild(inactiveSection);
            }

            eventBus.emit(EVENTS.PLAYER_ACCESS_CODES_UPDATED, codes);

        } catch (error) {
            console.error('Chyba při načítání kódů:', error);
            const listContainer = document.getElementById('access-codes-list');
            if (listContainer) {
                listContainer.innerHTML = `
                    <div class="alert alert-danger">
                        <i class="fas fa-exclamation-triangle"></i> 
                        Chyba při načítání přístupových kódů: ${error.message}
                    </div>
                `;
            }
        }
    }

    /**
     * Vytvoří element pro kód
     * @param {Object} code 
     * @param {boolean} isActive 
     * @returns {HTMLElement}
     */
    createCodeElement(code, isActive) {
        const codeElement = document.createElement('div');
        codeElement.className = `access-code-item mb-2 p-3 border rounded ${isActive ? 'border-primary' : 'border-secondary'}`;
        codeElement.style.opacity = isActive ? '1' : '0.6';

        const expiresText = code.expires_at ?
            `Platný do: ${new Date(code.expires_at).toLocaleString('cs-CZ')}` :
            'Neomezená platnost';

        const usesText = code.max_uses ?
            `Použito: ${code.use_count}/${code.max_uses}` :
            `Použito: ${code.use_count}×`;

        const statusBadge = isActive ?
            '<span class="badge badge-success ml-2">Aktivní</span>' :
            '<span class="badge badge-secondary ml-2">Neaktivní</span>';

        codeElement.innerHTML = `
            <div class="d-flex justify-content-between align-items-center">
                <div class="flex-grow-1">
                    <div class="d-flex align-items-center mb-1">
                        <strong class="text-primary font-monospace" style="font-size: 1.1rem;">${code.code}</strong>
                        ${statusBadge}
                    </div>
                    <div class="text-muted small">
                        <div>${expiresText}</div>
                        <div>${usesText} • Vytvořen: ${new Date(code.created_at).toLocaleString('cs-CZ')}</div>
                    </div>
                </div>
                ${isActive ? `
                <button class="btn btn-sm revoke-code-btn ml-3" data-code-id="${code.id}">
                    <i class="fas fa-ban"></i> Zrušit
                </button>
                ` : ''}
            </div>
        `;

        // Přidat event listener pro aktivní kódy
        if (isActive) {
            const revokeBtn = codeElement.querySelector('.revoke-code-btn');
            revokeBtn.addEventListener('click', () => {
                this.revokeAccessCode(code.id, code.code);
            });
        }

        return codeElement;
    }

    /**
     * Vytvoří rozbalovací sekci neaktivních kódů
     * @param {Array} inactiveCodes 
     * @returns {HTMLElement}
     */
    createInactiveCodesSection(inactiveCodes) {
        const section = document.createElement('div');
        section.className = 'inactive-codes-section mt-4';

        const header = document.createElement('div');
        header.className = 'inactive-codes-header';
        header.innerHTML = `
            <h6>
                <i class="fas fa-history"></i>
                Neaktivní kódy (${inactiveCodes.length})
                <i class="fas fa-chevron-down toggle-icon"></i>
            </h6>
        `;

        const content = document.createElement('div');
        content.className = 'inactive-codes-content';
        content.style.display = 'none';

        // Přidat neaktivní kódy do obsahu
        inactiveCodes.forEach(code => {
            const codeElement = this.createCodeElement(code, false);
            content.appendChild(codeElement);
        });

        // Přidat funkci rozbalení/sbalení
        header.addEventListener('click', function () {
            const isExpanded = content.style.display === 'block';
            content.style.display = isExpanded ? 'none' : 'block';
            this.classList.toggle('expanded', !isExpanded);
        });

        section.appendChild(header);
        section.appendChild(content);

        return section;
    }

    /**
     * Vygeneruje nový přístupový kód
     */
    async generateAccessCode() {
        const expiresHours = document.getElementById('expires-hours').value;
        const maxUsesInput = document.getElementById('max-uses');
        const maxUses = maxUsesInput.value ? parseInt(maxUsesInput.value) : null;

        const generateBtn = document.getElementById('generate-code-btn');
        const originalText = generateBtn.innerHTML;

        try {
            generateBtn.disabled = true;
            generateBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Generuji...';

            const response = await fetch(API_ENDPOINTS.PLAYER_ACCESS_GENERATE, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    server_id: this.serverId,
                    expires_hours: parseInt(expiresHours),
                    max_uses: maxUses
                })
            });

            const result = await response.json();

            if (result.success) {
                const resultDiv = document.getElementById('generated-code-result');
                const expiresText = result.expires_at ?
                    `Platný do: ${new Date(result.expires_at).toLocaleString('cs-CZ')}` :
                    'Neomezená platnost';
                const usesText = result.max_uses ?
                    `Maximální počet použití: ${result.max_uses}` :
                    'Neomezený počet použití';

                resultDiv.innerHTML = `
                    <strong><i class="fas fa-key"></i> Nový přístupový kód:</strong><br>
                    <span style="font-size: 1.4rem; color: #28a745;">${result.code}</span><br>
                    <small>${expiresText}<br>${usesText}</small>
                `;
                resultDiv.style.display = 'block';

                // Skrýt výsledek po 30 sekundách
                setTimeout(() => {
                    resultDiv.style.display = 'none';
                }, 30000);

                // Resetovat formulář
                maxUsesInput.value = '';

                // Načíst aktualizovaný seznam kódů
                await this.loadAccessCodes();

                eventBus.emit(EVENTS.NOTIFICATION_SHOW, {
                    type: 'success',
                    message: 'Nový přístupový kód byl vygenerován'
                });

            } else {
                throw new Error(result.error || 'Neznámá chyba při generování kódu');
            }

        } catch (error) {
            console.error('Chyba při generování kódu:', error);
            eventBus.emit(EVENTS.NOTIFICATION_SHOW, {
                type: 'error',
                message: `Chyba při generování kódu: ${error.message}`
            });
        } finally {
            generateBtn.disabled = false;
            generateBtn.innerHTML = originalText;
        }
    }

    /**
     * Zruší platnost přístupového kódu
     * @param {number} codeId 
     * @param {string} codeText 
     */
    async revokeAccessCode(codeId, codeText) {
        if (!confirm(`Opravdu chcete zrušit přístupový kód "${codeText}"?\n\nTato akce je nevratná a kód již nebude možné použít.`)) {
            return;
        }

        const revokeBtn = document.querySelector(`.revoke-code-btn[data-code-id="${codeId}"]`);
        const originalHtml = revokeBtn ? revokeBtn.innerHTML : '';

        try {
            if (revokeBtn) {
                revokeBtn.disabled = true;
                revokeBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
            }

            const response = await fetch(API_ENDPOINTS.PLAYER_ACCESS_REVOKE, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ code_id: parseInt(codeId) })
            });

            const result = await response.json();

            if (result.success) {
                eventBus.emit(EVENTS.NOTIFICATION_SHOW, {
                    type: 'success',
                    message: `Přístupový kód "${codeText}" byl úspěšně zrušen`
                });

                await this.loadAccessCodes();

            } else {
                throw new Error(result.error || 'Neznámá chyba při rušení kódu');
            }

        } catch (error) {
            console.error('Chyba při rušení kódu:', error);
            eventBus.emit(EVENTS.NOTIFICATION_SHOW, {
                type: 'error',
                message: `Chyba při rušení kódu: ${error.message}`
            });

            if (revokeBtn) {
                revokeBtn.disabled = false;
                revokeBtn.innerHTML = originalHtml;
            }
        }
    }

    /**
     * Vyčistí zdroje
     */
    cleanup() {
        // Prozatím nic
    }
}

// Export instance
export const playerAccessManager = new PlayerAccessManager();