// API služba pro komunikaci se serverem
import { API_ENDPOINTS } from './constants.js';

class APIService {
    constructor() {
        this.baseURL = ''; // Relativní URL (stejný origin)
    }

    /**
     * Odesílá GET požadavek
     * @param {string} endpoint 
     * @param {Object} params 
     * @returns {Promise<any>}
     */
    async get(endpoint, params = {}) {
        const url = this.buildURL(endpoint, params);
        try {
            const response = await fetch(url);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            return await response.json();
        } catch (error) {
            console.error(`GET ${endpoint} failed:`, error);
            throw error;
        }
    }

    /**
     * Odesílá POST požadavek
     * @param {string} endpoint 
     * @param {Object} data 
     * @returns {Promise<any>}
     */
    async post(endpoint, data = {}) {
        try {
            const response = await fetch(endpoint, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(data)
            });
            
            if (!response.ok) {
                const errorText = await response.text();
                let errorMessage = response.statusText;

                try {
                    const errorData = JSON.parse(errorText);
                    errorMessage = errorData.error || errorData.message || errorMessage;
                } catch {
                    errorMessage = errorText || errorMessage;
                }

                throw new Error(`HTTP ${response.status}: ${errorMessage}`);
            }
            
            return await response.json();
        } catch (error) {
            console.error(`POST ${endpoint} failed:`, error);
            throw error;
        }
    }

    /**
     * Odesílá PUT požadavek
     * @param {string} endpoint 
     * @param {Object} data 
     * @returns {Promise<any>}
     */
    async put(endpoint, data = {}) {
        try {
            const response = await fetch(endpoint, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(data)
            });
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            return await response.json();
        } catch (error) {
            console.error(`PUT ${endpoint} failed:`, error);
            throw error;
        }
    }

    /**
     * Odesílá DELETE požadavek
     * @param {string} endpoint 
     * @param {Object} data 
     * @returns {Promise<any>}
     */
    async delete(endpoint, data = {}) {
        try {
            const response = await fetch(endpoint, {
                method: 'DELETE',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(data)
            });
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            return await response.json();
        } catch (error) {
            console.error(`DELETE ${endpoint} failed:`, error);
            throw error;
        }
    }

    /**
     * Stahuje binární soubor
     * @param {string} endpoint 
     * @param {Object} params 
     * @returns {Promise<Blob>}
     */
    async download(endpoint, params = {}) {
        const url = this.buildURL(endpoint, params);
        try {
            const response = await fetch(url);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            return await response.blob();
        } catch (error) {
            console.error(`Download ${endpoint} failed:`, error);
            throw error;
        }
    }

    /**
     * Vytváří URL s parametry
     * @param {string} endpoint 
     * @param {Object} params 
     * @returns {string}
     */
    buildURL(endpoint, params = {}) {
        const url = new URL(endpoint, window.location.origin);
        Object.keys(params).forEach(key => {
            url.searchParams.append(key, params[key]);
        });
        return url.toString();
    }

    // Specifické metody pro server panel
    
    /**
     * Získá informace o serveru
     * @param {number} serverId 
     * @returns {Promise<Object>}
     */
    async getServerInfo(serverId) {
        return this.get(API_ENDPOINTS.SERVER_INFO, { server_id: serverId });
    }

    /**
     * Získá stav serveru
     * @param {number} serverId 
     * @returns {Promise<Object>}
     */
    async getServerStatus(serverId) {
        return this.get(API_ENDPOINTS.SERVER_STATUS, { server_id: serverId });
    }

    /**
     * Spustí server
     * @param {number} serverId 
     * @returns {Promise<Object>}
     */
    async startServer(serverId) {
        return this.post(API_ENDPOINTS.SERVER_START, { server_id: serverId });
    }

    /**
     * Vypne server
     * @param {number} serverId 
     * @returns {Promise<Object>}
     */
    async stopServer(serverId) {
        return this.post(API_ENDPOINTS.SERVER_STOP, { server_id: serverId });
    }

    /**
     * Restartuje server
     * @param {number} serverId 
     * @returns {Promise<Object>}
     */
    async restartServer(serverId) {
        return this.post(API_ENDPOINTS.SERVER_RESTART, { server_id: serverId });
    }

    /**
     * Odešle příkaz na server
     * @param {number} serverId 
     * @param {string} command 
     * @returns {Promise<Object>}
     */
    async sendCommand(serverId, command) {
        return this.post(API_ENDPOINTS.SERVER_COMMAND, { 
            server_id: serverId,
            command 
        });
    }

    /**
     * Získá logy serveru
     * @param {number} serverId 
     * @param {number} lines 
     * @returns {Promise<Object>}
     */
    async getServerLogs(serverId, lines = 200) {
        return this.get(API_ENDPOINTS.SERVER_LOGS, { 
            server_id: serverId,
            lines 
        });
    }

    /**
     * Získá staré logy
     * @param {number} serverId 
     * @returns {Promise<string[]>}
     */
    async getOldLogs(serverId) {
        return this.get(API_ENDPOINTS.SERVER_OLD_LOGS, { server_id: serverId });
    }
}

// Export singleton instance
export const api = new APIService();
