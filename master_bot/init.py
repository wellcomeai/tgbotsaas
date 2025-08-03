"""
Master Bot Module - главный бот SaaS платформы
"""

__version__ = "1.0.0-mvp"

# Безопасные импорты с обработкой ошибок
__all__ = []

try:
    from .database import MasterDatabase
    __all__.append('MasterDatabase')
except ImportError as e:
    import logging
    logging.warning(f"Could not import MasterDatabase: {e}")

try:
    from .main import MasterBot
    __all__.append('MasterBot')
except ImportError as e:
    import logging
    logging.warning(f"Could not import MasterBot: {e}")
