// Konstanty pro server panel
export const API_ENDPOINTS = {
    SERVER_INFO: '/api/server/info',
    SERVER_STATUS: '/api/server/status',
    SERVER_BUILD_TYPE: '/api/server/build-type',
    SERVER_START: '/api/server/start',
    SERVER_STOP: '/api/server/stop',
    SERVER_RESTART: '/api/server/restart',
    SERVER_COMMAND: '/api/server/command',
    SERVER_LOGS: '/api/server/logs',
    SERVER_OLD_LOGS: '/api/server/old-logs',
    SERVER_ADMINS: '/api/server/admins',
    SERVER_ADMINS_ADD: '/api/server/admins/add',
    SERVER_ADMINS_REMOVE: '/api/server/admins/remove',
    SERVER_BACKUPS: '/api/server/backups',
    SERVER_DISK_USAGE: '/api/server/disk-usage',
    NOTICES: '/api/notices',
    NOTICES_CREATE: '/api/notices/create',
    NOTICES_UPDATE: '/api/notices/update',
    NOTICES_DELETE: '/api/notices/delete',
    MODS_INSTALLED: '/api/mods/installed',
    MODPACKS_UPDATE: '/api/modpacks/update',      
    MODPACKS_DELETE: '/api/modpacks/delete',      
    PLUGINS_INSTALLED: '/api/plugins/installed',
    MODPACKS_LIST: '/api/modpacks/list',
    MODPACKS_CREATE: '/api/modpacks/create',
    MODPACKS_DOWNLOAD: '/api/modpacks/download',
    PLAYER_ACCESS_CODES: '/api/server/player-access/codes',
    PLAYER_ACCESS_GENERATE: '/api/server/player-access/generate-code',
    PLAYER_ACCESS_REVOKE: '/api/server/player-access/revoke-code'
};

export const BUILD_TYPES = {
    MOD: [
        'FABRIC', 'FORGE', 'NEOFORGE', 'QUILT', 'BABRIC', 'BTA',
        'JAVA_AGENT', 'LEGACY_FABRIC', 'LITELOADER', 'MODLOADER',
        'NILLOADER', 'ORNITHE', 'RIFT', 'RISUGAMI'
    ],
    PLUGIN: [
        'BUKKIT', 'FOLIA', 'PAPER', 'PURPUR', 'SPIGOT', 'SPONGE'
    ]
};

export const STORAGE_KEYS = {
    CURRENT_SERVER_ID: 'current_server_id',
    SERVER_BUILD_TYPE: (serverId) => `server_${serverId}_build_type`,
    CURRENT_USER: 'current_user'
};

export const NOTICE_TYPES = {
    INFO: 'info',
    WARNING: 'warning',
    IMPORTANT: 'important',
    UPDATE: 'update'
};

export const NOTICE_TYPE_LABELS = {
    [NOTICE_TYPES.INFO]: 'ℹ️ Informace',
    [NOTICE_TYPES.WARNING]: '⚠️ Varování',
    [NOTICE_TYPES.IMPORTANT]: '🔔 Důležité',
    [NOTICE_TYPES.UPDATE]: '🔄 Aktualizace'
};