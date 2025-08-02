"""
Shared Utilities Module - общие утилиты
"""

__version__ = "1.0.0-mvp"

# Безопасные импорты с обработкой ошибок
__all__ = []

try:
    from . import constants
    __all__.append('constants')
except ImportError as e:
    import logging
    logging.warning(f"Could not import constants: {e}")

try:
    from . import database_utils
    __all__.append('database_utils')
except ImportError as e:
    import logging
    logging.warning(f"Could not import database_utils: {e}")

try:
    from . import telegram_utils
    __all__.append('telegram_utils')
except ImportError as e:
    import logging
    logging.warning(f"Could not import telegram_utils: {e}")

# Попытаемся импортировать часто используемые константы
try:
    from .constants import (
        BOT_STATUS_ACTIVE,
        BOT_STATUS_CREATING,
        BOT_STATUS_STOPPED,
        BOT_STATUS_ERROR,
        MESSAGE_TYPE_WELCOME,
        MESSAGE_TYPE_BROADCAST,
        EVENT_BOT_CREATED,
        EVENT_BOT_STARTED
    )
    
    __all__.extend([
        'BOT_STATUS_ACTIVE',
        'BOT_STATUS_CREATING',
        'BOT_STATUS_STOPPED',
        'BOT_STATUS_ERROR',
        'MESSAGE_TYPE_WELCOME',
        'MESSAGE_TYPE_BROADCAST',
        'EVENT_BOT_CREATED',
        'EVENT_BOT_STARTED'
    ])
except ImportError as e:
    import logging
    logging.warning(f"Could not import constants values: {e}")
