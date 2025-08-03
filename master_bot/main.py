"""
Master Bot - главный бот SaaS платформы
Обрабатывает регистрацию, создание ботов, управление
"""

import asyncio
import logging
import re
import sys
import traceback
from pathlib import Path
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# IMPROVED IMPORTS WITH DETAILED LOGGING
try:
    from master_bot.database import MasterDatabase
    logging.info("✅ Successfully imported MasterDatabase")
except ImportError as e:
    logging.error(f"❌ Failed to import MasterDatabase: {e}")
    logging.error(f"Traceback: {traceback.format_exc()}")
    sys.exit(1)

try:
    from shared.telegram_utils import verify_bot_token
    logging.info("✅ Successfully imported verify_bot_token")
except ImportError as e:
    logging.error(f"❌ Failed to import verify_bot_token: {e}")
    logging.error(f"Traceback: {traceback.format_exc()}")
    sys.exit(1)

class MasterBot:
    def __init__(self, bot_token: str):
        self.bot_token = bot_token
        self.db = MasterDatabase()
        self.application = None
        
        logging.info("MasterBot initialized successfully")
        
    async def setup_handlers(self, application: Application):
        """Configure all handlers for master bot"""
        
        # Main handlers
        application.add_handler(CommandHandler("start", self.handle_start))
        application.add_handler(CallbackQueryHandler(self.handle_callback))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_text_input))
        
        logging.info("Master bot handlers configured")
    
    async def handle_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        user = update.effective_user
        user_id = user.id
        
        try:
            # Update user activity
            self.db.update_user_activity(user_id)
            
            # Check if user exists
            db_user = self.db.get_user_by_telegram_id(user_id)
            
            if not db_user:
                # New user registration
                db_user_id = self.db.create_user(
                    telegram_id=user_id,
                    username=user.username,
                    first_name=user.first_name
                )
                
                await self.send_welcome_message(update, context)
            else:
                # Existing user - show dashboard
                await self.show_user_dashboard(update, context, db_user)
                
        except Exception as e:
            logging.error(f"Error in handle_start: {e}")
            await update.message.reply_text("❌ Произошла ошибка. Попробуйте позже.")
    
    async def send_welcome_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Send welcome message to new user"""
        message = """
🤖 <b>Добро пожаловать в Bot Factory!</b>

Создай персонального бота для рассылок в твоем Telegram канале за 2 минуты:

✅ Автоматические рассылки с задержками
✅ Полная админ-панель в Telegram  
✅ Статистика переходов и UTM-трекинг
✅ Управление подписчиками канала

🎁 <b>MVP версия - БЕСПЛАТНО для тестирования</b>

<b>Что умеет твой бот:</b>
• Автоматически одобрять заявки в закрытый канал
• Отправлять рассылки всем участникам
• Показывать статистику переходов
• Управлять приветственными сообщениями

<b>Как это работает:</b>
1. Ты создаешь бота через @BotFather
2. Даешь мне токен - я запускаю твоего бота
3. Добавляешь бота админом в свой канал
4. Управляешь через админ-панель

