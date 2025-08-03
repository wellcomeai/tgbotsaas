"""
User Bot Handlers Module - обработчики пользовательских ботов
"""

# Безопасные импорты с обработкой ошибок
__all__ = []

try:
    from .admin_commands import AdminCommandsHandler
    __all__.append('AdminCommandsHandler')
except ImportError as e:
    import logging
    logging.warning(f"Could not import AdminCommandsHandler: {e}")

try:
    from .channel_events import ChannelEventsHandler
    __all__.append('ChannelEventsHandler')
except ImportError as e:
    import logging
    logging.warning(f"Could not import ChannelEventsHandler: {e}")

try:
    from .messaging import MessagingHandler
    __all__.append('MessagingHandler')
except ImportError as e:
    import logging
    logging.warning(f"Could not import MessagingHandler: {e}")
