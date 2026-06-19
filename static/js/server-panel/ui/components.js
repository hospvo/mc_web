// UI komponenty pro server panel
import { API_ENDPOINTS } from '../core/constants.js';
import { api } from '../core/api.js';
import { eventBus, EVENTS } from '../core/event-bus.js';

export class ClientTools {
    /**
     * Inicializuje nástroje pro klienta
     * @param {number} serverId 
     */
    static init(serverId) {
        const container = document.getElementById('client-tools-container');
        if (!container) {
            console.warn('Container #client-tools-container nebyl nalezen');
            return;
        }

        // Vytvoření základního UI pro client tools
        container.innerHTML = `
            <div class="tool-card">
                <h5><i class="fas fa-file-archive"></i> Klientský balíček modů</h5>
                <p>Stáhněte si všechny módy, které potřebujete pro připojení k tomuto serveru.</p>
                <button class="btn btn-success" id="download-client-pack">
                    <i class="fas fa-download"></i> Stáhnout ZIP
                </button>
                <div id="client-pack-status" class="tool-status"></div>
            </div>
            <div class="tool-card">
                <h5><i class="fas fa-cubes"></i> Modpacky serveru</h5>
                <p>Vyberte si z modpacků vytvořených administrátory serveru.</p>
                <button class="btn btn-info" id="show-modpacks">
                    <i class="fas fa-list"></i> Zobrazit modpacky
                </button>
                <div id="modpacks-status" class="tool-status"></div>
            </div>
        `;

        // Event listenery
        document.getElementById('download-client-pack')?.addEventListener('click',
            () => this.downloadClientPack(serverId));

        document.getElementById('show-modpacks')?.addEventListener('click',
            () => this.showModpacksSelection(serverId));
    }

    /**
     * Stáhne klientský balíček
     * @param {number} serverId 
     */
    static async downloadClientPack(serverId) {
        const statusElement = document.getElementById('client-pack-status');
        const button = document.getElementById('download-client-pack');

        if (!statusElement || !button) return;

        const originalText = button.innerHTML;

        try {
            statusElement.textContent = 'Připravuji ZIP balíček...';
            statusElement.className = 'tool-status info';
            button.disabled = true;
            button.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Připravuji...';

            const response = await fetch(`/api/mods/client-pack/download?server_id=${serverId}`);
            if (!response.ok) throw new Error(`HTTP ${response.status}: ${response.statusText}`);

            const blob = await response.blob();
            if (blob.size === 0) throw new Error('Obdržen prázdný soubor');

            // Vytvoření a stažení souboru
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
            button.disabled = false;
            button.innerHTML = originalText;

            // Automaticky skrýt status zprávu po 10 sekundách
            setTimeout(() => {
                statusElement.textContent = '';
                statusElement.className = 'tool-status';
            }, 10000);
        }
    }

    /**
     * Zobrazí výběr modpacků
     * @param {number} serverId 
     */
    static async showModpacksSelection(serverId) {
        const statusElement = document.getElementById('modpacks-status');
        const button = document.getElementById('show-modpacks');

        if (!statusElement || !button) return;

        const originalText = button.innerHTML;

        try {
            statusElement.textContent = 'Načítám modpacky...';
            statusElement.className = 'tool-status info';
            button.disabled = true;
            button.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Načítám...';

            const response = await fetch(`${API_ENDPOINTS.MODPACKS_LIST}?server_id=${serverId}`);
            if (!response.ok) throw new Error('Chyba při načítání modpacků');

            const modpacks = await response.json();

            if (modpacks.length === 0) {
                statusElement.textContent = 'Pro tento server nejsou k dispozici žádné modpacky.';
                statusElement.className = 'tool-status warning';
                return;
            }

            // Zobrazit modální okno s modpacky
            this.showModpacksModal(modpacks, serverId);

            statusElement.textContent = '';
            statusElement.className = 'tool-status';

        } catch (error) {
            console.error('Chyba při načítání modpacků:', error);
            statusElement.textContent = `Chyba při načítání modpacků: ${error.message}`;
            statusElement.className = 'tool-status error';
        } finally {
            button.disabled = false;
            button.innerHTML = originalText;

            // Automaticky skrýt status zprávu po 10 sekundách
            setTimeout(() => {
                statusElement.textContent = '';
                statusElement.className = 'tool-status';
            }, 10000);
        }
    }

