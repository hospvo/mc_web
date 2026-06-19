// Modul pro správu modpacků
import { API_ENDPOINTS } from '../core/constants.js';
import { api } from '../core/api.js';
import { eventBus, EVENTS } from '../core/event-bus.js';
import { getCurrentServerId, formatSize } from '../core/utils.js';

class ModpacksManager {
    constructor() {
        this.serverId = getCurrentServerId();
        this.currentModpacks = [];
    }

    /**
     * Inicializuje správu modpacků
     */
    async init() {
        if (!this.serverId) {
            console.error('Nelze inicializovat ModpacksManager - chybějící serverId');
            return;
        }

        this.setupEventListeners();
        await this.loadAvailableMods();
        await this.loadModpacksList();
        this.setupExpandableSections();

        console.log('Modpacks management initialized for server', this.serverId);
    }

    /**
     * Nastaví event listenery
     */
    setupEventListeners() {
        // Vytvoření modpacku
        const createBtn = document.getElementById('create-modpack-btn');
        if (createBtn) {
            createBtn.addEventListener('click', () => this.createModpack());
        }

        // Delegované event listenery pro seznam modpacků
        const modpacksList = document.getElementById('modpacks-list');
        if (modpacksList) {
            modpacksList.addEventListener('click', (e) => this.handleModpackClick(e));
        }
    }

    /**
     * Zpracuje kliknutí na modpack
     * @param {Event} e 
     */
    handleModpackClick(e) {
        console.log('Modpack click event:', {
            target: e.target,
            classList: e.target.classList,
            dataset: e.target.dataset
        });

        // Editace modpacku
        const editBtn = e.target.closest('.edit-modpack-btn');
        if (editBtn) {
            const packId = editBtn.dataset.packId;
            console.log('Edit modpack clicked:', packId);
            this.toggleEditModpack(packId);
            e.stopPropagation();
            return;
        }

        // Smazat modpack
        const deleteBtn = e.target.closest('.delete-modpack-btn');
        if (deleteBtn) {
            const packId = deleteBtn.dataset.packId;
            console.log('Delete modpack clicked:', packId);
            this.deleteModpack(packId);
            e.stopPropagation();
            return;
        }

        // Uložení editace
        const saveBtn = e.target.closest('.save-edit-btn');
        if (saveBtn) {
            const packId = saveBtn.dataset.packId;
            console.log('Save edit clicked:', packId);
            this.saveModpackEdit(packId);
            e.stopPropagation();
            return;
        }

        // Zrušení editace
        const cancelBtn = e.target.closest('.cancel-edit-btn');
        if (cancelBtn) {
            const packId = cancelBtn.dataset.packId;
            console.log('Cancel edit clicked:', packId);
            this.cancelModpackEdit(packId);
            e.stopPropagation();
            return;
        }
    }

    // Uprav setupEventListeners
    setupEventListeners() {
        // Vytvoření modpacku
        const createBtn = document.getElementById('create-modpack-btn');
        if (createBtn) {
            createBtn.addEventListener('click', (e) => {
                console.log('Create modpack button clicked');
                this.createModpack();
            });
        }

        // Delegované event listenery pro seznam modpacků
        const modpacksList = document.getElementById('modpacks-list');
        if (modpacksList) {
            console.log('Setting up modpack list event delegation');
            modpacksList.addEventListener('click', (e) => this.handleModpackClick(e));
        } else {
            console.error('Modpacks list container not found!');
        }
    }

    /**
     * Nastaví rozbalovací sekce
     */
    setupExpandableSections() {
        const sectionHeaders = document.querySelectorAll('.section-header');

        sectionHeaders.forEach(header => {
            if (header.dataset.expandableReady === 'true') {
                return;
            }

            const section = header.dataset.section;
            const content = document.getElementById(`${section}-content`);
            if (!content) {
                return;
            }

            content.style.display = '';
            content.classList.remove('expanded');
            content.classList.add('collapsed');
            header.classList.remove('expanded');

            header.addEventListener('click', function () {
                const isExpanded = content.classList.contains('expanded');

                if (isExpanded) {
                    content.classList.remove('expanded');
                    content.classList.add('collapsed');
                    this.classList.remove('expanded');
                } else {
                    content.classList.remove('collapsed');
                    content.classList.add('expanded');
                    this.classList.add('expanded');
                }
            });
            header.dataset.expandableReady = 'true';
        });
    }

