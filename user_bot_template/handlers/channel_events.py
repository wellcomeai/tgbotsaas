"""
Channel Events Handler - обработка событий канала
"""

import logging
from telegram import Update, ChatJoinRequest
from telegram.ext import ContextTypes
from telegram.error import TelegramError

class ChannelEventsHandler:
    def __init__(self, db, config):
        self.db = db
        self.config = config
        self.admin_chat_id = config['ADMIN_CHAT_ID']
        self.auto_approve = config.get('AUTO_APPROVE_REQUESTS', True)
    
    async def handle_join_request(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle channel join requests"""
        try:
            join_request: ChatJoinRequest = update.chat_join_request
            user = join_request.from_user
            chat = join_request.chat
            
            logging.info(f"Join request from user {user.id} ({user.username}) to chat {chat.id}")
            
            # Add user to database
            self.db.add_user(
                user_id=user.id,
                username=user.username,
                first_name=user.first_name,
                last_name=user.last_name,
                utm_source='channel_join'
            )
            
            # Check auto-approve setting
            auto_approve_enabled = self.db.get_setting('auto_approve', 'true') == 'true'
            
            if auto_approve_enabled and self.auto_approve:
                # Auto-approve the request
                try:
                    await join_request.approve()
                    
                    # Send welcome message if enabled
                    await self._send_welcome_message(user.id, context)
                    
                    # Log approval
                    self.db.log_message(
                        user_id=user.id,
                        message_type='auto_approval',
                        content='User auto-approved to channel',
                        utm_source='auto_approve'
                    )
                    
                    # Notify admin
                    await self._notify_admin_join(user, context, approved=True)
                    
                    logging.info(f"Auto-approved join request from {user.id}")
                    
                except TelegramError as e:
                    logging.error(f"Failed to approve join request: {e}")
                    await self._notify_admin_error(user, context, str(e))
            else:
                # Manual approval needed - notify admin
                await self._notify_admin_join(user, context, approved=False)
                logging.info(f"Join request from {user.id} pending manual approval")
                
        except Exception as e:
            logging.error(f"Error handling join request: {e}")
    
    async def _send_welcome_message(self, user_id: int, context: ContextTypes.DEFAULT_TYPE):
        """Send welcome message to new user"""
        try:
            welcome_message = self.db.get_setting('welcome_message', 
                self.config.get('WELCOME_MESSAGE', 
                    '👋 Добро пожаловать в наш канал! Мы рады видеть тебя здесь.'
                )
            )
            
            if welcome_message and self.config.get('WELCOME_MESSAGE_ENABLED', True):
                await context.bot.send_message(
                    chat_id=user_id,
                    text=welcome_message,
                    parse_mode='Markdown'
                )
                
                # Log welcome message
                self.db.log_message(
                    user_id=user_id,
                    message_type='welcome',
                    content=welcome_message,
                    utm_source='auto_welcome'
                )
                
        except TelegramError as e:
            logging.warning(f"Failed to send welcome message to {user_id}: {e}")
        except Exception as e:
            logging.error(f"Error sending welcome message: {e}")
    
    async def _notify_admin_join(self, user, context: ContextTypes.DEFAULT_TYPE, approved: bool = False):
        """Notify admin about new join request"""
        try:
            username = f"@{user.username}" if user.username else "Без username"
            name = user.first_name or "Без имени"
            
            if approved:
                message = f"""
✅ **Новый участник одобрен автоматически**

👤 **Пользователь:** {name} ({username})
🆔 **ID:** `{user.id}`
🕐 **Время:** {context.bot_data.get('current_time', 'сейчас')}

Пользователь был автоматически добавлен в канал и получил приветственное сообщение.
"""
            else:
                message = f"""
🔔 **Новая заявка на вступление**

👤 **Пользователь:** {name} ({username})
🆔 **ID:** `{user.id}`
🕐 **Время:** {context.bot_data.get('current_time', 'сейчас')}

⚠️ Автоодобрение отключено. Заявка ожидает ручного рассмотрения в настройках канала.
"""
            
            await context.bot.send_message(
                chat_id=self.admin_chat_id,
                text=message,
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logging.error(f"Failed to notify admin: {e}")
    
    async def _notify_admin_error(self, user, context: ContextTypes.DEFAULT_TYPE, error_msg: str):
        """Notify admin about approval error"""
        try:
            username = f"@{user.username}" if user.username else "Без username"
            name = user.first_name or "Без имени"
            
            message = f"""
❌ **Ошибка при автоодобрении**

👤 **Пользователь:** {name} ({username})
🆔 **ID:** `{user.id}`
🚫 **Ошибка:** {error_msg}

Пожалуйста, рассмотрите заявку вручную в настройках канала.
"""
            
            await context.bot.send_message(
                chat_id=self.admin_chat_id,
                text=message,
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logging.error(f"Failed to notify admin about error: {e}")
    
    async def handle_member_left(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle member leaving channel"""
        try:
            left_member = update.message.left_chat_member
            if not left_member:
                return
            
            # Update user status in database
            user = self.db.get_user(left_member.id)
            if user:
                # Mark as inactive instead of deleting
                with self.db.get_connection() as conn:
                    conn.execute('''
                        UPDATE users SET is_active = 0, last_activity = CURRENT_TIMESTAMP 
                        WHERE user_id = ?
                    ''', (left_member.id,))
                    conn.commit()
                
                # Send farewell message if enabled
                await self._send_farewell_message(left_member.id, context)
                
                # Log event
                self.db.log_message(
                    user_id=left_member.id,
                    message_type='member_left',
                    content='User left the channel',
                    utm_source='channel_event'
                )
                
                # Notify admin
                await self._notify_admin_left(left_member, context)
                
                logging.info(f"User {left_member.id} left the channel")
                
        except Exception as e:
            logging.error(f"Error handling member left: {e}")
    
    async def _send_farewell_message(self, user_id: int, context: ContextTypes.DEFAULT_TYPE):
        """Send farewell message to user who left"""
        try:
            farewell_message = self.db.get_setting('farewell_message',
                self.config.get('FAREWELL_MESSAGE', 
                    '👋 До свидания! Будем скучать. Возвращайся к нам в любое время!'
                )
            )
            
            if farewell_message and self.config.get('FAREWELL_MESSAGE_ENABLED', True):
                await context.bot.send_message(
                    chat_id=user_id,
                    text=farewell_message,
                    parse_mode='Markdown'
                )
                
                # Log farewell message
                self.db.log_message(
                    user_id=user_id,
                    message_type='farewell',
                    content=farewell_message,
                    utm_source='auto_farewell'
                )
                
        except TelegramError as e:
            logging.warning(f"Failed to send farewell message to {user_id}: {e}")
        except Exception as e:
            logging.error(f"Error sending farewell message: {e}")
    
    async def _notify_admin_left(self, user, context: ContextTypes.DEFAULT_TYPE):
        """Notify admin about user leaving"""
        try:
            username = f"@{user.username}" if user.username else "Без username"
            name = user.first_name or "Без имени"
            
            message = f"""
👋 **Пользователь покинул канал**

👤 **Пользователь:** {name} ({username})
🆔 **ID:** `{user.id}`
🕐 **Время:** {context.bot_data.get('current_time', 'сейчас')}

Пользователь был помечен как неактивный в базе данных.
"""
            
            await context.bot.send_message(
                chat_id=self.admin_chat_id,
                text=message,
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logging.error(f"Failed to notify admin about user leaving: {e}")
    
    async def handle_new_member(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle new member added to channel"""
        try:
            new_members = update.message.new_chat_members
            if not new_members:
                return
            
            for member in new_members:
                # Skip bots
                if member.is_bot:
                    continue
                
                # Add to database
                self.db.add_user(
                    user_id=member.id,
                    username=member.username,
                    first_name=member.first_name,
                    last_name=member.last_name,
                    utm_source='channel_invite'
                )
                
                # Send welcome message
                await self._send_welcome_message(member.id, context)
                
                # Log event
                self.db.log_message(
                    user_id=member.id,
                    message_type='member_added',
                    content='User added to channel',
                    utm_source='channel_event'
                )
                
                logging.info(f"New member added: {member.id}")
                
        except Exception as e:
            logging.error(f"Error handling new member: {e}")
    
    def get_channel_stats(self) -> dict:
        """Get channel statistics"""
        try:
            stats = self.db.get_dashboard_stats()
            
            # Add channel-specific stats
            with self.db.get_connection() as conn:
                # Join requests processed
                cursor = conn.execute('''
                    SELECT COUNT(*) FROM messages 
                    WHERE message_type IN ('auto_approval', 'member_added')
                    AND sent_at > datetime('now', '-30 days')
                ''')
                join_requests = cursor.fetchone()[0]
                
                # Recent activity
                cursor = conn.execute('''
                    SELECT COUNT(*) FROM users 
                    WHERE last_activity > datetime('now', '-7 days')
                ''')
                recent_activity = cursor.fetchone()[0]
                
                stats.update({
                    'join_requests_30d': join_requests,
                    'recent_activity_7d': recent_activity,
                    'auto_approve_enabled': self.db.get_setting('auto_approve', 'true') == 'true'
                })
            
            return stats
            
        except Exception as e:
            logging.error(f"Error getting channel stats: {e}")
            return {}