Готов начать?
"""
        
        keyboard = [
            [InlineKeyboardButton("🚀 Создать первого бота", callback_data="create_bot")],
            [InlineKeyboardButton("📺 Посмотреть пример", callback_data="show_examples")],
            [InlineKeyboardButton("💬 Поддержка", callback_data="contact_support")]
        ]
        
        await update.message.reply_text(
            message,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )
    
    async def show_user_dashboard(self, update: Update, context: ContextTypes.DEFAULT_TYPE, user: dict):
        """Show user dashboard with existing bots"""
        try:
            user_bots = self.db.get_user_bots(user['id'])
            
            if not user_bots:
                await self.send_welcome_message(update, context)
                return
            
            # Safely handle user data
            safe_first_name = user.get('first_name') or "Пользователь"
            
            message = f"🏠 <b>Твоя панель управления</b>\n\n"
            message += f"👋 Привет, {safe_first_name}!\n\n"
            message += f"<b>Твои боты ({len(user_bots)}):</b>\n\n"
            
            keyboard = []
            
            for bot in user_bots:
                status_emoji = {
                    'active': '✅',
                    'creating': '🔄',
                    'stopped': '⏸️',
                    'error': '❌'
                }.get(bot['status'], '❓')
                
                bot_username = bot.get('bot_username', 'unknown')
                bot_status = bot.get('status', 'unknown')
                
                message += f"{status_emoji} @{bot_username} - {bot_status}\n"
                
                keyboard.append([
                    InlineKeyboardButton(f"⚙️ @{bot_username}", callback_data=f"manage_{bot['id']}"),
                    InlineKeyboardButton("📊", callback_data=f"stats_{bot['id']}")
                ])
            
            keyboard.append([InlineKeyboardButton("➕ Создать нового бота", callback_data="create_bot")])
            keyboard.append([InlineKeyboardButton("💬 Поддержка", callback_data="contact_support")])
            
            if update.callback_query:
                await update.callback_query.edit_message_text(
                    message,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode='HTML'
                )
            else:
                await update.message.reply_text(
                    message,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode='HTML'
                )
        except Exception as e:
            logging.error(f"Error showing dashboard: {e}")
            # Fallback без форматирования
            fallback_message = "🏠 Твоя панель управления\n\nДобро пожаловать! Выберите действие из меню ниже."
            
            keyboard = [
                [InlineKeyboardButton("➕ Создать нового бота", callback_data="create_bot")],
                [InlineKeyboardButton("💬 Поддержка", callback_data="contact_support")]
            ]
            
            if update.callback_query:
                await update.callback_query.edit_message_text(
                    fallback_message,
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            else:
                await update.message.reply_text(
                    fallback_message,
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
    
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle callback queries"""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        
        try:
            if data == "create_bot":
                await self.initiate_bot_creation(update, context)
            elif data == "show_examples":
                await self.show_examples(update, context)
            elif data == "contact_support":
                await self.contact_support(update, context)
            elif data.startswith("manage_"):
                bot_id = int(data.split("_")[1])
                await self.manage_bot(update, context, bot_id)
            elif data.startswith("stats_"):
                bot_id = int(data.split("_")[1])
                await self.show_bot_stats(update, context, bot_id)
            elif data.startswith("restart_"):
                bot_id = int(data.split("_")[1])
                await self.restart_bot(update, context, bot_id)
            elif data == "back_to_dashboard":
                user = self.db.get_user_by_telegram_id(update.effective_user.id)
                await self.show_user_dashboard(update, context, user)
            else:
                await query.answer("🚧 Функция в разработке")
                
        except Exception as e:
            logging.error(f"Error in callback handler: {e}")
            await query.answer("❌ Произошла ошибка")
    
    async def initiate_bot_creation(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start bot creation process"""
        context.user_data['creation_step'] = 'waiting_token'
        
        message = """
📝 <b>Создание бота - Шаг 1/3</b>

Сначала создай бота через @BotFather:

<b>Пошаговая инструкция:</b>
1️⃣ Перейди к @BotFather
2️⃣ Отправь команду: /newbot
3️⃣ Придумай имя: "Мой канал помощник"
4️⃣ Придумай username: @mychannel_helper_bot
5️⃣ Получи токен: 123456789:ABC-DEF1234567890

<b>⚠️ Важно:</b>
• Username должен заканчиваться на bot
• Токен выглядит как: числа:буквы-цифры
• Сохрани токен - он нужен только один раз

Когда получишь токен - пришли его мне следующим сообщением.

<b>Пример токена:</b>
<code>1234567890:ABCdefGHI123-456789JKLmnop</code>
"""
        
        keyboard = [
            [InlineKeyboardButton("🔙 Назад", callback_data="back_to_dashboard")],
            [InlineKeyboardButton("❓ Нужна помощь?", callback_data="contact_support")]
        ]
        
        await update.callback_query.edit_message_text(
            message,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )
    
    async def handle_text_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle text messages (bot tokens)"""
        if context.user_data.get('creation_step') == 'waiting_token':
            await self.process_bot_token(update, context)
        else:
            # Default response for unexpected messages
            await update.message.reply_text(
                "👋 Привет! Используй /start для начала работы с Bot Factory."
            )
    
    async def process_bot_token(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Process and validate bot token"""
        token = update.message.text.strip()
        user_id = update.effective_user.id
        
        try:
            logging.info(f"🔄 Processing bot token for user {user_id}")
            
            # Validate token format
            if not re.match(r'^\d+:[A-Za-z0-9_-]+$', token):
                logging.warning(f"❌ Invalid token format from user {user_id}")
                await update.message.reply_text(
                    "❌ <b>Неверный формат токена</b>\n\n"
                    "Токен должен выглядеть так:\n"
                    "<code>1234567890:ABCdefGHI123-456789JKLmnop</code>\n\n"
                    "Попробуй еще раз или нажми /start для возврата в меню.",
                    parse_mode='HTML'
                )
                return
            
            # Show processing message
            processing_msg = await update.message.reply_text("🔄 Проверяю токен...")
            logging.info(f"🔄 Verifying token for user {user_id}")
            
            # Verify token works
            bot_info = await verify_bot_token(token)
            if not bot_info:
                logging.error(f"❌ Token verification failed for user {user_id}")
                await processing_msg.edit_text(
                    "❌ <b>Токен не работает</b>\n\n"
                    "Возможные причины:\n"
                    "• Токен введен неправильно\n"
                    "• Бот заблокирован\n"
                    "• Токен уже недействителен\n\n"
                    "Проверь правильность токена и попробуй еще раз.",
                    parse_mode='HTML'
                )
                return
            
            logging.info(f"✅ Token verified successfully for user {user_id}, bot: @{bot_info['username']}")
            
            # Check if token already exists
            if self.db.bot_exists_by_token(token):
                logging.warning(f"❌ Token already exists for user {user_id}")
                await processing_msg.edit_text(
                    "❌ <b>Этот бот уже зарегистрирован</b>\n\n"
                    "Используй другого бота или обратись в поддержку: /start"
                )
                return
            
            # Create bot record
            db_user = self.db.get_user_by_telegram_id(user_id)
            logging.info(f"🔄 Creating bot record for user {user_id}")
            
            bot_id = self.db.create_user_bot(
                owner_id=db_user['id'],
                bot_token=token,
                bot_username=bot_info['username'],
                bot_display_name=bot_info.get('first_name', bot_info['username'])
            )
            
            logging.info(f"✅ Bot record created with ID {bot_id}")
            await processing_msg.edit_text("✅ Токен принят! Запускаю бота...")
            
            # Deploy bot
            context.user_data['bot_id'] = bot_id
            await self.deploy_user_bot(update, context, bot_info, processing_msg)
            
        except Exception as e:
            logging.error(f"❌ Error processing bot token for user {user_id}: {e}")
            logging.error(f"Traceback: {traceback.format_exc()}")
            await update.message.reply_text("❌ Произошла ошибка при обработке токена")
    
    async def deploy_user_bot(self, update: Update, context: ContextTypes.DEFAULT_TYPE, 
                             bot_info: dict, message_to_edit):
        """Deploy user bot - IMPROVED WITH DETAILED LOGGING"""
        bot_id = context.user_data['bot_id']
        
        try:
            logging.info(f"🚀 Starting deployment for bot {bot_id}")
            
            # IMPROVED IMPORT WITH DETAILED LOGGING
            try:
                logging.info("🔄 Attempting to import BotProcessManager...")
                from bot_manager.process_manager import BotProcessManager
                logging.info("✅ BotProcessManager imported successfully")
            except ImportError as e:
                logging.error(f"❌ CRITICAL: Failed to import BotProcessManager: {e}")
                logging.error(f"Traceback: {traceback.format_exc()}")
                logging.error(f"Python path: {sys.path}")
                
                await self.show_deployment_error(update, context, message_to_edit, 
                    f"Ошибка импорта: {e}")
                return
            except Exception as e:
                logging.error(f"❌ CRITICAL: Unexpected error importing BotProcessManager: {e}")
                logging.error(f"Traceback: {traceback.format_exc()}")
                
                await self.show_deployment_error(update, context, message_to_edit, 
                    f"Неожиданная ошибка импорта: {e}")
                return
            
            # Initialize manager
            try:
                logging.info("🔄 Initializing BotProcessManager...")
                manager = BotProcessManager()
                logging.info("✅ BotProcessManager initialized successfully")
            except Exception as e:
                logging.error(f"❌ Failed to initialize BotProcessManager: {e}")
                logging.error(f"Traceback: {traceback.format_exc()}")
                
                await self.show_deployment_error(update, context, message_to_edit, 
                    f"Ошибка инициализации: {e}")
                return
            
            # Deploy bot
            logging.info(f"🔄 Calling deploy_user_bot for bot {bot_id}...")
            success = await manager.deploy_user_bot(bot_id)
            
            if success:
                logging.info(f"✅ Bot {bot_id} deployed successfully!")
                await self.show_deployment_success(update, context, bot_info, message_to_edit)
            else:
                logging.error(f"❌ Bot {bot_id} deployment failed")
                await self.show_deployment_error(update, context, message_to_edit)
                
        except Exception as e:
            logging.error(f"❌ CRITICAL: Unexpected error in deploy_user_bot for bot {bot_id}: {e}")
            logging.error(f"Traceback: {traceback.format_exc()}")
            await self.show_deployment_error(update, context, message_to_edit, str(e))
    
    async def show_deployment_success(self, update: Update, context: ContextTypes.DEFAULT_TYPE, 
                                    bot_info: dict, message_to_edit):
        """Show successful deployment message"""
        bot_username = bot_info['username']
        
        message = f"""
🎉 <b>Готово! Твой @{bot_username} запущен!</b>

📋 <b>Что делать дальше:</b>

<b>1️⃣ Добавь бота в канал как администратора:</b>
• Зайди в настройки канала
• Администраторы → Добавить администратора  
• Найди @{bot_username} и добавь
• Дай права: "Удаление сообщений" и "Приглашение пользователей"

<b>2️⃣ Перейди к своему боту:</b> @{bot_username}

<b>3️⃣ Напиши ему /start</b> - откроется админ-панель!

🎁 <b>MVP версия работает бесплатно</b>
📊 Полная статистика и аналитика
⚡ Мгновенные рассылки и автоматизация

<b>Нужна помощь?</b> Обращайся в поддержку!
"""
        
        keyboard = [
            [InlineKeyboardButton(f"🤖 Перейти к @{bot_username}", 
                                url=f"https://t.me/{bot_username}")],
            [InlineKeyboardButton("📖 Инструкция по настройке", 
                                callback_data="setup_guide")],
            [InlineKeyboardButton("🏠 Мои боты", callback_data="back_to_dashboard")],
            [InlineKeyboardButton("💬 Поддержка", callback_data="contact_support")]
        ]
        
        await message_to_edit.edit_text(
            message,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )
        
        # Clear creation state
        context.user_data.clear()
    
    async def show_deployment_error(self, update: Update, context: ContextTypes.DEFAULT_TYPE, 
                                  message_to_edit, error_details: str = None):
        """Show deployment error message"""
        message = """
❌ <b>Ошибка при запуске бота</b>

К сожалению, произошла ошибка при создании твоего бота.

<b>Что делать:</b>
• Попробуй еще раз через несколько минут
• Обратись в поддержку для решения проблемы
• Проверь, что токен был скопирован правильно

Мы уже получили уведомление об ошибке и работаем над исправлением.
"""
        
        if error_details:
            message += f"\n\n<i>Техническая информация:</i>\n<code>{error_details[:200]}</code>"
        
        keyboard = [
            [InlineKeyboardButton("🔄 Попробовать еще раз", callback_data="create_bot")],
            [InlineKeyboardButton("💬 Поддержка", callback_data="contact_support")],
            [InlineKeyboardButton("🏠 В главное меню", callback_data="back_to_dashboard")]
        ]
        
        await message_to_edit.edit_text(
            message,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )
    
    async def show_examples(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show bot examples"""
        message = """
📺 <b>Примеры использования Bot Factory</b>

<b>🎯 Для бизнеса:</b>
• Автоматические уведомления о новых товарах
• Рассылка промо-акций и скидок  
• Сбор заявок через закрытый канал
• Статистика эффективности рекламы

<b>📚 Для образования:</b>
• Рассылка учебных материалов
• Уведомления о занятиях и экзаменах
• Автоматический прием в учебные группы
• Статистика активности студентов

<b>🎮 Для сообществ:</b>
• Приветствие новых участников
• Автоматическая модерация заявок
• Регулярные дайджесты и новости
• Интерактивные опросы и голосования

<b>📈 Возможности ботов:</b>
✅ Автоматические рассылки по расписанию
✅ UTM-трекинг ссылок и переходов
✅ Статистика активности участников  
✅ Персонализированные сообщения
✅ Интеграция с внешними сервисами
"""
        
        keyboard = [
            [InlineKeyboardButton("🚀 Создать своего бота", callback_data="create_bot")],
            [InlineKeyboardButton("🔙 Назад", callback_data="back_to_dashboard")]
        ]
        
        await update.callback_query.edit_message_text(
            message,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )
    
    async def contact_support(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show support information"""  
        message = """
💬 <b>Поддержка Bot Factory</b>

<b>Нужна помощь?</b> Мы всегда готовы помочь!

📧 <b>Email:</b> support@botfactory.ru
💬 <b>Telegram:</b> @BotFactorySupport  
📱 <b>Чат поддержки:</b> @BotFactoryChat

<b>Частые вопросы:</b>

❓ <b>Как добавить бота в канал?</b>
Перейди в настройки канала → Администраторы → Добавить администратора → Найди своего бота

❓ <b>Бот не отвечает на команды</b>
Убедись, что бот добавлен как администратор канала с правами на удаление сообщений

❓ <b>Как настроить автоматические рассылки?</b>
В админ-панели бота выбери "Управление рассылками" → "Создать рассылку"

❓ <b>Где посмотреть статистику?</b>
В админ-панели бота раздел "Статистика и аналитика"

<b>🕐 Время ответа:</b> обычно в течение 2-4 часов
"""
        
        keyboard = [
            [InlineKeyboardButton("📧 Написать в поддержку", url="https://t.me/BotFactorySupport")],
            [InlineKeyboardButton("🔙 Назад", callback_data="back_to_dashboard")]
        ]
        
        await update.callback_query.edit_message_text(
            message,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )
    
    async def manage_bot(self, update: Update, context: ContextTypes.DEFAULT_TYPE, bot_id: int):
        """Show bot management options"""
        try:
            bot = self.db.get_bot_by_id(bot_id)
            if not bot:
                await update.callback_query.answer("Бот не найден")
                return
            
            status_text = {
                'active': '✅ Активен',
                'creating': '🔄 Создается',
                'stopped': '⏸️ Остановлен',
                'error': '❌ Ошибка'
            }.get(bot['status'], '❓ Неизвестно')
            
            bot_username = bot.get('bot_username', 'unknown')
            created_at = bot.get('created_at', 'Неизвестно')[:16]
            last_ping = bot.get('last_ping')
            last_ping_text = last_ping[:16] if last_ping else 'Никогда'
            error_message = bot.get('error_message', '')
            
            message = f"""
⚙️ <b>Управление ботом @{bot_username}</b>

<b>Статус:</b> {status_text}
<b>Создан:</b> {created_at}
<b>Последняя активность:</b> {last_ping_text}
"""
            
            if error_message:
                message += f"\n<b>Ошибка:</b> <code>{error_message}</code>\n"
            
            message += "\n<b>Доступные действия:</b>"
            
            keyboard = [
                [InlineKeyboardButton(f"🤖 Перейти к @{bot_username}", 
                                    url=f"https://t.me/{bot_username}")],
                [InlineKeyboardButton("📊 Статистика", callback_data=f"stats_{bot_id}")],
                [InlineKeyboardButton("🔄 Перезапустить", callback_data=f"restart_{bot_id}")],
                [InlineKeyboardButton("🔙 Назад", callback_data="back_to_dashboard")]
            ]
            
            await update.callback_query.edit_message_text(
                message,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='HTML'
            )
        except Exception as e:
            logging.error(f"Error in manage_bot: {e}")
            await update.callback_query.answer("❌ Ошибка при загрузке информации о боте")
    
    async def restart_bot(self, update: Update, context: ContextTypes.DEFAULT_TYPE, bot_id: int):
        """Restart a user bot"""
        try:
            bot = self.db.get_bot_by_id(bot_id)
            if not bot:
                await update.callback_query.answer("Бот не найден")
                return
            
            # Show processing message
            processing_msg = await update.callback_query.edit_message_text(
                f"🔄 Перезапускаю бота @{bot['bot_username']}...\n\n"
                "Это может занять несколько секунд."
            )
            
            try:
                # Import process manager
                from bot_manager.process_manager import BotProcessManager
                manager = BotProcessManager()
                
                # Restart the bot
                success = await manager.restart_bot(bot_id)
                
                if success:
                    await processing_msg.edit_text(
                        f"✅ <b>Бот @{bot['bot_username']} успешно перезапущен!</b>\n\n"
                        "Попробуй написать ему /start для проверки работы.",
                        parse_mode='HTML',
                        reply_markup=InlineKeyboardMarkup([
                            [InlineKeyboardButton(f"🤖 Перейти к @{bot['bot_username']}", 
                                                url=f"https://t.me/{bot['bot_username']}")],
                            [InlineKeyboardButton("🔙 Назад к управлению", 
                                                callback_data=f"manage_{bot_id}")]
                        ])
                    )
                else:
                    await processing_msg.edit_text(
                        f"❌ <b>Не удалось перезапустить бота @{bot['bot_username']}</b>\n\n"
                        "Попробуйте еще раз или обратитесь в поддержку.",
                        parse_mode='HTML',
                        reply_markup=InlineKeyboardMarkup([
                            [InlineKeyboardButton("🔄 Попробовать еще раз", 
                                                callback_data=f"restart_{bot_id}")],
                            [InlineKeyboardButton("🔙 Назад к управлению", 
                                                callback_data=f"manage_{bot_id}")]
                        ])
                    )
                    
            except Exception as e:
                logging.error(f"Error restarting bot {bot_id}: {e}")
                await processing_msg.edit_text(
                    f"❌ <b>Ошибка при перезапуске бота</b>\n\n"
                    f"Техническая информация: <code>{str(e)[:100]}</code>\n\n"
                    "Обратитесь в поддержку для решения проблемы.",
                    parse_mode='HTML',
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("💬 Поддержка", callback_data="contact_support")],
                        [InlineKeyboardButton("🔙 Назад к управлению", 
                                            callback_data=f"manage_{bot_id}")]
                    ])
                )
                
        except Exception as e:
            logging.error(f"Error in restart_bot: {e}")
            await update.callback_query.answer("❌ Ошибка при перезапуске бота")
    
    async def show_bot_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE, bot_id: int):
        """Show bot statistics"""
        try:
            bot = self.db.get_bot_by_id(bot_id)
            if not bot:
                await update.callback_query.answer("Бот не найден")
                return
            
            bot_username = bot.get('bot_username', 'unknown')
            bot_status = bot.get('status', 'unknown')
            created_at = bot.get('created_at', 'Неизвестно')[:16]
            last_ping = bot.get('last_ping')
            last_ping_text = last_ping[:16] if last_ping else 'Неизвестно'
            process_id = bot.get('process_id', 'Неизвестно')
            database_status = '✅ Создана' if bot.get('database_path') else '❌ Не создана'
            
            message = f"""
📊 <b>Статистика @{bot_username}</b>

<b>Основные показатели:</b>
• Статус: {bot_status}
• Создан: {created_at}
• Активность: {last_ping_text}

<b>Техническая информация:</b>
• ID бота: {bot_id}
• Process ID: {process_id}
• База данных: {database_status}

<i>В полной версии здесь будет подробная аналитика:
количество подписчиков, отправленных сообщений,
переходов по ссылкам и другие метрики.</i>
"""
            
            keyboard = [
                [InlineKeyboardButton("⚙️ Управление", callback_data=f"manage_{bot_id}")],
                [InlineKeyboardButton("🔙 Мои боты", callback_data="back_to_dashboard")]
            ]
            
            await update.callback_query.edit_message_text(
                message,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='HTML'
            )
        except Exception as e:
            logging.error(f"Error in show_bot_stats: {e}")
            await update.callback_query.answer("❌ Ошибка при загрузке статистики")
    
    def run(self):
        """Run the master bot - СИНХРОННАЯ ВЕРСИЯ"""
        try:
            logging.info("🔄 Creating Application...")
            self.application = Application.builder().token(self.bot_token).build()
            
            # Setup handlers (это теперь должно быть синхронно)
            logging.info("🔄 Setting up handlers...")
            self.setup_handlers_sync(self.application)
            
            logging.info("🚀 Starting Master Bot...")
            
            # ПРОСТОЙ СИНХРОННЫЙ ПОДХОД
            self.application.run_polling(drop_pending_updates=True)
            
        except Exception as e:
            logging.error(f"❌ Error running master bot: {e}")
            logging.error(f"Traceback: {traceback.format_exc()}")
            raise
    
    def setup_handlers_sync(self, application: Application):
        """Configure all handlers for master bot - СИНХРОННАЯ ВЕРСИЯ"""
        
        # Main handlers
        application.add_handler(CommandHandler("start", self.handle_start))
        application.add_handler(CallbackQueryHandler(self.handle_callback))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_text_input))
        
        logging.info("✅ Master bot handlers configured")
