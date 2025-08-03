"""
User Bot Template Module - шаблон пользовательских ботов
"""

__version__ = "1.0.0-mvp"

# Безопасные импорты с обработкой ошибок
__all__ = []

try:
    from .database import Database
    __all__.append('Database')
except ImportError as e:
    import logging
    logging.warning(f"Could not import Database: {e}")

try:
    from .admin_panel import AdminPanel
    __all__.append('AdminPanel')
except ImportError as e:
    import logging
    logging.warning(f"Could not import AdminPanel: {e}")

# NOTE: НЕ импортируем main.py напрямую, чтобы избежать парсинга аргументов при импорте модуля
# UserBot импортируется только при прямом запуске модуля
# try:
#     from .main import UserBot
#     __all__.append('UserBot')
# except ImportError as e:
#     import logging
#     logging.warning(f"Could not import UserBot: {e}")
