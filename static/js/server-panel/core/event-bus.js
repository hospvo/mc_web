// Event systém pro komunikaci mezi moduly
class EventBus {
    constructor() {
        this.events = new Map();
    }

    /**
     * Registruje posluchače události
     * @param {string} eventName 
     * @param {Function} callback 
     * @returns {Function} Funkce pro odregistrování
     */
    on(eventName, callback) {
        if (!this.events.has(eventName)) {
            this.events.set(eventName, new Set());
        }
        
        const callbacks = this.events.get(eventName);
        callbacks.add(callback);
        
        // Vrací funkci pro odregistrování
        return () => this.off(eventName, callback);
    }

    /**
     * Odregistruje posluchače události
     * @param {string} eventName 
     * @param {Function} callback 
     */
    off(eventName, callback) {
        if (this.events.has(eventName)) {
            const callbacks = this.events.get(eventName);
            callbacks.delete(callback);
        }
    }

    /**
     * Vyvolá událost
     * @param {string} eventName 
     * @param {any} data 
     */
    emit(eventName, data = null) {
        if (this.events.has(eventName)) {
            const callbacks = this.events.get(eventName);
            callbacks.forEach(callback => {
                try {
                    callback(data);
                } catch (error) {
                    console.error(`Error in event handler for ${eventName}:`, error);
                }
            });
        }
    }

    /**
     * Registruje jednorázového posluchače
     * @param {string} eventName 
     * @param {Function} callback 
     */
    once(eventName, callback) {
        const onceCallback = (data) => {
            callback(data);
            this.off(eventName, onceCallback);
        };
        this.on(eventName, onceCallback);
    }

    /**
     * Vyčistí všechny posluchače pro událost
     * @param {string} eventName 
     */
    clear(eventName) {
        if (eventName) {
            this.events.delete(eventName);
        } else {
            this.events.clear();
        }
    }
}

// Export singleton instance
export const eventBus = new EventBus();

// Definice událostí
export const EVENTS = {
    SERVER_STATUS_UPDATED: 'server:status:updated',
    SERVER_STATUS_CHANGED: 'server:status:changed',
    SERVER_STARTED: 'server:started',
    SERVER_STOPPED: 'server:stopped',
    SERVER_RESTARTED: 'server:restarted',
    SERVER_LOGS_UPDATED: 'server:logs:updated',
    SERVER_INFO_UPDATED: 'server:info:updated',
    BACKUPS_UPDATED: 'backups:updated',
    MODPACKS_UPDATED: 'modpacks:updated',
    NOTICES_UPDATED: 'notices:updated',
    PLAYER_ACCESS_CODES_UPDATED: 'player-access:codes:updated',
    ADMIN_LIST_UPDATED: 'admin:list:updated',
    ERROR_OCCURRED: 'error:occurred',
    NOTIFICATION_SHOW: 'notification:show'
};