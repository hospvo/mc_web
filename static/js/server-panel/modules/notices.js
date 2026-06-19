// Modul pro správu oznámení
import { API_ENDPOINTS } from '../core/constants.js';
import { eventBus, EVENTS } from '../core/event-bus.js';
import { getCurrentServerId, isAdmin, formatNoticeContent } from '../core/utils.js';

class NoticesManager {
    constructor() {
        this.serverId = getCurrentServerId();
        this.currentNotices = [];
    }

    /**
     * Inicializuje správu oznámení
     */
    async init() {
        if (!this.serverId) {
            console.error('Nelze inicializovat NoticesManager - chybějící serverId');
            return;
        }

        this.setupEventListeners();
        await this.loadNotices();
        this.initTextTools();
        
        // Zkontrolovat admin přístup
        await this.checkAdminAccess();
    }

    /**
     * Nastaví event listenery
     */
    setupEventListeners() {
        const createBtn = document.getElementById('create-notice-btn');
        if (createBtn) createBtn.addEventListener('click', () => this.createNotice());

        const noticesContainer = document.getElementById('notices-container');
        if (noticesContainer) {
            noticesContainer.addEventListener('click', async (e) => this.handleNoticeClick(e));
        }
    }

    /**
     * Zpracuje kliknutí na oznámení
     * @param {Event} e 
     */
    async handleNoticeClick(e) {
        const noticeId = e.target.closest('[data-notice-id]')?.dataset.noticeId;
        if (!noticeId) return;

        if (e.target.closest('.edit-notice-btn')) this.editNotice(noticeId);
        if (e.target.closest('.delete-notice-btn')) this.deleteNotice(noticeId);
        if (e.target.closest('.toggle-notice-btn')) {
            const isActive = e.target.closest('.toggle-notice-btn').dataset.active === 'true';
            this.toggleNotice(noticeId, !isActive);
        }
        if (e.target.closest('.save-edit-notice-btn')) this.saveNoticeEdit(noticeId);
        if (e.target.closest('.cancel-edit-notice-btn')) this.cancelNoticeEdit(noticeId);
    }

    /**
     * Inicializuje textové nástroje
     */
    initTextTools() {
        const toolbar = document.querySelector('.text-toolbar');
        if (!toolbar) return;

        toolbar.addEventListener('click', (e) => {
            const btn = e.target.closest('.text-tool-btn');
            if (!btn) return;

            const tag = btn.dataset.tag;
            const textarea = document.getElementById('notice-content');
            if (textarea) this.applyTextFormatting(tag, textarea);
        });
    }

    /**
     * Aplikuje textové formátování
     * @param {string} tag 
     * @param {HTMLTextAreaElement} textarea 
     */
    applyTextFormatting(tag, textarea) {
        const start = textarea.selectionStart;
        const end = textarea.selectionEnd;
        const selected = textarea.value.substring(start, end);

        const formats = {
            'bold': { prefix: '**', suffix: '**', placeholder: 'tučný text' },
            'italic': { prefix: '*', suffix: '*', placeholder: 'kurzíva' },
            'underline': { prefix: '<u>', suffix: '</u>', placeholder: 'podtržený text' },
            'code': { prefix: '`', suffix: '`', placeholder: 'kód' },
            'link': { prefix: '[', suffix: '](https://example.com)', placeholder: 'odkaz' },
            'list-ul': { prefix: '- ', suffix: '', placeholder: 'položka seznamu' },
            'list-ol': { prefix: '1. ', suffix: '', placeholder: 'položka seznamu' }
        };

        const fmt = formats[tag];
        if (!fmt) return;

        const newText = fmt.prefix + (selected || fmt.placeholder) + fmt.suffix;
        textarea.value = textarea.value.substring(0, start) + newText + textarea.value.substring(end);

        const cursorPos = start + fmt.prefix.length;
        if (!selected) {
            textarea.setSelectionRange(cursorPos, cursorPos + fmt.placeholder.length);
        } else {
            textarea.setSelectionRange(cursorPos + selected.length + fmt.suffix.length, 
                                       cursorPos + selected.length + fmt.suffix.length);
        }

        textarea.focus();
    }

