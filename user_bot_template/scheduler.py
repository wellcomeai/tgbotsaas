"""
Scheduler - планировщик для автоматических и массовых рассылок
"""

import asyncio
import logging
from datetime import datetime, timedelta
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.error import TelegramError
from typing import Dict, List
from .utm_utils import process_text_links, create_tracking_link

class MessageScheduler:
    def __init__(self, bot_token: str, database, config: dict):
        self.bot = Bot(token=bot_token)
        self.db = database
        self.config = config
        self.running = False
        self.check_interval = 30  # секунд
        
    async def start(self):
        """Start the scheduler"""
        self.running = True
        logging.info("🕐 Message scheduler started")
        
        while self.running:
            try:
                await self._check_scheduled_messages()
                await self._check_scheduled_broadcasts()
                await self._check_broadcast_status()
                
                await asyncio.sleep(self.check_interval)
                
            except Exception as e:
                logging.error(f"❌ Scheduler error: {e}")
                await asyncio.sleep(60)  # Wait longer on error
    
    def stop(self):
        """Stop the scheduler"""
        self.running = False
        logging.info("🛑 Message scheduler stopped")
    
    async def _check_scheduled_messages(self):
        """Check and send scheduled user messages"""
        try:
            scheduled_messages = self.db.get_scheduled_messages('scheduled')
            
            if not scheduled_messages:
                return
            
            logging.info(f"📝 Found {len(scheduled_messages)} scheduled messages to send")
            
            for msg in scheduled_messages:
                try:
                    await self._send_scheduled_message(msg)
                except Exception as e:
                    logging.error(f"❌ Error sending scheduled message {msg['id']}: {e}")
                    # Mark as failed but don't stop processing others
                    await self._mark_message_failed(msg['id'], str(e))
                    
        except Exception as e:
            logging.error(f"❌ Error checking scheduled messages: {e}")
    
    async def _send_scheduled_message(self, msg: dict):
        """Send single scheduled message"""
        try:
            user_id = msg['user_id']
            message_number = msg['message_number']
            
            # Get message content
            text = msg['text']
            photo_url = msg.get('photo_url')
            
            # Process UTM links
            processed_text = process_text_links(
                text, user_id, 
                source='auto_message',
                campaign=f'sequence_msg_{message_number}'
            )
            
            # Get message buttons
            buttons = self.db.get_message_buttons(message_number)
            reply_markup = None
            
            if buttons:
                # Create inline keyboard for URL buttons
                keyboard = []
                for button in buttons:
                    tracking_url = create_tracking_link(
                        button['button_url'], 
                        user_id, 
                        'auto_message',
                        button['button_text']
                    )
                    keyboard.append([InlineKeyboardButton(
                        button['button_text'], 
                        url=tracking_url
                    )])
                reply_markup = InlineKeyboardMarkup(keyboard)
            
            # Send message
            if photo_url:
                await self.bot.send_photo(
                    chat_id=user_id,
                    photo=photo_url,
                    caption=processed_text,
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
            else:
                await self.bot.send_message(
                    chat_id=user_id,
                    text=processed_text,
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
            
            # Mark as sent
            self.db.mark_message_sent(msg['id'])
            
            # Log message
            self.db.log_message(
                user_id=user_id,
                message_type='auto_message',
                content=processed_text[:200],
                utm_source='auto_message',
                utm_campaign=f'sequence_msg_{message_number}'
            )
            
            logging.info(f"✅ Sent scheduled message {msg['id']} to user {user_id}")
            
        except TelegramError as e:
            if "blocked by the user" in str(e).lower():
                logging.warning(f"⚠️ User {user_id} blocked the bot, marking message as failed")
                await self._mark_message_failed(msg['id'], "User blocked bot")
            else:
                raise e
    
    async def _mark_message_failed(self, message_id: int, error_msg: str):
        """Mark scheduled message as failed"""
        try:
            with self.db.get_connection() as conn:
                conn.execute('''
                    UPDATE scheduled_user_messages 
                    SET status = 'failed', sent_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (message_id,))
                conn.commit()
                
            logging.warning(f"⚠️ Marked message {message_id} as failed: {error_msg}")
            
        except Exception as e:
            logging.error(f"❌ Error marking message as failed: {e}")
    
    async def _check_scheduled_broadcasts(self):
        """Check and send scheduled broadcasts"""
        try:
            broadcasts = self.db.get_scheduled_broadcasts()
            
            if not broadcasts:
                return
            
            logging.info(f"📢 Found {len(broadcasts)} scheduled broadcasts to send")
            
            for broadcast in broadcasts:
                try:
                    await self._send_scheduled_broadcast(broadcast)
                except Exception as e:
                    logging.error(f"❌ Error sending broadcast {broadcast['id']}: {e}")
                    
        except Exception as e:
            logging.error(f"❌ Error checking scheduled broadcasts: {e}")
    
    async def _send_scheduled_broadcast(self, broadcast: dict):
        """Send scheduled broadcast to all users"""
        try:
            broadcast_id = broadcast['id']
            message_text = broadcast['message_text']
            photo_url = broadcast.get('photo_url')
            
            # Get all active users
            users = self.db.get_active_users()
            
            if not users:
                logging.warning(f"⚠️ No active users for broadcast {broadcast_id}")
                self.db.mark_broadcast_sent(broadcast_id)
                return
            
            logging.info(f"📢 Sending broadcast {broadcast_id} to {len(users)} users")
            
            successful_sends = 0
            failed_sends = 0
            
            # Get broadcast buttons if any
            buttons = []
            with self.db.get_connection() as conn:
                cursor = conn.execute('''
                    SELECT * FROM scheduled_broadcast_buttons 
                    WHERE broadcast_id = ? ORDER BY position
                ''', (broadcast_id,))
                buttons = [dict(row) for row in cursor.fetchall()]
            
            # Send to each user
            for user in users:
                try:
                    user_id = user['user_id']
                    
                    # Process UTM links for this user
                    processed_text = process_text_links(
                        message_text, user_id,
                        source='scheduled_broadcast',
                        campaign=f'broadcast_{broadcast_id}'
                    )
                    
                    reply_markup = None
                    if buttons:
                        # Create inline keyboard
                        keyboard = []
                        for button in buttons:
                            tracking_url = create_tracking_link(
                                button['button_url'],
                                user_id,
                                'scheduled_broadcast',
                                button['button_text']
                            )
                            keyboard.append([InlineKeyboardButton(
                                button['button_text'],
                                url=tracking_url
                            )])
                        reply_markup = InlineKeyboardMarkup(keyboard)
                    
                    # Send message
                    if photo_url:
                        await self.bot.send_photo(
                            chat_id=user_id,
                            photo=photo_url,
                            caption=processed_text,
                            reply_markup=reply_markup,
                            parse_mode='Markdown'
                        )
                    else:
                        await self.bot.send_message(
                            chat_id=user_id,
                            text=processed_text,
                            reply_markup=reply_markup,
                            parse_mode='Markdown'
                        )
                    
                    successful_sends += 1
                    
                    # Log message
                    self.db.log_message(
                        user_id=user_id,
                        message_type='scheduled_broadcast',
                        content=processed_text[:200],
                        utm_source='scheduled_broadcast',
                        utm_campaign=f'broadcast_{broadcast_id}'
                    )
                    
                    # Small delay to avoid rate limits
                    await asyncio.sleep(0.1)
                    
                except TelegramError as e:
                    failed_sends += 1
                    if "blocked by the user" not in str(e).lower():
                        logging.warning(f"⚠️ Failed to send to user {user['user_id']}: {e}")
                
                except Exception as e:
                    failed_sends += 1
                    logging.error(f"❌ Error sending to user {user['user_id']}: {e}")
            
            # Mark broadcast as sent
            self.db.mark_broadcast_sent(broadcast_id)
            
            # Create broadcast record for statistics
            broadcast_record_id = self.db.create_broadcast(
                title=f"Scheduled Broadcast {broadcast_id}",
                content=message_text,
                utm_source='scheduled_broadcast',
                utm_campaign=f'broadcast_{broadcast_id}'
            )
            
            # Update statistics
            self.db.update_broadcast_stats(
                broadcast_id=broadcast_record_id,
                total_recipients=len(users),
                successful_sends=successful_sends,
                failed_sends=failed_sends
            )
            
            logging.info(f"✅ Broadcast {broadcast_id} sent: {successful_sends} success, {failed_sends} failed")
            
            # Notify admin
            await self._notify_admin_broadcast_complete(
                broadcast_id, len(users), successful_sends, failed_sends
            )
            
        except Exception as e:
            logging.error(f"❌ Error sending scheduled broadcast: {e}")
    
    async def _notify_admin_broadcast_complete(self, broadcast_id: int, total: int, 
                                             successful: int, failed: int):
        """Notify admin about broadcast completion"""
        try:
            admin_chat_id = self.config['ADMIN_CHAT_ID']
            
            message = f"""
📢 **Рассылка #{broadcast_id} завершена**

📊 **Результаты:**
• Всего получателей: {total}
• Доставлено: {successful}
• Ошибок: {failed}
• Успешность: {(successful/total*100):.1f}%

🕐 Время: {datetime.now().strftime('%H:%M %d.%m.%Y')}
"""
            
            await self.bot.send_message(
                chat_id=admin_chat_id,
                text=message,
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logging.error(f"❌ Error notifying admin: {e}")
    
    async def _check_broadcast_status(self):
        """Check if broadcasts should be auto-resumed"""
        try:
            status = self.db.get_broadcast_status()
            
            if not status['enabled'] and status['auto_resume_time']:
                resume_time = datetime.fromisoformat(status['auto_resume_time'])
                
                if datetime.now() >= resume_time:
                    # Auto-resume broadcasts
                    self.db.set_broadcast_status(True)
                    
                    # Notify admin
                    await self._notify_admin_auto_resume()
                    
                    logging.info("✅ Auto-resumed broadcasts")
                    
        except Exception as e:
            logging.error(f"❌ Error checking broadcast status: {e}")
    
    async def _notify_admin_auto_resume(self):
        """Notify admin about auto-resume"""
        try:
            admin_chat_id = self.config['ADMIN_CHAT_ID']
            
            message = """
🔄 **Рассылки автоматически возобновлены**

Система автоматически включила рассылки согласно установленному расписанию.

🕐 Время: {}
""".format(datetime.now().strftime('%H:%M %d.%m.%Y'))
            
            await self.bot.send_message(
                chat_id=admin_chat_id,
                text=message,
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logging.error(f"❌ Error notifying admin about auto-resume: {e}")
    
    async def schedule_user_messages(self, user_id: int):
        """Schedule automatic message sequence for new user"""
        try:
            # Get all enabled broadcast messages
            messages = self.db.get_all_broadcast_messages()
            enabled_messages = [msg for msg in messages if msg.get('is_enabled', 1)]
            
            if not enabled_messages:
                logging.info(f"ℹ️ No enabled auto messages for user {user_id}")
                return
            
            base_time = datetime.now()
            scheduled_count = 0
            
            for msg in enabled_messages:
                try:
                    # Calculate send time
                    delay_hours = msg['delay_hours']
                    send_time = base_time + timedelta(hours=delay_hours)
                    
                    # Schedule message
                    self.db.schedule_user_message(
                        user_id=user_id,
                        message_number=msg['message_number'],
                        scheduled_at=send_time
                    )
                    
                    scheduled_count += 1
                    
                    logging.info(f"📅 Scheduled message {msg['message_number']} for user {user_id} at {send_time}")
                    
                except Exception as e:
                    logging.error(f"❌ Error scheduling message {msg['message_number']}: {e}")
            
            logging.info(f"✅ Scheduled {scheduled_count} messages for user {user_id}")
            
        except Exception as e:
            logging.error(f"❌ Error scheduling user messages: {e}")
    
    def cancel_user_messages(self, user_id: int):
        """Cancel all scheduled messages for user"""
        try:
            self.db.cancel_user_messages(user_id)
            logging.info(f"🚫 Cancelled scheduled messages for user {user_id}")
            
        except Exception as e:
            logging.error(f"❌ Error cancelling user messages: {e}")
    
    def get_scheduler_stats(self) -> dict:
        """Get scheduler statistics"""
        try:
            with self.db.get_connection() as conn:
                stats = {}
                
                # Pending scheduled messages
                cursor = conn.execute('''
                    SELECT COUNT(*) FROM scheduled_user_messages 
                    WHERE status = 'scheduled'
                ''')
                stats['pending_user_messages'] = cursor.fetchone()[0]
                
                # Pending broadcasts
                cursor = conn.execute('''
                    SELECT COUNT(*) FROM scheduled_broadcasts 
                    WHERE is_sent = 0 AND cancelled = 0
                ''')
                stats['pending_broadcasts'] = cursor.fetchone()[0]
                
                # Messages sent today
                cursor = conn.execute('''
                    SELECT COUNT(*) FROM scheduled_user_messages 
                    WHERE status = 'sent' 
                    AND sent_at > datetime('now', 'start of day')
                ''')
                stats['messages_sent_today'] = cursor.fetchone()[0]
                
                # Broadcast status
                broadcast_status = self.db.get_broadcast_status()
                stats['broadcasts_enabled'] = broadcast_status['enabled']
                
                return stats
                
        except Exception as e:
            logging.error(f"❌ Error getting scheduler stats: {e}")
            return {}
