"""
Admin Commands Handler - обработка административных команд
"""

import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

class AdminCommandsHandler:
    def __init__(self, db, config, admin_panel):
        self.db = db
        self.config = config
        self.admin_panel = admin_panel
        self.admin_chat_id = config['ADMIN_CHAT_ID']
    
    async def handle_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        user = update.effective_user
        user_id = user.id
        
        # Add user to database
        self.db.add_user(
            user_id=user_id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name
        )
        
        if self.admin_panel.is_admin(user_id):
            # Admin accessing bot
            await self.show_admin_dashboard(update, context)
        else:
            # Regular user accessing bot
            self.db.set_user_bot_started(user_id)
            await self.show_user_welcome(update, context)
    
    async def show_admin_dashboard(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show main admin dashboard"""
        message = self.admin_panel.get_main_menu_message()
        keyboard = self.admin_panel.get_main_menu_markup()
        
        if update.callback_query:
            await update.callback_query.edit_message_text(
                message,
                reply_markup=keyboard,
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(
                message,
                reply_markup=keyboard,
                parse_mode='Markdown'
            )
    
    async def show_user_welcome(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show welcome message to regular users"""
        welcome_message = self.db.get_setting('welcome_message', 
            f"👋 Привет! Этот бот управляет каналом @{self.config.get('BOT_USERNAME', 'channel')}.\n\n"
            "Если ты хочешь создать своего бота, обратись к @BotFactoryMasterBot"
        )
        
        await update.message.reply_text(welcome_message)
    
    async def handle_admin(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /admin command"""
        if not self.admin_panel.is_admin(update.effective_user.id):
            await update.message.reply_text("❌ У вас нет прав для этого действия")
            return
        
        await self.show_admin_dashboard(update, context)
    
    async def handle_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /stats command"""
        if not self.admin_panel.is_admin(update.effective_user.id):
            await update.message.reply_text("❌ У вас нет прав для этого действия")
            return
        
        message = self.admin_panel.get_stats_message()
        keyboard = self.admin_panel.get_stats_keyboard()
        
        await update.message.reply_text(
            message,
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
    
    async def handle_broadcast(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /broadcast command"""
        if not self.admin_panel.is_admin(update.effective_user.id):
            await update.message.reply_text("❌ У вас нет прав для этого действия")
            return
        
        # Extract broadcast message from command
        args = context.args
        if not args:
            await update.message.reply_text(
                "📢 **Использование команды /broadcast**\n\n"
                "Формат: `/broadcast Ваше сообщение для рассылки`\n\n"
                "Или используйте админ-панель для создания рассылки: /admin",
                parse_mode='Markdown'
            )
            return
        
        broadcast_text = ' '.join(args)
        await self.send_broadcast(update, context, broadcast_text)
    
    async def send_broadcast(self, update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
        """Send broadcast message to all users"""
        try:
            # Get all active users
            users = self.db.get_active_users()
            
            if not users:
                await update.message.reply_text("❌ Нет активных пользователей для рассылки")
                return
            
            # Create broadcast record
            broadcast_id = self.db.create_broadcast(
                title="Быстрая рассылка",
                content=text,
                utm_source="admin_broadcast"
            )
            
            # Send status message
            status_msg = await update.message.reply_text(
                f"🔄 Отправляю рассылку {len(users)} пользователям..."
            )
            
            successful_sends = 0
            failed_sends = 0
            
            # Send to each user
            for user in users:
                try:
                    await context.bot.send_message(
                        chat_id=user['user_id'],
                        text=text,
                        parse_mode='Markdown'
                    )
                    
                    # Log message
                    self.db.log_message(
                        user_id=user['user_id'],
                        message_type='broadcast',
                        content=text,
                        utm_source='admin_broadcast'
                    )
                    
                    successful_sends += 1
                    
                except Exception as e:
                    logging.warning(f"Failed to send to user {user['user_id']}: {e}")
                    failed_sends += 1
            
            # Update broadcast stats
            self.db.update_broadcast_stats(
                broadcast_id=broadcast_id,
                total_recipients=len(users),
                successful_sends=successful_sends,
                failed_sends=failed_sends
            )
            
            # Update status message
            await status_msg.edit_text(
                f"✅ **Рассылка завершена!**\n\n"
                f"📊 Результаты:\n"
                f"• Получателей: {len(users)}\n"
                f"• Доставлено: {successful_sends}\n"
                f"• Ошибок: {failed_sends}\n"
                f"• Успешность: {(successful_sends/len(users)*100):.1f}%",
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logging.error(f"Broadcast error: {e}")
            await update.message.reply_text(
                f"❌ Ошибка при отправке рассылки: {str(e)}"
            )
    
    async def handle_callback_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle callback queries from admin panel"""
        query = update.callback_query
        data = query.data
        
        await query.answer()
        
        try:
            if data == "admin_main":
                await self.show_admin_dashboard(update, context)
            
            elif data == "admin_stats":
                await self.show_admin_stats(update, context)
            
            elif data == "admin_broadcast":
                await self.show_broadcast_menu(update, context)
            
            elif data == "admin_users":
                await self.show_users_menu(update, context)
            
            elif data == "admin_settings":
                await self.show_settings_menu(update, context)
            
            elif data == "admin_mass_send":
                await self.show_mass_send_menu(update, context)
            
            elif data == "admin_help":
                await self.show_help_menu(update, context)
            
            elif data.startswith("broadcast_"):
                await self.handle_broadcast_callback(update, context, data)
            
            elif data.startswith("users_"):
                await self.handle_users_callback(update, context, data)
            
            elif data.startswith("settings_"):
                await self.handle_settings_callback(update, context, data)
            
            else:
                await query.answer("🚧 Функция в разработке")
                
        except Exception as e:
            logging.error(f"Callback query error: {e}")
            await query.answer("❌ Произошла ошибка")
    
    async def show_admin_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show detailed statistics"""
        message = self.admin_panel.get_stats_message()
        keyboard = self.admin_panel.get_stats_keyboard()
        
        await update.callback_query.edit_message_text(
            message,
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
    
    async def show_broadcast_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show broadcast management menu"""
        message = self.admin_panel.get_broadcast_menu_message()
        keyboard = self.admin_panel.get_broadcast_keyboard()
        
        await update.callback_query.edit_message_text(
            message,
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
    
    async def show_users_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show user management menu"""
        message = self.admin_panel.get_users_menu_message()
        keyboard = self.admin_panel.get_users_keyboard()
        
        await update.callback_query.edit_message_text(
            message,
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
    
    async def show_settings_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show settings menu"""
        message = self.admin_panel.get_settings_menu_message()
        keyboard = self.admin_panel.get_settings_keyboard()
        
        await update.callback_query.edit_message_text(
            message,
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
    
    async def show_mass_send_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show mass send interface"""
        message = """
📢 **Массовая рассылка**

Отправьте следующим сообщением текст, который хотите разослать всем подписчикам канала.

**Возможности:**
- Поддержка Markdown разметки
- Автоматический UTM трекинг ссылок  
- Статистика доставки
- Защита от спама

**Пример сообщения:**
🎉 Новая акция в нашем магазине!
Скидка 20% на все товары до конца недели.
Переходите по ссылке: https://example.com
#акция #скидка
Отправьте сообщение или вернитесь в меню:
"""
        
        keyboard = [
            [InlineKeyboardButton("🔙 Назад", callback_data="admin_main")]
        ]
        
        await update.callback_query.edit_message_text(
            message,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        
        # Set user state for next message
        context.user_data['waiting_for_broadcast'] = True
    
    async def show_help_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show help menu"""
        message = self.admin_panel.get_help_message()
        keyboard = self.admin_panel.get_help_keyboard()
        
        await update.callback_query.edit_message_text(
            message,
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
    
    async def handle_broadcast_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE, data: str):
        """Handle broadcast-related callbacks"""
        if data == "broadcast_create":
            await update.callback_query.answer("🚧 Создание рассылки в разработке")
        elif data == "broadcast_history":
            await update.callback_query.answer("🚧 История рассылок в разработке")
        elif data == "broadcast_welcome":
            await update.callback_query.answer("🚧 Настройка приветствия в разработке")
    
    async def handle_users_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE, data: str):
        """Handle user management callbacks"""
        if data == "users_list":
            await self.show_users_list(update, context)
        elif data == "users_activity":
            await update.callback_query.answer("🚧 Статистика активности в разработке")
        elif data == "users_export":
            await update.callback_query.answer("🚧 Экспорт данных в разработке")
    
    async def show_users_list(self, update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 0):
        """Show paginated users list"""
        users = self.db.get_active_users()
        
        if not users:
            await update.callback_query.edit_message_text(
                "👥 **Пользователи канала**\n\nПользователей пока нет."
            )
            return
        
        per_page = 5
        total_pages = (len(users) + per_page - 1) // per_page
        
        message = self.admin_panel.format_user_list(users, page, per_page)
        keyboard = self.admin_panel.get_pagination_keyboard(page, total_pages, "users_page")
        
        await update.callback_query.edit_message_text(
            message,
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
    
    async def handle_settings_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE, data: str):
        """Handle settings callbacks"""
        if data == "settings_auto_approve":
            await self.toggle_auto_approve(update, context)
        elif data == "settings_welcome":
            await update.callback_query.answer("🚧 Настройка приветствия в разработке")
        elif data == "settings_channel":
            await update.callback_query.answer("🚧 Настройка канала в разработке")
        elif data == "settings_utm":
            await update.callback_query.answer("🚧 UTM настройки в разработке")
    
    async def toggle_auto_approve(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Toggle auto-approve setting"""
        current = self.db.get_setting('auto_approve', 'true')
        new_value = 'false' if current == 'true' else 'true'
        
        self.db.set_setting('auto_approve', new_value)
        
        status = "включено" if new_value == 'true' else "выключено"
        await update.callback_query.answer(f"✅ Автоодобрение {status}")
        
        # Refresh settings menu
        await self.show_settings_menu(update, context)
    
    async def handle_private_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle private messages from admin"""
        # Check if waiting for broadcast message
        if context.user_data.get('waiting_for_broadcast'):
            broadcast_text = update.message.text
            context.user_data['waiting_for_broadcast'] = False
            
            await self.send_broadcast(update, context, broadcast_text)
        else:
            # Default response
            await update.message.reply_text(
                "👋 Привет! Используй /admin для открытия панели управления."
            )