    /**
     * Zkontroluje admin přístup
     */
    async checkAdminAccess() {
        const isUserAdmin = await isAdmin(this.serverId);
        const panel = document.getElementById('notice-management-panel');
        
        if (panel && isUserAdmin) {
            panel.style.display = 'block';
        }
    }

    /**
     * Načte oznámení
     */
    async loadNotices() {
        try {
            const response = await fetch(`${API_ENDPOINTS.NOTICES}?server_id=${this.serverId}`);
            if (!response.ok) throw new Error('Chyba při načítání oznámení');

            const notices = await response.json();
            this.currentNotices = notices;

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
                noticeElement.setAttribute('data-notice-id', notice.id);

                noticeElement.innerHTML = `
                    <div class="notice-header">
                        <div>
                            <h5 class="notice-title">
                                ${notice.is_pinned ? '<i class="fas fa-thumbtack"></i>' : ''}
                                ${notice.title}
                                <span class="notice-badge badge-${notice.type}">
                                    ${this.getNoticeTypeLabel(notice.type)}
                                </span>
                                ${!notice.is_active ? '<span class="badge badge-secondary">Skryté</span>' : ''}
                            </h5>
                            <div class="notice-meta">
                                ${notice.author} • ${notice.created_at}
                                ${notice.updated_at ? ` (upraveno ${notice.updated_at})` : ''}
                            </div>
                        </div>
                    </div>
                    <div class="notice-content formatted">
                        ${formatNoticeContent(notice.content)}
                    </div>
                    ${notice.can_edit ? `
                        <div class="notice-actions">
                            <button class="btn btn-sm btn-primary edit-notice-btn" data-notice-id="${notice.id}">
                                <i class="fas fa-edit"></i> Upravit
                            </button>
                            <button class="btn btn-sm btn-danger delete-notice-btn" data-notice-id="${notice.id}">
                                <i class="fas fa-trash"></i> Smazat
                            </button>
                            <button class="btn btn-sm btn-secondary toggle-notice-btn" 
                                    data-notice-id="${notice.id}" 
                                    data-active="${notice.is_active}">
                                <i class="fas ${notice.is_active ? 'fa-eye-slash' : 'fa-eye'}"></i> 
                                ${notice.is_active ? 'Skrýt' : 'Zobrazit'}
                            </button>
                        </div>
                    ` : ''}
                `;
                container.appendChild(noticeElement);
            });