    /**
     * Načte dostupné módy pro checkboxy
     */
    async loadAvailableMods() {
        try {
            const response = await fetch(`${API_ENDPOINTS.MODS_INSTALLED}?server_id=${this.serverId}`);
            if (!response.ok) throw new Error('Chyba při načítání módů');

            const mods = await response.json();
            const checklist = document.getElementById('mods-checklist');
            if (!checklist) {
                console.warn('Element #mods-checklist nebyl nalezen');
                return;
            }

            checklist.innerHTML = '';

            if (mods.length === 0) {
                checklist.innerHTML = '<div class="text-muted">Na serveru nejsou nainstalovány žádné módy</div>';
                return;
            }

            mods.forEach(mod => {
                const modItem = document.createElement('div');
                modItem.className = 'mod-checkbox-item';
                modItem.innerHTML = `
                    <input type="checkbox" id="mod-${mod.id}" value="${mod.id}" class="mod-checkbox"
                           title="Vybrat mod" aria-label="Vybrat mod">
                    <label class="mod-info" for="mod-${mod.id}">
                        <span class="mod-name">${mod.display_name}</span>
                        <span class="mod-version">v${mod.version}</span>
                        ${mod.description ? `<div class="mod-description">${mod.description}</div>` : ''}
                    </label>
                `;
                checklist.appendChild(modItem);
            });

        } catch (error) {
            console.error('Chyba při načítání módů:', error);
            const checklist = document.getElementById('mods-checklist');
            if (checklist) {
                checklist.innerHTML = '<div class="text-danger">Chyba při načítání módů</div>';
            }
        }
    }

    /**
     * Načte seznam modpacků
     */
    async loadModpacksList() {
        try {
            const response = await fetch(`${API_ENDPOINTS.MODPACKS_LIST}?server_id=${this.serverId}`);
            if (!response.ok) throw new Error('Chyba při načítání modpacků');

            const modpacks = await response.json();
            this.currentModpacks = modpacks;
            const listContainer = document.getElementById('modpacks-list');

            if (!listContainer) {
                console.warn('Element #modpacks-list nebyl nalezen');
                return;
            }

            if (modpacks.length === 0) {
                listContainer.innerHTML = '<div class="text-muted">Zatím nebyly vytvořeny žádné modpacky</div>';
                return;
            }

            listContainer.innerHTML = '';
            modpacks.forEach(pack => {
                const packElement = document.createElement('div');
                packElement.className = 'modpack-item';
                packElement.id = `modpack-${pack.id}`;
                packElement.innerHTML = `
                    <div class="modpack-header">
                        <div>
                            <h5 class="modpack-title">${pack.name}</h5>
                            <div class="modpack-meta">
                                Vytvořil ${pack.author} • ${pack.created_at}
                            </div>
                        </div>
                        <div class="modpack-actions">
                            <button class="btn btn-sm btn-primary edit-modpack-btn" data-pack-id="${pack.id}">
                                <i class="fas fa-edit"></i> Upravit
                            </button>
                            <button class="btn btn-sm btn-danger delete-modpack-btn" data-pack-id="${pack.id}">
                                <i class="fas fa-trash"></i> Smazat
                            </button>
                        </div>
                    </div>
                    ${pack.description ? `<div class="modpack-description">${pack.description}</div>` : ''}
                    <div class="modpack-stats">
                        <span class="modpack-stat">
                            <i class="fas fa-cube"></i> ${pack.mod_count} módů
                        </span>
                        <span class="modpack-stat">
                            <i class="fas fa-download"></i> ${pack.download_count} stažení
                        </span>
                        <span class="modpack-stat">
                            <i class="fas fa-hdd"></i> ${formatSize(pack.file_size)}
                        </span>
                    </div>
                    <div class="modpack-mods-preview">
                        <h6>Obsažené módy:</h6>
                        <div class="mods-preview-list">
                            ${pack.mods.slice(0, 8).map(mod =>
                    `<span class="mod-badge">${mod.name} v${mod.version}</span>`
                ).join('')}
                            ${pack.mods.length > 8 ? `<span class="mod-badge">+${pack.mods.length - 8} dalších</span>` : ''}
                        </div>
                    </div>
                    <div id="edit-form-${pack.id}" class="edit-modpack-form" style="display: none;">
                        <!-- Editovací formulář se načte dynamicky -->
                    </div>
                `;
                listContainer.appendChild(packElement);
            });

            eventBus.emit(EVENTS.MODPACKS_UPDATED, modpacks);

        } catch (error) {
            console.error('Chyba při načítání modpacků:', error);
            const listContainer = document.getElementById('modpacks-list');
            if (listContainer) {
                listContainer.innerHTML = '<div class="text-danger">Chyba při načítání modpacků</div>';
            }
        }
    }

