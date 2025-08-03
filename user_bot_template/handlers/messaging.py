"""
Messaging Handler - обработка сообщений и рассылок
"""

import logging
import re
import asyncio
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from telegram import Update
from telegram.ext import ContextTypes
from telegram.error import TelegramError

class MessagingHandler:
    def __init__(self, db, config):
        self.db = db
        self.config = config
        self.admin_chat_id = config['ADMIN_CHAT_ID']
        self.utm_tracking_enabled = config.get('UTM_TRACKING_ENABLED', True)
        self.broadcast_delay = config.get('BROADCAST_DELAY', 1)
        self.max_broadcast_size = config.get('MAX_BROADCAST_SIZE', 1000)
    
    async def handle_channel_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle messages in channel/group"""
        try:
            message = update.message
            if not message:
                return
            
            # Skip if message is from bot itself
            if message.from_user and message.from_user.is_bot:
                return
            
            # Log channel activity
            if message.from_user:
                self.db.update_user_activity(message.from_user.id)
            
            # Process URLs in message for tracking
            if message.text and self.utm_tracking_enabled:
                await self._process_message_links(message, context)
            
        except Exception as e:
            logging.error(f"Error handling channel message: {e}")
    
    async def _process_message_links(self, message, context: ContextTypes.DEFAULT_TYPE):
        """Process and track links in messages"""
        try:
            text = message.text
            urls = re.findall(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', text)
            
            for url in urls:
                # Add UTM parameters if enabled
                if self.utm_tracking_enabled:
                    utm_url = self._add_utm_parameters(url, 'channel_message', 'organic')
                    
                    # Log URL for tracking
                    self.db.log_message(
                        user_id=message.from_user.id if message.from_user else None,
                        message_type='url_shared',
                        content=f"Original: {url}, UTM: {utm_url}",
                        utm_source='channel_message'
                    )
            
        except Exception as e:
            logging.error(f"Error processing message links: {e}")
    
    def _add_utm_parameters(self, url: str, source: str = 'bot', campaign: str = 'default', 
                           medium: str = 'telegram') -> str:
        """Add UTM parameters to URL"""
        try:
            parsed = urlparse(url)
            query_params = parse_qs(parsed.query)
            
            # Add UTM parameters if not already present
            utm_params = {
                'utm_source': source,
                'utm_medium': medium,
                'utm_campaign': campaign,
                'utm_content': f"bot_{self.config.get('BOT_ID', 'unknown')}"
            }
            
            for key, value in utm_params.items():
                if key not in query_params:
                    query_params[key] = [value]
            
            # Rebuild URL
            new_query = urlencode(query_params, doseq=True)
            new_parsed = parsed._replace(query=new_query)
            
            return urlunparse(new_parsed)
            
        except Exception as e:
            logging.error(f"Error adding UTM parameters: {e}")
            return url  # Return original URL if error
    
    async def send_broadcast_message(self, content: str, users: list = None, 
                                   utm_source: str = 'broadcast', utm_campaign: str = 'manual',
                                   title: str = "Рассылка") -> dict:
        """Send broadcast message to users"""
        try:
            # Get recipients
            if users is None:
                users = self.db.get_active_users()
            
            if not users:
                return {
                    'success': False,
                    'error': 'No active users to send to',
                    'total': 0,
                    'successful': 0,
                    'failed': 0
                }
            
            # Limit broadcast size
            if len(users) > self.max_broadcast_size:
                users = users[:self.max_broadcast_size]
                logging.warning(f"Broadcast limited to {self.max_broadcast_size} users")
            
            # Create broadcast record
            broadcast_id = self.db.create_broadcast(
                title=title,
                content=content,
                utm_source=utm_source,
                utm_campaign=utm_campaign
            )
            
            # Process content (add UTM to links)
            processed_content = self._process_broadcast_content(content, utm_source, utm_campaign)
            
            successful_sends = 0
            failed_sends = 0
            failed_users = []
            
            # Send to each user with delay
            for i, user in enumerate(users):
                try:
                    # Send message
                    await self._send_single_message(
                        user_id=user['user_id'],
                        content=processed_content,
                        utm_source=utm_source,
                        utm_campaign=utm_campaign
                    )
                    
                    successful_sends += 1
                    
                    # Add delay between messages to avoid rate limits
                    if i < len(users) - 1:  # Don't delay after last message
                        await asyncio.sleep(self.broadcast_delay)
                    
                except TelegramError as e:
                    failed_sends += 1
                    failed_users.append({
                        'user_id': user['user_id'],
                        'error': str(e)
                    })
                    logging.warning(f"Failed to send to user {user['user_id']}: {e}")
                    
                except Exception as e:
                    failed_sends += 1
                    failed_users.append({
                        'user_id': user['user_id'],
                        'error': str(e)
                    })
                    logging.error(f"Unexpected error sending to user {user['user_id']}: {e}")
            
            # Update broadcast statistics
            self.db.update_broadcast_stats(
                broadcast_id=broadcast_id,
                total_recipients=len(users),
                successful_sends=successful_sends,
                failed_sends=failed_sends
            )
            
            return {
                'success': True,
                'broadcast_id': broadcast_id,
                'total': len(users),
                'successful': successful_sends,
                'failed': failed_sends,
                'failed_users': failed_users,
                'success_rate': (successful_sends / len(users)) * 100 if users else 0
            }
            
        except Exception as e:
            logging.error(f"Error in broadcast: {e}")
            return {
                'success': False,
                'error': str(e),
                'total': len(users) if users else 0,
                'successful': 0,
                'failed': 0
            }
    
    async def _send_single_message(self, user_id: int, content: str, 
                                  utm_source: str = None, utm_campaign: str = None):
        """Send single message to user"""
        try:
            from telegram import Bot
            bot = Bot(token=self.config['BOT_TOKEN'])
            
            await bot.send_message(
                chat_id=user_id,
                text=content,
                parse_mode='Markdown'
            )
            
            # Log message
            self.db.log_message(
                user_id=user_id,
                message_type='broadcast',
                content=content[:200],  # Truncate for storage
                utm_source=utm_source,
                utm_campaign=utm_campaign
            )
            
        except Exception as e:
            raise e  # Re-raise to be handled by caller
    
    def _process_broadcast_content(self, content: str, utm_source: str, utm_campaign: str) -> str:
        """Process broadcast content - add UTM to links"""
        try:
            if not self.utm_tracking_enabled:
                return content
            
            # Find all URLs
            url_pattern = r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
            urls = re.findall(url_pattern, content)
            
            processed_content = content
            
            # Replace each URL with UTM version
            for url in urls:
                utm_url = self._add_utm_parameters(url, utm_source, utm_campaign, 'telegram')
                processed_content = processed_content.replace(url, utm_url)
            
            return processed_content
            
        except Exception as e:
            logging.error(f"Error processing broadcast content: {e}")
            return content  # Return original content if error
    
    async def send_welcome_sequence(self, user_id: int, context: ContextTypes.DEFAULT_TYPE):
        """Send welcome message sequence to new user"""
        try:
            welcome_message = self.db.get_setting('welcome_message',
                self.config.get('WELCOME_MESSAGE', 
                    '👋 Добро пожаловать! Спасибо за подписку на наш канал.'
                )
            )
            
            if not welcome_message:
                return
            
            # Process welcome message (add UTM)
            processed_message = self._process_broadcast_content(
                welcome_message, 'welcome', 'auto_welcome'
            )
            
            # Send welcome message
            await context.bot.send_message(
                chat_id=user_id,
                text=processed_message,
                parse_mode='Markdown'
            )
            
            # Log welcome message
            self.db.log_message(
                user_id=user_id,
                message_type='welcome',
                content=processed_message[:200],
                utm_source='welcome',
                utm_campaign='auto_welcome'
            )
            
            logging.info(f"Welcome message sent to user {user_id}")
            
        except Exception as e:
            logging.error(f"Error sending welcome sequence: {e}")
    
    async def track_link_click(self, user_id: int, original_url: str, 
                              utm_source: str = None, utm_campaign: str = None,
                              ip_address: str = None):
        """Track link click (for future webhook integration)"""
        try:
            utm_url = self._add_utm_parameters(original_url, utm_source or 'unknown', 
                                              utm_campaign or 'unknown')
            
            self.db.log_link_click(
                user_id=user_id,
                original_url=original_url,
                utm_url=utm_url,
                utm_source=utm_source,
                utm_campaign=utm_campaign,
                ip_address=ip_address
            )
            
            logging.info(f"Link click tracked: user {user_id}, URL {original_url}")
            
        except Exception as e:
            logging.error(f"Error tracking link click: {e}")
    
    def get_broadcast_stats(self, days: int = 30) -> dict:
        """Get broadcast statistics"""
        try:
            message_stats = self.db.get_message_stats(days)
            click_stats = self.db.get_click_stats(days)
            
            # Calculate additional metrics
            ctr = 0
            if message_stats['total_messages'] > 0:
                ctr = (click_stats['total_clicks'] / message_stats['total_messages']) * 100
            
            engagement_rate = 0
            total_users = self.db.get_user_count()
            if total_users > 0:
                engagement_rate = (message_stats['unique_recipients'] / total_users) * 100
            
            return {
                'messages': message_stats,
                'clicks': click_stats,
                'ctr_percent': round(ctr, 2),
                'engagement_rate_percent': round(engagement_rate, 2),
                'avg_clicks_per_message': round(
                    click_stats['total_clicks'] / max(message_stats['total_messages'], 1), 2
                ),
                'total_users': total_users
            }
            
        except Exception as e:
            logging.error(f"Error getting broadcast stats: {e}")
            return {}
    
    def validate_broadcast_content(self, content: str) -> tuple[bool, str]:
        """Validate broadcast content"""
        if not content or not content.strip():
            return False, "Сообщение не может быть пустым"
        
        if len(content) > self.config.get('MAX_MESSAGE_LENGTH', 4000):
            return False, f"Сообщение слишком длинное (максимум {self.config.get('MAX_MESSAGE_LENGTH', 4000)} символов)"
        
        # Check for spam patterns (basic)
        spam_patterns = [
            r'СРОЧНО!!!',
            r'БЕСПЛАТНО!!!',
            r'ТОЛЬКО СЕГОДНЯ!!!',
        ]
        
        for pattern in spam_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                return False, "Сообщение содержит спам-паттерны"
        
        return True, "Сообщение корректно"
