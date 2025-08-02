"""
Configuration Module - настройки приложения
"""

# Безопасные импорты с обработкой ошибок
__all__ = []

try:
    from .settings import settings, Settings
    __all__.extend(['settings', 'Settings'])
except ImportError as e:
    import logging
    logging.warning(f"Could not import settings: {e}")
    
    # Создаем заглушку для settings если импорт не удался
    class DummySettings:
        def __getattr__(self, name):
            return None
    
    settings = DummySettings()
    Settings = DummySettings
    __all__.extend(['settings', 'Settings'])
