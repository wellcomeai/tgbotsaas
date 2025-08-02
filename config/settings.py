"""
Application Settings - конфигурация приложения
"""

import os
from pathlib import Path
from typing import Optional

class Settings:
    """Application settings container"""
    
    # Environment
    ENVIRONMENT: str = os.environ.get('ENVIRONMENT', 'development')
    DEBUG: bool = ENVIRONMENT == 'development'
    
    # Paths
    BASE_DIR: Path = Path(__file__).parent.parent
    DATA_DIR: Path = Path(os.environ.get('RENDER_DISK_PATH', '/data'))
    
    # Bot tokens
    MASTER_BOT_TOKEN: str = os.environ.get('MASTER_BOT_TOKEN', '')
    
    # Flask settings
    FLASK_SECRET_KEY: str = os.environ.get('FLASK_SECRET_KEY', 'dev-secret-key-change-in-production')
    FLASK_HOST: str = os.environ.get('FLASK_HOST', '0.0.0.0')
    FLASK_PORT: int = int(os.environ.get('PORT', 10000))
    
    # Database settings
    MASTER_DB_PATH: str = str(DATA_DIR / 'master_database.db')
    BOT_CONFIGS_DIR: str = str(DATA_DIR / 'bot_configs')
    USER_DATABASES_DIR: str = str(DATA_DIR / 'user_databases')
    LOGS_DIR: str = str(DATA_DIR / 'logs')
    
    # Logging
    LOG_LEVEL: str = os.environ.get('LOG_LEVEL', 'INFO')
    LOG_FORMAT: str = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    # Bot management
    MAX_BOTS_PER_USER: int = int(os.environ.get('MAX_BOTS_PER_USER', 5))
    BOT_HEALTH_CHECK_INTERVAL: int = int(os.environ.get('BOT_HEALTH_CHECK_INTERVAL', 300))
    BOT_RESTART_TIMEOUT: int = int(os.environ.get('BOT_RESTART_TIMEOUT', 10))
    
    # Broadcasting
    BROADCAST_DELAY: float = float(os.environ.get('BROADCAST_DELAY', 1.0))
    MAX_BROADCAST_SIZE: int = int(os.environ.get('MAX_BROADCAST_SIZE', 1000))
    BROADCAST_TIMEOUT: int = int(os.environ.get('BROADCAST_TIMEOUT', 30))
    
    # Rate limiting
    RATE_LIMIT_ENABLED: bool = os.environ.get('RATE_LIMIT_ENABLED', 'true').lower() == 'true'
    MESSAGES_PER_MINUTE: int = int(os.environ.get('MESSAGES_PER_MINUTE', 30))
    BROADCASTS_PER_HOUR: int = int(os.environ.get('BROADCASTS_PER_HOUR', 5))
    
    # UTM tracking
    UTM_TRACKING_ENABLED: bool = os.environ.get('UTM_TRACKING_ENABLED', 'true').lower() == 'true'
    UTM_DEFAULT_SOURCE: str = os.environ.get('UTM_DEFAULT_SOURCE', 'telegram_bot')
    UTM_DEFAULT_MEDIUM: str = os.environ.get('UTM_DEFAULT_MEDIUM', 'telegram')
    
    # HTTP settings
    HTTP_TIMEOUT: int = int(os.environ.get('HTTP_TIMEOUT', 10))
    HTTP_MAX_RETRIES: int = int(os.environ.get('HTTP_MAX_RETRIES', 3))
    
    # Telegram API settings
    TELEGRAM_API_BASE_URL: str = 'https://api.telegram.org'
    TELEGRAM_MAX_MESSAGE_LENGTH: int = 4096
    TELEGRAM_RATE_LIMIT: int = 30  # messages per second
    
    # Cache settings
    STATS_CACHE_DURATION: int = int(os.environ.get('STATS_CACHE_DURATION', 3600))  # 1 hour
    USER_LIST_PAGE_SIZE: int = int(os.environ.get('USER_LIST_PAGE_SIZE', 10))
    
    # Cleanup settings
    LOG_RETENTION_DAYS: int = int(os.environ.get('LOG_RETENTION_DAYS', 30))
    MESSAGE_RETENTION_DAYS: int = int(os.environ.get('MESSAGE_RETENTION_DAYS', 90))
    ANALYTICS_RETENTION_DAYS: int = int(os.environ.get('ANALYTICS_RETENTION_DAYS', 365))
    
    # Backup settings
    BACKUP_ENABLED: bool = os.environ.get('BACKUP_ENABLED', 'false').lower() == 'true'
    BACKUP_INTERVAL_HOURS: int = int(os.environ.get('BACKUP_INTERVAL_HOURS', 24))
    BACKUP_RETENTION_DAYS: int = int(os.environ.get('BACKUP_RETENTION_DAYS', 7))
    
    # Support settings
    SUPPORT_EMAIL: str = os.environ.get('SUPPORT_EMAIL', 'support@botfactory.ru')
    SUPPORT_TELEGRAM: str = os.environ.get('SUPPORT_TELEGRAM', '@BotFactorySupport')
    SUPPORT_CHAT: str = os.environ.get('SUPPORT_CHAT', '@BotFactoryChat')
    
    # Feature flags
    ENABLE_SUBSCRIPTIONS: bool = os.environ.get('ENABLE_SUBSCRIPTIONS', 'false').lower() == 'true'
    ENABLE_PAYMENTS: bool = os.environ.get('ENABLE_PAYMENTS', 'false').lower() == 'true'
    ENABLE_ANALYTICS: bool = os.environ.get('ENABLE_ANALYTICS', 'true').lower() == 'true'
    ENABLE_WEBHOOKS: bool = os.environ.get('ENABLE_WEBHOOKS', 'false').lower() == 'true'
    
    # Security settings
    ALLOWED_HOSTS: list = os.environ.get('ALLOWED_HOSTS', '*').split(',')
    TRUSTED_PROXIES: list = os.environ.get('TRUSTED_PROXIES', '').split(',') if os.environ.get('TRUSTED_PROXIES') else []
    
    # Monitoring
    HEALTH_CHECK_ENABLED: bool = True
    METRICS_ENABLED: bool = os.environ.get('METRICS_ENABLED', 'true').lower() == 'true'
    SENTRY_DSN: Optional[str] = os.environ.get('SENTRY_DSN')
    
    @classmethod
    def validate(cls) -> list:
        """Validate settings and return list of errors"""
        errors = []
        
        # Required settings
        if not cls.MASTER_BOT_TOKEN:
            errors.append("MASTER_BOT_TOKEN is required")
        
        # Validate bot token format
        if cls.MASTER_BOT_TOKEN and ':' not in cls.MASTER_BOT_TOKEN:
            errors.append("MASTER_BOT_TOKEN has invalid format")
        
        # Validate paths
        try:
            cls.DATA_DIR.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            errors.append(f"Cannot create data directory: {e}")
        
        # Validate numeric settings
        if cls.FLASK_PORT < 1 or cls.FLASK_PORT > 65535:
            errors.append("FLASK_PORT must be between 1 and 65535")
        
        if cls.MAX_BOTS_PER_USER < 1:
            errors.append("MAX_BOTS_PER_USER must be at least 1")
        
        if cls.BROADCAST_DELAY < 0:
            errors.append("BROADCAST_DELAY cannot be negative")
        
        return errors
    
    @classmethod
    def get_config_dict(cls) -> dict:
        """Get configuration as dictionary"""
        config = {}
        
        for attr in dir(cls):
            if not attr.startswith('_') and not callable(getattr(cls, attr)):
                value = getattr(cls, attr)
                # Convert Path objects to strings
                if isinstance(value, Path):
                    value = str(value)
                config[attr] = value
        
        return config
    
    @classmethod
    def print_config(cls, hide_sensitive: bool = True):
        """Print current configuration"""
        print("🔧 Application Configuration:")
        print("=" * 50)
        
        config = cls.get_config_dict()
        sensitive_keys = ['MASTER_BOT_TOKEN', 'FLASK_SECRET_KEY', 'SENTRY_DSN']
        
        for key, value in sorted(config.items()):
            if hide_sensitive and key in sensitive_keys and value:
                display_value = f"{value[:8]}..." if len(str(value)) > 8 else "***"
            else:
                display_value = value
            
            print(f"{key:25}: {display_value}")
        
        print("=" * 50)