    /**
     * Vytvoří nový modpack
     */
    async createModpack() {
        const nameInput = document.getElementById('modpack-name');
        const descriptionInput = document.getElementById('modpack-description');

        if (!nameInput || !descriptionInput) {
            eventBus.emit(EVENTS.NOTIFICATION_SHOW, {
                type: 'warning',
                message: 'Formulář pro vytváření modpacků není k dispozici'
            });
            return;
        }

        const name = nameInput.value.trim();
        const description = descriptionInput.value.trim();

        if (!name) {
            eventBus.emit(EVENTS.NOTIFICATION_SHOW, {
                type: 'warning',
                message: 'Zadejte název modpacku'
            });
            return;
        }

        // Získat vybrané módy
        const selectedMods = Array.from(document.querySelectorAll('.mod-checkbox:checked'))
            .map(checkbox => parseInt(checkbox.value));

        if (selectedMods.length === 0) {
            eventBus.emit(EVENTS.NOTIFICATION_SHOW, {
                type: 'warning',
                message: 'Vyberte alespoň jeden mód pro modpack'
            });
            return;
        }

        const createBtn = document.getElementById('create-modpack-btn');
        const originalText = createBtn.innerHTML;

        try {
            createBtn.disabled = true;
            createBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Vytvářím...';

            const result = await api.post(API_ENDPOINTS.MODPACKS_CREATE, {
                server_id: this.serverId,
                name: name,
                description: description,
                mod_ids: selectedMods
            });

            if (result.success) {
                eventBus.emit(EVENTS.NOTIFICATION_SHOW, {
                    type: 'success',
                    message: `Modpack "${name}" byl úspěšně vytvořen!`
                });

                // Resetovat formulář
                nameInput.value = '';
                descriptionInput.value = '';
                document.querySelectorAll('.mod-checkbox').forEach(cb => cb.checked = false);

                // Načíst aktualizovaný seznam
                await this.loadModpacksList();
            } else {
                throw new Error(result.error || 'Neznámá chyba');
            }

        } catch (error) {
            console.error('Chyba při vytváření modpacku:', error);
            eventBus.emit(EVENTS.NOTIFICATION_SHOW, {
                type: 'error',
                message: `Chyba: ${error.message}`
            });
        } finally {
            createBtn.disabled = false;
            createBtn.innerHTML = originalText;
        }
    }

    /**
     * Přepne do režimu editace modpacku
     * @param {string} packId 
     */
    async toggleEditModpack(packId) {
        const packElement = document.getElementById(`modpack-${packId}`);
        const editForm = document.getElementById(`edit-form-${packId}`);

        if (!packElement || !editForm) return;

        // Pokud už je v režimu editace, zrušit
        if (packElement.classList.contains('modpack-editing')) {
            this.cancelModpackEdit(packId);
            return;
        }

        try {
            // Načíst data modpacku
            const pack = this.currentModpacks.find(p => p.id == packId);
            if (!pack) return;

            // Načíst dostupné módy pro checkboxy
            const availableMods = await this.loadModsForEditing();

            // Vytvořit editovací formulář
            editForm.innerHTML = `
                <h5><i class="fas fa-edit"></i> Úprava modpacku</h5>
                <div class="form-group">
                    <label for="edit-name-${packId}">Název:</label>
                    <input type="text" id="edit-name-${packId}" class="form-control" value="${pack.name}">
                </div>
                <div class="form-group">
                    <label for="edit-description-${packId}">Popis:</label>
                    <textarea id="edit-description-${packId}" class="form-control" rows="2">${pack.description || ''}</textarea>
                </div>
                <div class="form-group">
                    <label>Vyberte módy:</label>
                    <div class="mods-edit-checklist" id="edit-mods-${packId}">
                        ${availableMods.map(mod => `
                            <div class="mod-checkbox-item">
                                <input type="checkbox" id="edit-mod-${mod.id}-${packId}" 
                                       value="${mod.id}" ${pack.mods.some(m => m.id === mod.id) ? 'checked' : ''}
                                       class="mod-checkbox"
                                       title="Vybrat mod" aria-label="Vybrat mod">
                                <label class="mod-info" for="edit-mod-${mod.id}-${packId}">
                                    <span class="mod-name">${mod.display_name}</span>
                                    <span class="mod-version">v${mod.version}</span>
                                    ${mod.description ? `<div class="mod-description">${mod.description}</div>` : ''}
                                </label>
                            </div>
                        `).join('')}
                    </div>
                </div>
                <div class="modpack-edit-actions">
                    <button class="btn btn-success save-edit-btn" data-pack-id="${packId}">
                        <i class="fas fa-save"></i> Uložit změny
                    </button>
                    <button class="btn btn-secondary cancel-edit-btn" data-pack-id="${packId}">
                        <i class="fas fa-times"></i> Zrušit
                    </button>
                </div>
            `;

            // Zobrazit editovací formulář
            editForm.style.display = 'block';
            packElement.classList.add('modpack-editing');

            // Skrýt hlavní akce během editace
            const actions = packElement.querySelector('.modpack-actions');
            if (actions) {
                actions.style.opacity = '0.5';
                actions.style.pointerEvents = 'none';
            }

        } catch (error) {
            console.error('Chyba při přípravě editace:', error);
            eventBus.emit(EVENTS.NOTIFICATION_SHOW, {
                type: 'error',
                message: 'Chyba při přípravě editace modpacku'
            });
        }
    }

