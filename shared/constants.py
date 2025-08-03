"""
Application Constants - общие константы для всего приложения
"""

# Bot statuses
BOT_STATUS_CREATING = 'creating'
BOT_STATUS_ACTIVE = 'active'
BOT_STATUS_STOPPED = 'stopped'
BOT_STATUS_ERROR = 'error'
BOT_STATUS_DELETED = 'deleted'

BOT_STATUSES = [
    BOT_STATUS_CREATING,
    BOT_STATUS_ACTIVE,
    BOT_STATUS_STOPPED,
    BOT_STATUS_ERROR,
    BOT_STATUS_DELETED
]

# User subscription statuses
SUBSCRIPTION_TRIAL = 'trial'
SUBSCRIPTION_ACTIVE = 'active'
SUBSCRIPTION_EXPIRED = 'expired'
SUBSCRIPTION_CANCELLED = 'cancelled'

SUBSCRIPTION_STATUSES = [
    SUBSCRIPTION_TRIAL,
    SUBSCRIPTION_ACTIVE,
    SUBSCRIPTION_EXPIRED,
    SUBSCRIPTION_CANCELLED
]

# Message types
MESSAGE_TYPE_WELCOME = 'welcome'
MESSAGE_TYPE_FAREWELL = 'farewell'
MESSAGE_TYPE_BROADCAST = 'broadcast'
MESSAGE_TYPE_AUTO_APPROVAL = 'auto_approval'
MESSAGE_TYPE_MEMBER_ADDED = 'member_added'
MESSAGE_TYPE_MEMBER_LEFT = 'member_left'
MESSAGE_TYPE_URL_SHARED = 'url_shared'

MESSAGE_TYPES = [
    MESSAGE_TYPE_WELCOME,
    MESSAGE_TYPE_FAREWELL,
    MESSAGE_TYPE_BROADCAST,
    MESSAGE_TYPE_AUTO_APPROVAL,
    MESSAGE_TYPE_MEMBER_ADDED,
    MESSAGE_TYPE_MEMBER_LEFT,
    MESSAGE_TYPE_URL_SHARED
]

# Event types for system logs
EVENT_USER_REGISTERED = 'user_registered'
EVENT_BOT_CREATED = 'bot_created'
EVENT_BOT_STARTED = 'bot_started'
EVENT_BOT_STOPPED = 'bot_stopped'
EVENT_BOT_ERROR = 'bot_error'
EVENT_BROADCAST_SENT = 'broadcast_sent'
EVENT_USER_JOINED = 'user_joined'
EVENT_USER_LEFT = 'user_left'

EVENT_TYPES = [
    EVENT_USER_REGISTERED,
    EVENT_BOT_CREATED,
    EVENT_BOT_STARTED,
    EVENT_BOT_STOPPED,
    EVENT_BOT_ERROR,
    EVENT_BROADCAST_SENT,
    EVENT_USER_JOINED,
    EVENT_USER_LEFT
]

# UTM sources
UTM_SOURCE_CHANNEL_JOIN = 'channel_join'
UTM_SOURCE_CHANNEL_INVITE = 'channel_invite'
UTM_SOURCE_CHANNEL_MESSAGE = 'channel_message'
UTM_SOURCE_WELCOME = 'welcome'
UTM_SOURCE_BROADCAST = 'broadcast'
UTM_SOURCE_AUTO_APPROVE = 'auto_approve'
UTM_SOURCE_AUTO_WELCOME = 'auto_welcome'
UTM_SOURCE_AUTO_FAREWELL = 'auto_farewell'

UTM_SOURCES = [
    UTM_SOURCE_CHANNEL_JOIN,
    UTM_SOURCE_CHANNEL_INVITE,
    UTM_SOURCE_CHANNEL_MESSAGE,
    UTM_SOURCE_WELCOME,
    UTM_SOURCE_BROADCAST,
    UTM_SOURCE_AUTO_APPROVE,
    UTM_SOURCE_AUTO_WELCOME,
    UTM_SOURCE_AUTO_FAREWELL
]

# Default configuration values
DEFAULT_WELCOME_MESSAGE = "👋 Добро пожаловать в наш канал! Мы рады видеть тебя здесь."
DEFAULT_FAREWELL_MESSAGE = "👋 До свидания! Будем скучать."
DEFAULT_AUTO_APPROVE_MESSAGE = "✅ Твоя заявка одобрена! Добро пожаловать в канал."

# Limits and constraints
MAX_MESSAGE_LENGTH = 4000
MAX_BROADCAST_SIZE = 1000
MAX_BOTS_PER_USER = 5  # For future implementation
BROADCAST_DELAY_SECONDS = 1
HEALTH_CHECK_INTERVAL_SECONDS = 300  # 5 minutes

# Rate limiting
RATE_LIMIT_MESSAGES_PER_MINUTE = 30
RATE_LIMIT_BROADCASTS_PER_HOUR = 5

# File paths (relative to data directory)
BOT_CONFIGS_SUBDIR = 'bot_configs'
USER_DATABASES_SUBDIR = 'user_databases' 
LOGS_SUBDIR = 'logs'

# Database settings
DB_CONNECTION_TIMEOUT = 30
DB_MAX_RETRIES = 3

# HTTP settings
HTTP_TIMEOUT = 10
HTTP_MAX_RETRIES = 3

# Support information
SUPPORT_EMAIL = 'support@botfactory.ru'
SUPPORT_TELEGRAM = '@BotFactorySupport'
SUPPORT_CHAT = '@BotFactoryChat'

# Application metadata
APP_NAME = 'Bot Factory'
APP_VERSION = '1.0.0-mvp'
APP_DESCRIPTION = 'SaaS platform for Telegram bot creation'

# Telegram API limits
TELEGRAM_MAX_MESSAGE_LENGTH = 4096
TELEGRAM_MAX_CAPTION_LENGTH = 1024
TELEGRAM_RATE_LIMIT_PER_SECOND = 30
TELEGRAM_RATE_LIMIT_PER_MINUTE = 20

# Error messages
ERROR_BOT_NOT_FOUND = 'Бот не найден'
ERROR_ACCESS_DENIED = 'У вас нет прав для этого действия'
ERROR_INVALID_TOKEN = 'Неверный токен бота'
ERROR_TOKEN_ALREADY_EXISTS = 'Этот токен уже используется'
ERROR_USER_NOT_FOUND = 'Пользователь не найден'
ERROR_BROADCAST_FAILED = 'Ошибка при отправке рассылки'
ERROR_NETWORK_ERROR = 'Ошибка сети'
ERROR_DATABASE_ERROR = 'Ошибка базы данных'

# Success messages
SUCCESS_BOT_CREATED = 'Бот успешно создан'
SUCCESS_BOT_STARTED = 'Бот запущен'
SUCCESS_BOT_STOPPED = 'Бот остановлен'
SUCCESS_BROADCAST_SENT = 'Рассылка отправлена'
SUCCESS_SETTINGS_UPDATED = 'Настройки обновлены'

# Regex patterns
TELEGRAM_BOT_TOKEN_PATTERN = r'^\d+:[A-Za-z0-9_-]+$'
TELEGRAM_USERNAME_PATTERN = r'^[a-zA-Z0-9_]+$'
URL_PATTERN = r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'

# Cache settings
STATS_CACHE_DURATION_MINUTES = 60
USER_LIST_CACHE_DURATION_MINUTES = 30

# Pagination
DEFAULT_PAGE_SIZE = 10
MAX_PAGE_SIZE = 50