    /**
     * Zobrazí modální okno s modpacky
     * @param {Array} modpacks 
     * @param {number} serverId 
     */
    static showModpacksModal(modpacks, serverId) {
        // Odstranit existující modální okno
        const existingModal = document.querySelector('.modpack-selection-modal');
        if (existingModal) {
            existingModal.remove();
        }

        // Vytvořit nové modální okno
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
                <div class="modpacks-selection-list" style="margin: 1rem 0;">
                    ${modpacks.map(pack => `
                        <div class="modpack-tool-card" style="background: #f8f9fa; border: 1px solid #dee2e6; border-radius: 6px; padding: 1rem; margin-bottom: 1rem;">
                            <h5 style="margin-top: 0;">${pack.name}</h5>
                            ${pack.description ? `<p style="color: #6c757d;">${pack.description}</p>` : ''}
                            <div class="modpack-tool-stats" style="display: flex; gap: 1rem; margin: 0.5rem 0; font-size: 0.9rem; color: #6c757d;">
                                <span><i class="fas fa-cube"></i> ${pack.mod_count} módů</span>
                                <span><i class="fas fa-download"></i> ${pack.download_count} stažení</span>
                                <span><i class="fas fa-hdd"></i> ${this.formatSize(pack.file_size)}</span>
                            </div>
                            <button class="btn btn-success download-modpack-selection" 
                                    data-pack-id="${pack.id}"
                                    style="background: linear-gradient(135deg, #28a745, #20c997); color: white; border: none; padding: 0.5rem 1rem; border-radius: 4px; cursor: pointer;">
                                <i class="fas fa-download"></i> Stáhnout tento modpack
                            </button>
                        </div>
                    `).join('')}
                </div>
                <div style="text-align: center; margin-top: 1rem;">
                    <button class="btn btn-danger" id="close-modpack-selection" 
                            style="background: linear-gradient(135deg, #e74c3c, #c0392b); color: white; border: none; padding: 0.5rem 1.5rem; border-radius: 6px; font-weight: 600; cursor: pointer;">
                        Zavřít
                    </button>
                </div>
            </div>
        `;

        document.body.appendChild(modal);

        // Zavření
        modal.querySelector('#close-modpack-selection').addEventListener('click', () => {
            modal.remove();
        });

        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                modal.remove();
            }
        });

        // Stahování vybraného modpacku
        modal.querySelectorAll('.download-modpack-selection').forEach(btn => {
            btn.addEventListener('click', async (e) => {
                const packId = e.target.closest('.download-modpack-selection').dataset.packId;
                modal.remove();
                await this.downloadModpack(packId);
            });
        });
    }

    /**
     * Stáhne modpack
     * @param {string} packId 
     */
    static async downloadModpack(packId) {
        try {
            // 1. Získat blob z API
            const blob = await api.download(`/api/modpacks/download/${packId}`);

            if (!blob || blob.size === 0) {
                throw new Error('Obdržen prázdný soubor');
            }

            // 2. Získat název souboru (pokud potřebuješ specifický)
            // Flask endpoint už nastavuje download_name, takže většinou není potřeba

            // 3. Vytvořit a spustit stažení
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `modpack_${packId}.zip`; // Fallback název
            document.body.appendChild(a);
            a.click();

            // 4. Cleanup
            setTimeout(() => {
                document.body.removeChild(a);
                URL.revokeObjectURL(url);
            }, 100);

            // 5. Notifikace
            eventBus.emit(EVENTS.NOTIFICATION_SHOW, {
                type: 'success',
                message: `Modpack stažen (${this.formatSize(blob.size)})`
            });

            console.log('Modpack download successful:', {
                packId,
                size: blob.size,
                type: blob.type
            });

            return blob;

        } catch (error) {
            console.error('Chyba při stahování modpacku:', error);

            // User-friendly error messages
            let userMessage = 'Chyba při stahování modpacku';

            if (error.message.includes('403')) {
                userMessage = 'Nemáte oprávnění stáhnout tento modpack';
            } else if (error.message.includes('404')) {
                userMessage = 'Modpack nebyl nalezen';
            } else if (error.message.includes('soubor nebyl nalezen')) {
                userMessage = 'Soubor modpacku není dostupný';
            }

            eventBus.emit(EVENTS.NOTIFICATION_SHOW, {
                type: 'error',
                message: userMessage
            });

            throw error;
        }
    }

    /**
     * Formátuje velikost souboru
     * @param {number} bytes 
     * @returns {string}
     */
    static formatSize(bytes) {
        if (bytes < 1024) return `${bytes} B`;
        if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
        return `${(bytes / 1024 / 1024).toFixed(2)} MB`;
    }
}

export class ExpandableSections {
    static init() {
        const sectionHeaders = document.querySelectorAll('.section-header');

        console.log(`Initializing ${sectionHeaders.length} expandable sections`);

        sectionHeaders.forEach(header => {
            const section = header.dataset.section;
            const content = document.getElementById(`${section}-content`);

            if (!content) {
                console.warn(`Content for section "${section}" not found`);
                return;
            }

            // DEBUG: Zkontroluj počáteční stav
            console.log(`Section "${section}":`, {
                hasCollapsedClass: content.classList.contains('collapsed'),
                hasExpandedClass: content.classList.contains('expanded'),
                computedDisplay: window.getComputedStyle(content).display
            });

            // Vsechny rozbalovaci sekce startuji zavrene.
            content.style.display = '';
            content.classList.remove('expanded');
            content.classList.add('collapsed');
            header.classList.remove('expanded');

            // Přidat event listener
            if (header.dataset.expandableReady === 'true') {
                return;
            }

            header.addEventListener('click', () => {
                this.toggleSection(header, content, section);
            });
            header.dataset.expandableReady = 'true';

            // Přidat CSS pro kurzor
            header.style.cursor = 'pointer';
        });

        console.log('Expandable sections initialized');
    }

    static toggleSection(header, content, sectionName) {
        const isExpanded = content.classList.contains('expanded');

        console.log(`Toggling section "${sectionName}" from ${isExpanded ? 'expanded' : 'collapsed'}`);

        if (isExpanded) {
            // Sbalit
            content.classList.remove('expanded');
            content.classList.add('collapsed');
            header.classList.remove('expanded');
        } else {
            // Rozbalit
            content.classList.remove('collapsed');
            content.classList.add('expanded');
            header.classList.add('expanded');
        }

        // Force reflow pro jistotu
        content.offsetHeight;
    }
}

export class ModalManager {
    /**
     * Zobrazí modální okno
     * @param {string} title 
     * @param {string} content 
     * @param {Object} options 
     */
    static show(title, content, options = {}) {
        // Odstranit existující modální okno
        const existingModal = document.querySelector('.custom-modal');
        if (existingModal) {
            existingModal.remove();
        }

        const modal = document.createElement('div');
        modal.className = 'custom-modal';
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

        const sizeClass = options.size === 'large' ? 'modal-large' :
            options.size === 'small' ? 'modal-small' : '';

        modal.innerHTML = `
            <div class="modal-content ${sizeClass}" style="background: white; padding: 2rem; border-radius: 8px; max-width: ${options.maxWidth || '500px'}; width: 90%; max-height: 80vh; overflow-y: auto;">
                <div class="modal-header" style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">
                    <h4 style="margin: 0;">${title}</h4>
                    <button class="modal-close" style="background: none; border: none; font-size: 1.5rem; cursor: pointer;">×</button>
                </div>
                <div class="modal-body">
                    ${content}
                </div>
                ${options.showFooter !== false ? `
                <div class="modal-footer" style="margin-top: 1rem; text-align: right;">
                    ${options.buttons || `
                        <button class="btn btn-primary modal-ok" style="padding: 0.5rem 1rem; border: none; border-radius: 4px; background: #007bff; color: white; cursor: pointer;">
                            OK
                        </button>
                    `}
                </div>
                ` : ''}
            </div>
        `;

        document.body.appendChild(modal);

        // Zavření
        const closeModal = () => modal.remove();

        modal.querySelector('.modal-close').addEventListener('click', closeModal);
        modal.querySelector('.modal-ok')?.addEventListener('click', closeModal);

        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                closeModal();
            }
        });

        return {
            close: closeModal,
            element: modal
        };
    }
}
