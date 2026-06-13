// Modul pro správu administrátorů serveru
import { API_ENDPOINTS } from '../core/constants.js';
import { eventBus, EVENTS } from '../core/event-bus.js';
import { getCurrentServerId, isAdmin } from '../core/utils.js';

class AdminManager {
    constructor() {
        this.serverId = getCurrentServerId();
    }

    /**
     * Inicializuje správu administrátorů
     */
    async init() {
        if (!this.serverId) {
            console.error('Nelze inicializovat AdminManager - chybějící serverId');
            return;
        }

        // Zkontrolovat, zda je uživatel owner
        await this.checkOwnerAccess();
        this.setupEventListeners();
        await this.loadAdminList();
    }

    /**
     * Zkontroluje, zda je uživatel owner serveru
     */
    async checkOwnerAccess() {
        try {
            const response = await fetch(`${API_ENDPOINTS.SERVER_ADMINS}?server_id=${this.serverId}`);
            const data = await response.json();

            if (data.is_owner) {
                const panel = document.getElementById('admin-management-panel');
                if (panel) {
                    panel.style.display = 'block';
                }
            } else {
                console.log('Uživatel není owner, skrývám správu adminů');
            }
        } catch (error) {
            console.error('Chyba při kontrole owner práv:', error);
        }
    }

    /**
     * Nastaví event listenery
     */
    setupEventListeners() {
        // Přidání admina
        const addBtn = document.getElementById('add-admin-btn');
        if (addBtn) {
            addBtn.addEventListener('click', () => this.addAdmin());
        }

        // Enter v inputu
        const emailInput = document.getElementById('admin-email-input');
        if (emailInput) {
            emailInput.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') {
                    this.addAdmin();
                }
            });
        }
    }

    /**
     * Načte seznam administrátorů
     */
    async loadAdminList() {
        try {
            const response = await fetch(`${API_ENDPOINTS.SERVER_ADMINS}?server_id=${this.serverId}`);
            const data = await response.json();

            if (!data.is_owner) {
                return;
            }

            const list = document.getElementById('admin-list');
            if (!list) return;

            list.innerHTML = '';

            if (!data.admins || data.admins.length === 0) {
                list.innerHTML = '<li class="list-group-item text-muted">Žádní administrátoři</li>';
                return;
            }

            data.admins.forEach(admin => {
                const li = document.createElement('li');
                li.className = 'list-group-item d-flex justify-content-between align-items-center';
                li.innerHTML = `
                    <div>
                        ${admin.email}
                        ${admin.is_owner ? '<span class="badge badge-warning ml-2">Owner</span>' : ''}
                    </div>
                    ${!admin.is_owner ? `
                        <button class="btn btn-sm btn-danger remove-admin-btn" data-user-id="${admin.user_id}">
                            <i class="fas fa-trash"></i> Odebrat
                        </button>
                    ` : ''}
                `;
                list.appendChild(li);
            });

            // Event listenery pro tlačítka odebrání
            document.querySelectorAll('.remove-admin-btn').forEach(btn => {
                btn.addEventListener('click', (e) => {
                    const userId = e.target.closest('.remove-admin-btn').dataset.userId;
                    this.removeAdmin(userId);
                });
            });

            eventBus.emit(EVENTS.ADMIN_LIST_UPDATED, data.admins);

        } catch (error) {
            console.error('Chyba při načítání adminů:', error);
            const list = document.getElementById('admin-list');
            if (list) {
                list.innerHTML = '<li class="list-group-item text-danger">Chyba při načítání seznamu adminů</li>';
            }
        }
    }

    /**
     * Přidá nového admina
     */
    async addAdmin() {
        const emailInput = document.getElementById('admin-email-input');
        const email = emailInput?.value.trim();

        if (!email) {
            eventBus.emit(EVENTS.NOTIFICATION_SHOW, {
                type: 'warning',
                message: 'Zadejte email admina'
            });
            return;
        }

        const addBtn = document.getElementById('add-admin-btn');
        const originalText = addBtn.innerHTML;

        try {
            addBtn.disabled = true;
            addBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Přidávám...';

            const response = await fetch(`${API_ENDPOINTS.SERVER_ADMINS_ADD}?server_id=${this.serverId}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email })
            });

            const result = await response.json();

            if (result.success) {
                eventBus.emit(EVENTS.NOTIFICATION_SHOW, {
                    type: 'success',
                    message: 'Admin byl úspěšně přidán'
                });

                // Vyčistit input
                if (emailInput) {
                    emailInput.value = '';
                }

                // Načíst aktualizovaný seznam
                await this.loadAdminList();

            } else {
                throw new Error(result.message || 'Nepodařilo se přidat admina');
            }

        } catch (error) {
            console.error('Chyba při přidávání admina:', error);
            eventBus.emit(EVENTS.NOTIFICATION_SHOW, {
                type: 'error',
                message: error.message || 'Chyba při přidávání admina'
            });
        } finally {
            addBtn.disabled = false;
            addBtn.innerHTML = originalText;
        }
    }

    /**
     * Odebere admina
     * @param {number} userId 
     */
    async removeAdmin(userId) {
        if (!confirm('Opravdu chcete odebrat tohoto admina?')) {
            return;
        }

        const removeBtn = document.querySelector(`.remove-admin-btn[data-user-id="${userId}"]`);
        const originalHtml = removeBtn ? removeBtn.innerHTML : '';

        try {
            if (removeBtn) {
                removeBtn.disabled = true;
                removeBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
            }

            const response = await fetch(`${API_ENDPOINTS.SERVER_ADMINS_REMOVE}?server_id=${this.serverId}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ user_id: parseInt(userId) })
            });

            const result = await response.json();

            if (result.success) {
                eventBus.emit(EVENTS.NOTIFICATION_SHOW, {
                    type: 'success',
                    message: 'Admin byl úspěšně odebrán'
                });

                await this.loadAdminList();

            } else {
                throw new Error(result.message || 'Chyba při odebírání admina');
            }

        } catch (error) {
            console.error('Chyba při odebírání admina:', error);
            eventBus.emit(EVENTS.NOTIFICATION_SHOW, {
                type: 'error',
                message: error.message || 'Chyba při odebírání admina'
            });

            if (removeBtn) {
                removeBtn.disabled = false;
                removeBtn.innerHTML = originalHtml;
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
export const adminManager = new AdminManager();