    /**
     * Načtení módů pro editaci
     */
    async loadModsForEditing() {
        try {
            const response = await fetch(`${API_ENDPOINTS.MODS_INSTALLED}?server_id=${this.serverId}`);
            if (!response.ok) throw new Error('Chyba při načítání módů');
            return await response.json();
        } catch (error) {
            console.error('Chyba při načítání módů pro editaci:', error);
            return [];
        }
    }

    /**
     * Uložení změn modpacku
     * @param {string} packId 
     */
    async saveModpackEdit(packId) {
        const nameInput = document.getElementById(`edit-name-${packId}`);
        const descriptionInput = document.getElementById(`edit-description-${packId}`);

        if (!nameInput) return;

        const name = nameInput.value.trim();
        const description = descriptionInput.value.trim();

        if (!name) {
            eventBus.emit(EVENTS.NOTIFICATION_SHOW, {
                type: 'warning',
                message: 'Zadejte název modpacku'
            });
            return;
        }

        // Získat vybrané módy
        const selectedMods = Array.from(document.querySelectorAll(`#edit-mods-${packId} .mod-checkbox:checked`))
            .map(checkbox => parseInt(checkbox.value));

        if (selectedMods.length === 0) {
            eventBus.emit(EVENTS.NOTIFICATION_SHOW, {
                type: 'warning',
                message: 'Vyberte alespoň jeden mód pro modpack'
            });
            return;
        }

        const saveBtn = document.querySelector(`.save-edit-btn[data-pack-id="${packId}"]`);
        const originalText = saveBtn.innerHTML;

        try {
            saveBtn.disabled = true;
            saveBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Ukládám...';

            const response = await fetch(`${API_ENDPOINTS.MODPACKS_UPDATE}/${packId}`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    name: name,
                    description: description,
                    mod_ids: selectedMods
                })
            });

            const result = await response.json();

            if (result.success) {
                eventBus.emit(EVENTS.NOTIFICATION_SHOW, {
                    type: 'success',
                    message: 'Modpack byl úspěšně aktualizován!'
                });
                await this.loadModpacksList();
            } else {
                throw new Error(result.error || 'Neznámá chyba');
            }

        } catch (error) {
            console.error('Chyba při ukládání změn:', error);
            eventBus.emit(EVENTS.NOTIFICATION_SHOW, {
                type: 'error',
                message: `Chyba: ${error.message}`
            });
        } finally {
            saveBtn.disabled = false;
            saveBtn.innerHTML = originalText;
        }
    }

    /**
     * Zruší editaci modpacku
     * @param {string} packId 
     */
    cancelModpackEdit(packId) {
        const packElement = document.getElementById(`modpack-${packId}`);
        const editForm = document.getElementById(`edit-form-${packId}`);

        if (packElement && editForm) {
            packElement.classList.remove('modpack-editing');
            editForm.style.display = 'none';

            // Obnovit hlavní akce
            const actions = packElement.querySelector('.modpack-actions');
            if (actions) {
                actions.style.opacity = '1';
                actions.style.pointerEvents = 'auto';
            }
        }
    }

    /**
     * Smaže modpack
     * @param {string} packId 
     */
    async deleteModpack(packId) {
        const pack = this.currentModpacks.find(p => p.id == packId);
        if (!pack) return;

        if (!confirm(`Opravdu chcete smazat modpack "${pack.name}"?`)) {
            return;
        }

        try {
            const response = await fetch(`${API_ENDPOINTS.MODPACKS_DELETE}/${packId}`, {
                method: 'DELETE'
            });

            const result = await response.json();

            if (result.success) {
                eventBus.emit(EVENTS.NOTIFICATION_SHOW, {
                    type: 'success',
                    message: 'Modpack byl smazán'
                });
                await this.loadModpacksList();
            } else {
                throw new Error(result.error || 'Neznámá chyba');
            }

        } catch (error) {
            console.error('Chyba při mazání modpacku:', error);
            eventBus.emit(EVENTS.NOTIFICATION_SHOW, {
                type: 'error',
                message: `Chyba: ${error.message}`
            });
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
export const modpacksManager = new ModpacksManager();