# Global settings instance
settings = Settings()

# Validate settings on import
validation_errors = settings.validate()
if validation_errors:
    print("❌ Configuration errors:")
    for error in validation_errors:
        print(f"  - {error}")
    
    if not settings.DEBUG:
        raise RuntimeError("Configuration validation failed")

def get_user_bot_config(bot_id: int) -> dict:
    """Get default configuration for user bot"""
    return {
        'BOT_ID': bot_id,
        'DATABASE_PATH': str(settings.DATA_DIR / 'user_databases' / f'bot_{bot_id}.db'),
        'LOG_LEVEL': settings.LOG_LEVEL,
        'HEALTH_CHECK_INTERVAL': settings.BOT_HEALTH_CHECK_INTERVAL,
        'MAX_MESSAGE_LENGTH': settings.TELEGRAM_MAX_MESSAGE_LENGTH,
        'RATE_LIMIT_ENABLED': settings.RATE_LIMIT_ENABLED,
        'UTM_TRACKING_ENABLED': settings.UTM_TRACKING_ENABLED,
        'BROADCAST_DELAY': settings.BROADCAST_DELAY,
        'MAX_BROADCAST_SIZE': settings.MAX_BROADCAST_SIZE,
        'AUTO_APPROVE_REQUESTS': True,
        'WELCOME_MESSAGE_ENABLED': True,
        'FAREWELL_MESSAGE_ENABLED': True,
        'STATS_ENABLED': settings.ENABLE_ANALYTICS,
        'ANALYTICS_RETENTION_DAYS': settings.ANALYTICS_RETENTION_DAYS,
        'WELCOME_MESSAGE': "👋 Добро пожаловать в наш канал! Мы рады видеть тебя здесь.",
        'FAREWELL_MESSAGE': "👋 До свидания! Будем скучать.",
        'AUTO_APPROVE_MESSAGE': "✅ Твоя заявка одобрена! Добро пожаловать в канал."
    }
