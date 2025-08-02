"""
Bot Manager Module - управление пользовательскими ботами
"""

__version__ = "1.0.0-mvp"

# Безопасные импорты с обработкой ошибок
__all__ = []

try:
    from .process_manager import BotProcessManager
    __all__.append('BotProcessManager')
except ImportError as e:
    import logging
    logging.warning(f"Could not import BotProcessManager: {e}")

try:
    from .config_generator import BotConfigGenerator
    __all__.append('BotConfigGenerator')
except ImportError as e:
    import logging
    logging.warning(f"Could not import BotConfigGenerator: {e}")

try:
    from .health_monitor import HealthMonitor
    __all__.append('HealthMonitor')
except ImportError as e:
    import logging
    logging.warning(f"Could not import HealthMonitor: {e}")