            eventBus.emit(EVENTS.NOTICES_UPDATED, notices);

        } catch (error) {
            console.error('Chyba při načítání oznámení:', error);
            const container = document.getElementById('notices-container');
            if (container) {
                container.innerHTML = '<div class="text-danger">Chyba při načítání oznámení</div>';
            }
        }
    }

    /**
     * Vytvoří nové oznámení
     */
    async createNotice() {
        const title = document.getElementById('notice-title')?.value.trim();
        const content = document.getElementById('notice-content')?.value.trim();
        const type = document.getElementById('notice-type')?.value;
        const isPinned = document.getElementById('notice-pinned')?.checked;

        if (!title || !content) {
            eventBus.emit(EVENTS.NOTIFICATION_SHOW, {
                type: 'warning',
                message: 'Vyplňte nadpis a obsah oznámení'
            });
            return;
        }

        const btn = document.getElementById('create-notice-btn');
        const original = btn.innerHTML;
        btn.disabled = true;
        btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Vytvářím...';

        try {
            const response = await fetch(API_ENDPOINTS.NOTICES_CREATE, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    server_id: this.serverId,
                    title,
                    content,
                    type,
                    is_pinned: isPinned
                })
            });

            const result = await response.json();
            if (!result.success) throw new Error(result.error || 'Neznámá chyba');

            eventBus.emit(EVENTS.NOTIFICATION_SHOW, {
                type: 'success',
                message: 'Oznámení bylo vytvořeno'
            });
            await this.loadNotices();

        } catch (error) {
            console.error('Chyba při vytváření oznámení:', error);
            eventBus.emit(EVENTS.NOTIFICATION_SHOW, {
                type: 'error',
                message: `Chyba: ${error.message}`
            });
        } finally {
            btn.disabled = false;
            btn.innerHTML = original;
        }
    }

    /**
     * Upraví oznámení
     * @param {string} noticeId 
     */
    async editNotice(noticeId) {
        const notice = this.currentNotices.find(n => n.id == noticeId);
        if (!notice) return;

        // Odstranit existující editovací formuláře
        document.querySelectorAll('.edit-notice-form').forEach(f => f.remove());
        
        const original = document.querySelector(`[data-notice-id="${noticeId}"]`);
        if (!original) return;

        const editForm = document.createElement('div');
        editForm.className = 'edit-notice-form';
        editForm.innerHTML = `
            <div class="card border-primary">
                <div class="card-header bg-primary text-white">
                    <h6><i class="fas fa-edit"></i> Úprava oznámení</h6>
                </div>
                <div class="card-body">
                    <input type="text" class="form-control mb-2 edit-notice-title" value="${notice.title}">
                    
                    <div class="text-toolbar mb-2">
                        <button type="button" class="btn btn-sm btn-outline-secondary text-tool-btn" data-tag="bold" title="Tu&#269;n&#233;" aria-label="Tu&#269;n&#233;"><i class="fas fa-bold"></i></button>
                        <button type="button" class="btn btn-sm btn-outline-secondary text-tool-btn" data-tag="italic" title="Kurz&#237;va" aria-label="Kurz&#237;va"><i class="fas fa-italic"></i></button>
                        <button type="button" class="btn btn-sm btn-outline-secondary text-tool-btn" data-tag="underline" title="Podtr&#382;en&#237;" aria-label="Podtr&#382;en&#237;"><i class="fas fa-underline"></i></button>
                        <button type="button" class="btn btn-sm btn-outline-secondary text-tool-btn" data-tag="code" title="K&#243;d" aria-label="K&#243;d"><i class="fas fa-code"></i></button>
                        <button type="button" class="btn btn-sm btn-outline-secondary text-tool-btn" data-tag="link" title="Vlo&#382;it odkaz" aria-label="Vlo&#382;it odkaz"><i class="fas fa-link"></i></button>
                    </div>

                    <textarea class="form-control mb-3 edit-notice-content" rows="5">${notice.content}</textarea>

                    <select class="form-control mb-2 edit-notice-type">
                        <option value="info" ${notice.type === 'info' ? 'selected' : ''}>ℹ️ Informace</option>
                        <option value="warning" ${notice.type === 'warning' ? 'selected' : ''}>⚠️ Varování</option>
                        <option value="important" ${notice.type === 'important' ? 'selected' : ''}>🔔 Důležité</option>
                        <option value="update" ${notice.type === 'update' ? 'selected' : ''}>🔄 Aktualizace</option>
                    </select>

                    <div class="form-check mb-2">
                        <input class="form-check-input edit-notice-pinned" type="checkbox" ${notice.is_pinned ? 'checked' : ''}> Připnout
                    </div>
                    <div class="form-check mb-3">
                        <input class="form-check-input edit-notice-active" type="checkbox" ${notice.is_active ? 'checked' : ''}> Aktivní
                    </div>

                    <button class="btn btn-success save-edit-notice-btn" data-notice-id="${noticeId}"><i class="fas fa-save"></i> Uložit</button>
                    <button class="btn btn-secondary cancel-edit-notice-btn" data-notice-id="${noticeId}"><i class="fas fa-times"></i> Zrušit</button>
                </div>
            </div>
        `;

        original.style.display = 'none';
        original.parentNode.insertBefore(editForm, original);
        this.initTextToolsForElement(editForm);
    }

    /**
     * Inicializuje textové nástroje pro konkrétní element
     * @param {HTMLElement} parent 
     */
    initTextToolsForElement(parent) {
        const toolbar = parent.querySelector('.text-toolbar');
        if (!toolbar) return;
        toolbar.addEventListener('click', e => {
            const btn = e.target.closest('.text-tool-btn');
            if (!btn) return;
            const tag = btn.dataset.tag;
            const textarea = parent.querySelector('textarea');
            this.applyTextFormatting(tag, textarea);
        });
    }

    /**
     * Uloží editaci oznámení
     * @param {string} noticeId 
     */
    async saveNoticeEdit(noticeId) {
        const title = document.querySelector(`.edit-notice-title`)?.value.trim();
        const content = document.querySelector(`.edit-notice-content`)?.value.trim();
        const type = document.querySelector(`.edit-notice-type`)?.value;
        const isPinned = document.querySelector(`.edit-notice-pinned`)?.checked;
        const isActive = document.querySelector(`.edit-notice-active`)?.checked;

        if (!title || !content) {
            eventBus.emit(EVENTS.NOTIFICATION_SHOW, {
                type: 'warning',
                message: 'Vyplňte všechna pole.'
            });
            return;
        }

        try {
            const response = await fetch(`${API_ENDPOINTS.NOTICES_UPDATE}/${noticeId}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    title,
                    content,
                    type,
                    is_pinned: isPinned,
                    is_active: isActive
                })
            });

            const result = await response.json();
            if (!result.success) throw new Error(result.error);

            await this.loadNotices();

        } catch (error) {
            console.error('Chyba při ukládání oznámení:', error);
            eventBus.emit(EVENTS.NOTIFICATION_SHOW, {
                type: 'error',
                message: `Chyba: ${error.message}`
            });
        }
    }

    /**
     * Zruší editaci oznámení
     * @param {string} noticeId 
     */
    cancelNoticeEdit(noticeId) {
        const form = document.querySelector('.edit-notice-form');
        const notice = document.querySelector(`[data-notice-id="${noticeId}"]`);
        if (form) form.remove();
        if (notice) notice.style.display = 'block';
    }

    /**
     * Smaže oznámení
     * @param {string} noticeId 
     */
    async deleteNotice(noticeId) {
        if (!confirm('Opravdu chcete smazat toto oznámení?')) return;
        
        try {
            const response = await fetch(`${API_ENDPOINTS.NOTICES_DELETE}/${noticeId}`, {
                method: 'DELETE'
            });

            const result = await response.json();
            if (!result.success) throw new Error(result.error);

            await this.loadNotices();

        } catch (error) {
            console.error('Chyba při mazání oznámení:', error);
            eventBus.emit(EVENTS.NOTIFICATION_SHOW, {
                type: 'error',
                message: `Chyba: ${error.message}`
            });
        }
    }

    /**
     * Přepne viditelnost oznámení
     * @param {string} noticeId 
     * @param {boolean} isActive 
     */
    async toggleNotice(noticeId, isActive) {
        try {
            const response = await fetch(`${API_ENDPOINTS.NOTICES_UPDATE}/${noticeId}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ is_active: isActive })
            });

            const result = await response.json();
            if (result.success) {
                await this.loadNotices();
            }
        } catch (error) {
            console.error('Chyba při přepínání oznámení:', error);
            eventBus.emit(EVENTS.NOTIFICATION_SHOW, {
                type: 'error',
                message: `Chyba: ${error.message}`
            });
        }
    }

    /**
     * Vrátí popisek pro typ oznámení
     * @param {string} type 
     * @returns {string}
     */
    getNoticeTypeLabel(type) {
        const labels = {
            info: 'Informace',
            warning: 'Varování',
            important: 'Důležité',
            update: 'Aktualizace',
            event: 'Event'
        };
        return labels[type] || type;
    }

    /**
     * Vyčistí zdroje
     */
    cleanup() {
        // Prozatím nic
    }
}

// Export instance
export const noticesManager = new NoticesManager();
