"""
Admin Panel - интерфейс управления для владельца бота
"""

import logging
from typing import Dict, List
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

class AdminPanel:
    def __init__(self, db, config):
        self.db = db
        self.config = config
        self.admin_chat_id = config['ADMIN_CHAT_ID']
    
    def is_admin(self, user_id: int) -> bool:
        """Check if user is bot admin"""
        return user_id == self.admin_chat_id
    
    def get_main_menu_markup(self) -> InlineKeyboardMarkup:
        """Get main admin menu keyboard"""
        keyboard = [
            [InlineKeyboardButton("📊 Статистика", callback_data="admin_stats")],
            [InlineKeyboardButton("✉️ Управление рассылкой", callback_data="admin_broadcast")],
            [InlineKeyboardButton("👥 Управление пользователями", callback_data="admin_users")],
            [InlineKeyboardButton("⚙️ Настройки бота", callback_data="admin_settings")],
            [InlineKeyboardButton("📢 Отправить всем", callback_data="admin_mass_send")],
            [InlineKeyboardButton("❓ Помощь", callback_data="admin_help")]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    def get_main_menu_message(self) -> str:
        """Get main admin menu message"""
        stats = self.db.get_dashboard_stats()
        
        message = f"""
🔧 **Админ-панель твоего бота**

📊 **Быстрая статистика:**
• Подписчиков канала: {stats['total_subscribers']}
• Активных пользователей: {stats['active_users']}
• Отправлено сообщений: {stats['messages_sent']}
• Переходов по ссылкам: {stats['link_clicks']}

⚙️ **Управление:**
Выберите действие из меню ниже
"""
        return message
    
    def get_stats_message(self) -> str:
        """Get detailed statistics message"""
        stats = self.db.get_dashboard_stats()
        message_stats = self.db.get_message_stats(30)
        click_stats = self.db.get_click_stats(30)
        
        message = f"""
📊 **Подробная статистика**

**👥 Пользователи:**
• Всего подписчиков: {stats['total_subscribers']}
• Активных (7 дней): {stats['active_users']}
• Взаимодействовали с ботом: {stats['bot_interactions']}

**📬 Сообщения (30 дней):**
• Всего отправлено: {message_stats['total_messages']}
• Уникальных получателей: {message_stats['unique_recipients']}
• Рассылок создано: {stats['recent_broadcasts']}

**🔗 Переходы по ссылкам (30 дней):**
• Всего кликов: {click_stats['total_clicks']}
• Уникальных пользователей: {click_stats['unique_clickers']}
• Уникальных ссылок: {click_stats['unique_urls']}

**📈 Эффективность:**
• CTR (клики/сообщения): {(click_stats['total_clicks'] / max(message_stats['total_messages'], 1) * 100):.1f}%
• Вовлеченность: {(stats['active_users'] / max(stats['total_subscribers'], 1) * 100):.1f}%
"""
        
        return message
    
    def get_stats_keyboard(self) -> InlineKeyboardMarkup:
        """Get statistics keyboard"""
        keyboard = [
            [InlineKeyboardButton("📈 Экспорт данных", callback_data="admin_export")],
            [InlineKeyboardButton("🔄 Обновить", callback_data="admin_stats")],
            [InlineKeyboardButton("🔙 Главное меню", callback_data="admin_main")]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    def get_broadcast_menu_message(self) -> str:
        """Get broadcast management message"""
        return """
✉️ **Управление рассылками**

**Доступные действия:**
• Создать новую рассылку
• Посмотреть историю рассылок
• Настроить автоматические сообщения

**Типы рассылок:**
📢 **Обычная рассылка** - отправка всем подписчикам
👋 **Приветственное сообщение** - для новых участников
👥 **Целевая рассылка** - для определенной группы

Выберите действие:
"""
    
    def get_broadcast_keyboard(self) -> InlineKeyboardMarkup:
        """Get broadcast management keyboard"""
        keyboard = [
            [InlineKeyboardButton("📢 Создать рассылку", callback_data="broadcast_create")],
            [InlineKeyboardButton("📋 История рассылок", callback_data="broadcast_history")],
            [InlineKeyboardButton("👋 Приветственное сообщение", callback_data="broadcast_welcome")],
            [InlineKeyboardButton("🔙 Главное меню", callback_data="admin_main")]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    def get_users_menu_message(self) -> str:
        """Get user management message"""
        stats = self.db.get_dashboard_stats()
        
        return f"""
👥 **Управление пользователями**

**Текущие показатели:**
• Всего пользователей: {stats['total_subscribers']}
• Активных за неделю: {stats['active_users']}
• Взаимодействовали с ботом: {stats['bot_interactions']}

**Доступные действия:**
• Просмотр списка пользователей
• Статистика активности
• Экспорт базы пользователей
• Массовая рассылка

Что хотите сделать?
"""
    
    def get_users_keyboard(self) -> InlineKeyboardMarkup:
        """Get user management keyboard"""
        keyboard = [
            [InlineKeyboardButton("📋 Список пользователей", callback_data="users_list")],
            [InlineKeyboardButton("📊 Статистика активности", callback_data="users_activity")],
            [InlineKeyboardButton("📤 Экспорт данных", callback_data="users_export")],
            [InlineKeyboardButton("🔙 Главное меню", callback_data="admin_main")]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    def get_settings_menu_message(self) -> str:
        """Get settings menu message"""
        welcome_msg = self.db.get_setting('welcome_message', 'Не настроено')
        auto_approve = self.db.get_setting('auto_approve', 'true')
        
        return f"""
⚙️ **Настройки бота**

**Текущие настройки:**
• Автоодобрение заявок: {'✅ Включено' if auto_approve == 'true' else '❌ Выключено'}
• Приветственное сообщение: {'✅ Настроено' if welcome_msg != 'Не настроено' else '❌ Не настроено'}
• UTM трекинг: {'✅ Включен' if self.config.get('UTM_TRACKING_ENABLED') else '❌ Выключен'}

**ID канала:** {self.config.get('CHANNEL_ID', 'Не настроен')}
**Имя бота:** @{self.config.get('BOT_USERNAME')}

Что хотите изменить?
"""
    
    def get_settings_keyboard(self) -> InlineKeyboardMarkup:
        """Get settings keyboard"""
        keyboard = [
            [InlineKeyboardButton("🔄 Автоодобрение заявок", callback_data="settings_auto_approve")],
            [InlineKeyboardButton("👋 Приветственное сообщение", callback_data="settings_welcome")],
            [InlineKeyboardButton("🔗 Настройка канала", callback_data="settings_channel")],
            [InlineKeyboardButton("📊 UTM трекинг", callback_data="settings_utm")],
            [InlineKeyboardButton("🔙 Главное меню", callback_data="admin_main")]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    def get_help_message(self) -> str:
        """Get help message"""
        return f"""
❓ **Помощь по использованию бота**

**🚀 Быстрый старт:**
1. Добавьте бота в канал как администратора
2. Дайте права: "Удаление сообщений" и "Приглашение пользователей"
3. Настройте приветственное сообщение
4. Включите автоодобрение заявок

**📋 Основные функции:**

**📊 Статистика**
• Количество подписчиков
• Активность пользователей  
• Клики по ссылкам
• Эффективность рассылок

**✉️ Рассылки**
• Отправка сообщений всем подписчикам
• Планирование рассылок
• Приветственные сообщения
• UTM трекинг ссылок

**👥 Управление**
• Просмотр пользователей
• Экспорт базы данных
• Модерация участников

**⚙️ Настройки**
• Автоматическое одобрение заявок
• Настройка сообщений
• Конфигурация канала

**💬 Поддержка**
Если нужна помощь - обратитесь к @BotFactorySupport

**Бот создан через Bot Factory** 🤖
"""
    
    def get_help_keyboard(self) -> InlineKeyboardMarkup:
        """Get help keyboard"""
        keyboard = [
            [InlineKeyboardButton("💬 Связаться с поддержкой", url="https://t.me/BotFactorySupport")],
            [InlineKeyboardButton("📖 Полная документация", callback_data="help_docs")],
            [InlineKeyboardButton("🔙 Главное меню", callback_data="admin_main")]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    def format_user_list(self, users: List[Dict], page: int = 0, per_page: int = 10) -> str:
        """Format user list for display"""
        start = page * per_page
        end = start + per_page
        page_users = users[start:end]
        
        message = f"👥 **Пользователи канала** (стр. {page + 1})\n\n"
        
        for i, user in enumerate(page_users, 1):
            username = f"@{user['username']}" if user['username'] else "Без username"
            name = user['first_name'] or "Без имени"
            joined = user['joined_at'][:16] if user['joined_at'] else "Неизвестно"
            activity = user['last_activity'][:16] if user['last_activity'] else "Никогда"
            
            message += f"""
**{start + i}.** {name} ({username})
    📅 Присоединился: {joined}
    🕐 Последняя активность: {activity}
    🤖 Статус: {'✅ Активен' if user['is_active'] else '❌ Неактивен'}
"""
        
        if len(users) > end:
            message += f"\n... и еще {len(users) - end} пользователей"
        
        return message
    
    def get_pagination_keyboard(self, current_page: int, total_pages: int, 
                               callback_prefix: str) -> InlineKeyboardMarkup:
        """Get pagination keyboard"""
        keyboard = []
        
        # Navigation buttons
        nav_buttons = []
        if current_page > 0:
            nav_buttons.append(InlineKeyboardButton("⬅️", callback_data=f"{callback_prefix}_{current_page - 1}"))
        
        nav_buttons.append(InlineKeyboardButton(f"{current_page + 1}/{total_pages}", callback_data="noop"))
        
        if current_page < total_pages - 1:
            nav_buttons.append(InlineKeyboardButton("➡️", callback_data=f"{callback_prefix}_{current_page + 1}"))
        
        if nav_buttons:
            keyboard.append(nav_buttons)
        
        # Back button
        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="admin_users")])
        
        return InlineKeyboardMarkup(keyboard)
