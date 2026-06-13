// Notifikace pro server panel
import { eventBus, EVENTS } from '../core/event-bus.js';

class NotificationManager {
    constructor() {
        this.container = null;
        this.setupEventListeners();
    }

    /**
     * Nastaví event listenery
     */
    setupEventListeners() {
        eventBus.on(EVENTS.NOTIFICATION_SHOW, (data) => {
            this.show(data.type, data.message, data.duration);
        });
    }

    /**
     * Zobrazí notifikaci
     * @param {string} type - 'success', 'error', 'info', 'warning'
     * @param {string} message - Zpráva
     * @param {number} duration - Trvání v ms
     */
    show(type, message, duration = 5000) {
        if (!this.container) {
            this.createContainer();
        }

        const notification = document.createElement('div');
        notification.className = `notification notification-${type}`;
        notification.innerHTML = `
            <i class="fas ${this.getNotificationIcon(type)}"></i>
            <span>${message}</span>
            <button class="notification-close"><i class="fas fa-times"></i></button>
        `;

        this.container.appendChild(notification);

        // Animace vstupu
        setTimeout(() => {
            notification.classList.add('show');
        }, 10);

        // Automatické odstranění
        const timeoutId = setTimeout(() => {
            this.removeNotification(notification);
        }, duration);

        // Ruční zavření
        notification.querySelector('.notification-close').addEventListener('click', () => {
            clearTimeout(timeoutId);
            this.removeNotification(notification);
        });
    }

    /**
     * Odstraní notifikaci
     * @param {HTMLElement} notification 
     */
    removeNotification(notification) {
        notification.classList.remove('show');
        notification.classList.add('hide');
        
        setTimeout(() => {
            if (notification.parentNode) {
                notification.parentNode.removeChild(notification);
            }
        }, 300);
    }

    /**
     * Vytvoří kontejner pro notifikace
     */
    createContainer() {
        this.container = document.createElement('div');
        this.container.id = 'notifications';
        this.container.className = 'notifications-container';
        document.body.appendChild(this.container);
    }

    /**
     * Vrátí ikonu pro typ notifikace
     * @param {string} type 
     * @returns {string}
     */
    getNotificationIcon(type) {
        const icons = {
            success: 'fa-check-circle',
            error: 'fa-exclamation-circle',
            info: 'fa-info-circle',
            warning: 'fa-exclamation-triangle'
        };
        return icons[type] || 'fa-info-circle';
    }
}

// Export singleton instance
export const notificationManager = new NotificationManager();