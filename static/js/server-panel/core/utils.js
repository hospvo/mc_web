// Utility funkce
import { STORAGE_KEYS } from './constants.js';
import { API_ENDPOINTS } from './constants.js';

/**
 * Získá aktuální server_id z URL nebo localStorage
 * @returns {number|null} Server ID nebo null
 */
export function getCurrentServerId() {
    const pathParts = window.location.pathname.split('/');
    const serverIdFromUrl = pathParts[2]; // /server/<id> => část na indexu 2

    if (serverIdFromUrl && !isNaN(serverIdFromUrl)) {
        const id = parseInt(serverIdFromUrl);
        localStorage.setItem(STORAGE_KEYS.CURRENT_SERVER_ID, id);
        return id;
    }
    
    const lastServerId = localStorage.getItem(STORAGE_KEYS.CURRENT_SERVER_ID);
    if (lastServerId && !isNaN(lastServerId)) {
        return parseInt(lastServerId);
    }
    
    console.error('Nelze získat server_id z URL:', window.location.pathname);
    return null;
}

/**
 * Kontroluje zda jsou dva pole stejné
 * @param {Array} a 
 * @param {Array} b 
 * @returns {boolean}
 */
export function arraysEqual(a, b) {
    if (a.length !== b.length) return false;
    for (let i = 0; i < a.length; i++) {
        if (a[i] !== b[i]) return false;
    }
    return true;
}

/**
 * Formátuje velikost v bytech na čitelný formát
 * @param {number} bytes 
 * @returns {string}
 */
export function formatSize(bytes) {
    if (bytes === 0) return '0 B';
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(1024));
    return parseFloat((bytes / Math.pow(1024, i)).toFixed(2)) + ' ' + sizes[i];
}

/**
 * Detekuje build type serveru
 * @param {string} buildType 
 * @returns {string} 'mod', 'plugin', nebo 'unknown'
 */
export function detectBuildType(buildType) {
    const { MOD, PLUGIN } = BUILD_TYPES;
    const upperType = buildType?.toUpperCase() || '';
    
    if (MOD.includes(upperType)) return 'mod';
    if (PLUGIN.includes(upperType)) return 'plugin';
    return 'unknown';
}

/**
 * Získá typ serveru z localStorage nebo API
 * @param {number} serverId 
 * @returns {Promise<string>}
 */
export async function getServerBuildType(serverId) {
    const cached = localStorage.getItem(STORAGE_KEYS.SERVER_BUILD_TYPE(serverId));
    if (cached) return cached;
    
    try {
        const response = await fetch(`${API_ENDPOINTS.SERVER_BUILD_TYPE}?server_id=${serverId}`);
        const data = await response.json();
        localStorage.setItem(STORAGE_KEYS.SERVER_BUILD_TYPE(serverId), data.build_type);
        return data.build_type;
    } catch (error) {
        console.error('Chyba při získávání build type:', error);
        return 'UNKNOWN';
    }
}

/**
 * Kontroluje zda je uživatel admin serveru
 * @param {number} serverId 
 * @returns {Promise<boolean>}
 */
export async function isAdmin(serverId) {
    try {
        const response = await fetch(`${API_ENDPOINTS.SERVER_ADMINS}?server_id=${serverId}`);
        const data = await response.json();
        
        if (data.is_owner) return true;
        
        const currentUser = JSON.parse(
            localStorage.getItem(STORAGE_KEYS.CURRENT_USER) || 
            sessionStorage.getItem(STORAGE_KEYS.CURRENT_USER) || 
            '{}'
        );
        
        return data.admins?.some(admin => admin.user_id === currentUser.id) || false;
    } catch (error) {
        console.error('Chyba při kontrole admin práv:', error);
        return false;
    }
}

/**
 * Zobrazí notifikaci
 * @param {string} type - 'success', 'error', 'info', 'warning'
 * @param {string} message - Zpráva
 * @param {number} duration - Trvání v ms
 */
export function showNotification(type, message, duration = 5000) {
    const container = document.getElementById('notifications') || createNotificationContainer();
    
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.innerHTML = `
        <i class="fas ${getNotificationIcon(type)}"></i>
        <span>${message}</span>
        <button class="notification-close"><i class="fas fa-times"></i></button>
    `;
    
    container.appendChild(notification);
    
    // Automatické odstranění
    setTimeout(() => {
        notification.classList.add('fade-out');
        setTimeout(() => notification.remove(), 300);
    }, duration);
    
    // Ruční zavření
    notification.querySelector('.notification-close').addEventListener('click', () => {
        notification.classList.add('fade-out');
        setTimeout(() => notification.remove(), 300);
    });
}

function createNotificationContainer() {
    const container = document.createElement('div');
    container.id = 'notifications';
    container.className = 'notifications-container';
    document.body.appendChild(container);
    return container;
}

function getNotificationIcon(type) {
    const icons = {
        success: 'fa-check-circle',
        error: 'fa-exclamation-circle',
        info: 'fa-info-circle',
        warning: 'fa-exclamation-triangle'
    };
    return icons[type] || 'fa-info-circle';
}

/**
 * Formátuje obsah oznámení s jednoduchým markdown
 * @param {string} text 
 * @returns {string}
 */
export function formatNoticeContent(text) {
    if (!text) return '';
    
    return text
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.*?)\*/g, '<em>$1</em>')
        .replace(/<u>(.*?)<\/u>/g, '<u>$1</u>')
        .replace(/`(.*?)`/g, '<code>$1</code>')
        .replace(/\[(.*?)\]\((.*?)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>')
        .replace(/^[-*] (.*)$/gm, '<li>$1</li>')
        .replace(/(<li>.*<\/li>)/gs, '<ul>$1</ul>')
        .replace(/^\d+\. (.*)$/gm, '<li>$1</li>')
        .replace(/(<li>.*<\/li>)/gs, '<ol>$1</ol>')
        .replace(/\n/g, '<br>');
}