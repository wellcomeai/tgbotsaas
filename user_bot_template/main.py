"""
User Bot Template - шаблон пользовательского бота
Запускается как отдельный процесс для каждого созданного бота
"""

import argparse
import asyncio
import json
import logging
import os
import signal
import sys
import traceback
from pathlib import Path
from telegram import Update
from telegram.ext import Application, CommandHandler, ChatJoinRequestHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

# Add project root to Python path - CRITICAL FOR RENDER
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# EARLY LOGGING SETUP for debugging startup issues
def setup_early_logging():
    """Setup basic logging before we know the bot_id"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - UserBot - %(name)s - %(levelname)s - %(message)s',
        force=True
    )

setup_early_logging()
logging.info("🔄 UserBot main.py started, beginning imports...")

# Safe imports with detailed error handling
def safe_import(module_name, description):
    """Safely import a module with detailed logging"""
    try:
        logging.info(f"🔄 Importing {description}...")
        if module_name == "user_bot_template.database":
            from user_bot_template.database import Database
            logging.info(f"✅ Successfully imported {description}")
            return Database
        elif module_name == "user_bot_template.admin_panel":
            from user_bot_template.admin_panel import AdminPanel
            logging.info(f"✅ Successfully imported {description}")
            return AdminPanel
        elif module_name == "user_bot_template.handlers.admin_commands":
            from user_bot_template.handlers.admin_commands import AdminCommandsHandler
            logging.info(f"✅ Successfully imported {description}")
            return AdminCommandsHandler
        elif module_name == "user_bot_template.handlers.channel_events":
            from user_bot_template.handlers.channel_events import ChannelEventsHandler
            logging.info(f"✅ Successfully imported {description}")
            return ChannelEventsHandler
        elif module_name == "user_bot_template.handlers.messaging":
            from user_bot_template.handlers.messaging import MessagingHandler
            logging.info(f"✅ Successfully imported {description}")
            return MessagingHandler
    except ImportError as e:
        logging.error(f"❌ Failed to import {description}: {e}")
        logging.error(f"Traceback: {traceback.format_exc()}")
        logging.error(f"Python path: {sys.path}")
        logging.error(f"Current working directory: {os.getcwd()}")
        logging.error(f"Project root: {project_root}")
        sys.exit(1)
    except Exception as e:
        logging.error(f"❌ Unexpected error importing {description}: {e}")
        logging.error(f"Traceback: {traceback.format_exc()}")
        sys.exit(1)

# Import all required modules
Database = safe_import("user_bot_template.database", "Database")
AdminPanel = safe_import("user_bot_template.admin_panel", "AdminPanel")
AdminCommandsHandler = safe_import("user_bot_template.handlers.admin_commands", "AdminCommandsHandler")
ChannelEventsHandler = safe_import("user_bot_template.handlers.channel_events", "ChannelEventsHandler")
MessagingHandler = safe_import("user_bot_template.handlers.messaging", "MessagingHandler")

logging.info("✅ All imports completed successfully")

def setup_bot_logging(bot_id):
    """Setup logging for specific bot with file output"""
    try:
        # Configure root logger for this bot
        logging.basicConfig(
            level=logging.INFO,
            format=f'%(asctime)s - UserBot{bot_id} - %(name)s - %(levelname)s - %(message)s',
            force=True
        )
        
        # Try to create file handler if possible
        try:
            log_dir = Path(os.environ.get('RENDER_DISK_PATH', '/tmp')) / 'logs'
            log_dir.mkdir(exist_ok=True, parents=True)
            
            file_handler = logging.FileHandler(log_dir / f"user_bot_{bot_id}_internal.log")
            file_handler.setFormatter(logging.Formatter(
                f'%(asctime)s - UserBot{bot_id} - %(name)s - %(levelname)s - %(message)s'
            ))
            
            logging.getLogger().addHandler(file_handler)
            logging.info(f"✅ File logging enabled: {log_dir / f'user_bot_{bot_id}_internal.log'}")
            
        except Exception as e:
            logging.warning(f"⚠️ Could not setup file logging: {e}")
            
    except Exception as e:
        print(f"❌ Error setting up logging: {e}", file=sys.stderr)

class UserBot:
    def __init__(self, config_path: str, bot_id: int):
        self.bot_id = bot_id
        self.config_path = config_path
        self.config = None
        self.db = None
        self.admin_panel = None
        self.admin_handler = None
        self.channel_handler = None
        self.messaging_handler = None
        self.application = None
        self.is_running = False
        
        # Setup logging first
        setup_bot_logging(bot_id)
        
        logging.info(f"🔄 Initializing UserBot {bot_id}")
        logging.info(f"📂 Config path: {config_path}")
        logging.info(f"📂 Current working directory: {os.getcwd()}")
        logging.info(f"📂 Project root: {project_root}")
        
        # Load and validate configuration
        self._load_and_validate_config()
        
        if not self.config:
            raise ValueError(f"Failed to load config from {config_path}")
        
        # Initialize all components step by step
        self._initialize_components()
        
        logging.info(f"✅ UserBot {bot_id} initialized successfully")
    
    def _load_and_validate_config(self):
        """Load and validate bot configuration with detailed error handling"""
        try:
            logging.info(f"🔄 Loading config from {self.config_path}")
            
            config_path_obj = Path(self.config_path)
            
            # Check if file exists
            if not config_path_obj.exists():
                logging.error(f"❌ Config file does not exist: {self.config_path}")
                logging.error(f"📂 Parent directory: {config_path_obj.parent}")
                logging.error(f"📂 Parent exists: {config_path_obj.parent.exists()}")
                if config_path_obj.parent.exists():
                    logging.error(f"📂 Files in parent: {list(config_path_obj.parent.glob('*'))}")
                return
            
            # Check file permissions
            if not os.access(config_path_obj, os.R_OK):
                logging.error(f"❌ Config file is not readable: {self.config_path}")
                return
            
            # Get file size
            file_size = config_path_obj.stat().st_size
            logging.info(f"📄 Config file size: {file_size} bytes")
            
            if file_size == 0:
                logging.error(f"❌ Config file is empty: {self.config_path}")
                return
            
            # Read file content
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    config_content = f.read()
                logging.info(f"✅ Config file read successfully, content length: {len(config_content)}")
                logging.info(f"📄 Config preview: {config_content[:200]}...")
            except Exception as e:
                logging.error(f"❌ Failed to read config file: {e}")
                return
            
            # Parse JSON
            try:
                self.config = json.loads(config_content)
                logging.info(f"✅ Config JSON parsed successfully")
                logging.info(f"📋 Config keys: {list(self.config.keys())}")
                
                # Validate required fields
                required_fields = ['BOT_ID', 'BOT_TOKEN', 'BOT_USERNAME', 'ADMIN_CHAT_ID', 'DATABASE_PATH']
                missing_fields = [field for field in required_fields if field not in self.config]
                
                if missing_fields:
                    logging.error(f"❌ Missing required config fields: {missing_fields}")
                    return
                
                # Validate BOT_ID matches
                if self.config['BOT_ID'] != self.bot_id:
                    logging.error(f"❌ Config BOT_ID ({self.config['BOT_ID']}) does not match expected ({self.bot_id})")
                    return
                
                # Validate bot token format
                if ':' not in self.config['BOT_TOKEN']:
                    logging.error(f"❌ Invalid bot token format")
                    return
                
                logging.info(f"✅ Config validation passed")
                logging.info(f"🤖 Bot: @{self.config['BOT_USERNAME']} (ID: {self.config['BOT_ID']})")
                logging.info(f"👤 Admin: {self.config['ADMIN_CHAT_ID']}")
                
            except json.JSONDecodeError as e:
                logging.error(f"❌ Invalid JSON in config file: {e}")
                logging.error(f"📄 JSON error line: {e.lineno}, column: {e.colno}")
                return
                
        except Exception as e:
            logging.error(f"❌ Unexpected error loading config: {e}")
            logging.error(f"Traceback: {traceback.format_exc()}")
    
    def _initialize_components(self):
        """Initialize all bot components with error handling"""
        try:
            logging.info(f"🔄 Initializing bot components...")
            
            # Initialize database
            logging.info("🔄 Initializing Database...")
            database_path = self.config['DATABASE_PATH']
            logging.info(f"📂 Database path: {database_path}")
            
            # Check if database directory exists
            db_path_obj = Path(database_path)
            db_dir = db_path_obj.parent
            if not db_dir.exists():
                logging.error(f"❌ Database directory does not exist: {db_dir}")
                raise ValueError(f"Database directory does not exist: {db_dir}")
            
            self.db = Database(database_path)
            logging.info("✅ Database initialized")
            
            # Initialize admin panel
            logging.info("🔄 Initializing AdminPanel...")
            self.admin_panel = AdminPanel(self.db, self.config)
            logging.info("✅ AdminPanel initialized")
            
            # Initialize handlers
            logging.info("🔄 Initializing handlers...")
            
            self.admin_handler = AdminCommandsHandler(self.db, self.config, self.admin_panel)
            logging.info("✅ AdminCommandsHandler initialized")
            
            self.channel_handler = ChannelEventsHandler(self.db, self.config)
            logging.info("✅ ChannelEventsHandler initialized")
            
            self.messaging_handler = MessagingHandler(self.db, self.config)
            logging.info("✅ MessagingHandler initialized")
            
            logging.info("✅ All components initialized successfully")
            
        except Exception as e:
            logging.error(f"❌ Error initializing components: {e}")
            logging.error(f"Traceback: {traceback.format_exc()}")
            raise
    
    async def setup_handlers(self):
        """Setup all bot handlers"""
        if not self.application:
            logging.error("❌ Application not initialized")
            return
        
        try:
            logging.info("🔄 Setting up handlers...")
            
            # Admin commands (only for bot owner)
            self.application.add_handler(
                CommandHandler("start", self.admin_handler.handle_start)
            )
            self.application.add_handler(
                CommandHandler("admin", self.admin_handler.handle_admin)
            )
            self.application.add_handler(
                CommandHandler("stats", self.admin_handler.handle_stats)
            )
            self.application.add_handler(
                CommandHandler("broadcast", self.admin_handler.handle_broadcast)
            )
            
            # Channel events
            self.application.add_handler(
                ChatJoinRequestHandler(self.channel_handler.handle_join_request)
            )
            
            # Message handlers
            self.application.add_handler(
                MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message)
            )
            
            # Callback query handler
            self.application.add_handler(
                CallbackQueryHandler(self.handle_callback_query)
            )
            
            logging.info(f"✅ Bot {self.bot_id} handlers setup complete")
            
        except Exception as e:
            logging.error(f"❌ Error setting up handlers: {e}")
            logging.error(f"Traceback: {traceback.format_exc()}")
            raise
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle text messages"""
        try:
            # Route to appropriate handler based on chat type
            if update.effective_chat.type == 'private':
                # Private message - route to admin handler if from owner
                if update.effective_user.id == self.config['ADMIN_CHAT_ID']:
                    await self.admin_handler.handle_private_message(update, context)
                else:
                    # Non-admin user in private chat
                    await update.message.reply_text(
                        "🤖 Этот бот предназначен для управления каналом.\n\n"
                        "Если вы хотите создать своего бота, обратитесь к @BotFactoryMasterBot"
                    )
            else:
                # Group/channel message
                await self.messaging_handler.handle_channel_message(update, context)
        except Exception as e:
            logging.error(f"❌ Error handling message: {e}")
    
    async def handle_callback_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle callback queries"""
        try:
            query = update.callback_query
            
            # Only admin can use callback queries
            if query.from_user.id != self.config['ADMIN_CHAT_ID']:
                await query.answer("❌ У вас нет прав для этого действия")
                return
            
            await self.admin_handler.handle_callback_query(update, context)
        except Exception as e:
            logging.error(f"❌ Error handling callback query: {e}")
    
    async def start_bot(self):
        """Start the bot with comprehensive error handling"""
        try:
            bot_token = self.config['BOT_TOKEN']
            logging.info(f"🔄 Creating application for bot {self.bot_id}")
            logging.info(f"🤖 Bot token: {bot_token[:20]}...{bot_token[-10:]}")
            
            # Create application
            self.application = Application.builder().token(bot_token).build()
            logging.info("✅ Application created")
            
            # Setup handlers
            await self.setup_handlers()
            logging.info("✅ Handlers setup complete")
            
            logging.info(f"🚀 Starting bot {self.bot_id} (@{self.config.get('BOT_USERNAME', 'unknown')})")
            
            # Update bot status in master database
            self._update_master_status('active')
            
            # Initialize and start the application
            logging.info("🔄 Initializing application...")
            await self.application.initialize()
            logging.info("✅ Application initialized")
            
            logging.info("🔄 Starting application...")
            await self.application.start()
            logging.info("✅ Application started")
            
            # Start polling
            self.is_running = True
            logging.info("🔄 Starting polling...")
            await self.application.updater.start_polling(drop_pending_updates=True)
            logging.info("✅ Polling started successfully")
            
            # Keep the bot running
            logging.info("🔄 Bot is now running, waiting for updates...")
            
            # Wait indefinitely (compatible with all telegram-bot versions)
            try:
                # Try modern approach first
                if hasattr(self.application, 'idle'):
                    await self.application.idle()
                else:
                    # Fallback for older versions
                    import asyncio
                    while self.is_running:
                        await asyncio.sleep(1)
            except Exception as e:
                logging.error(f"❌ Error in main loop: {e}")
                # Fallback: simple infinite loop
                while self.is_running:
                    await asyncio.sleep(1)
            
        except Exception as e:
            logging.error(f"❌ Error starting bot {self.bot_id}: {e}")
            logging.error(f"Traceback: {traceback.format_exc()}")
            self._update_master_status('error', str(e))
            raise
        finally:
            # Cleanup
            self.is_running = False
            if self.application:
                try:
                    logging.info("🔄 Stopping application...")
                    await self.application.stop()
                    await self.application.shutdown()
                    logging.info("✅ Application stopped")
                except Exception as e:
                    logging.error(f"❌ Error during cleanup: {e}")
    
    def _update_master_status(self, status: str, error_message: str = None):
        """Update bot status in master database"""
        try:
            # Import here to avoid circular dependencies
            sys.path.insert(0, str(project_root))
            from master_bot.database import MasterDatabase
            
            master_db = MasterDatabase()
            master_db.update_bot_status(self.bot_id, status, error_message)
            logging.info(f"✅ Updated master status to: {status}")
            
        except Exception as e:
            logging.error(f"❌ Failed to update master status: {e}")
    
    async def health_check(self):
        """Periodic health check"""
        while self.is_running:
            try:
                # Update last ping in master database
                self._update_master_status('active')
                
                # Wait for next check
                await asyncio.sleep(self.config.get('HEALTH_CHECK_INTERVAL', 300))
                
            except Exception as e:
                logging.error(f"❌ Health check error: {e}")
                await asyncio.sleep(60)  # Wait 1 minute before retry

def parse_arguments():
    """Parse command line arguments with validation"""
    try:
        logging.info("🔄 Parsing command line arguments...")
        
        parser = argparse.ArgumentParser(description='User Bot Template')
        parser.add_argument('--config', required=True, help='Path to bot configuration file')
        parser.add_argument('--bot-id', required=True, type=int, help='Bot ID')
        parser.add_argument('--help-test', action='store_true', help='Test help functionality')
        
        args = parser.parse_args()
        
        logging.info(f"✅ Arguments parsed successfully:")
        logging.info(f"  - config: {args.config}")
        logging.info(f"  - bot-id: {args.bot_id}")
        logging.info(f"  - help-test: {args.help_test}")
        
        return args
        
    except SystemExit as e:
        # This happens when --help is used or arguments are invalid
        logging.info(f"🔄 Argument parsing resulted in SystemExit: {e.code}")
        sys.exit(e.code)
    except Exception as e:
        logging.error(f"❌ Error parsing arguments: {e}")
        logging.error(f"Traceback: {traceback.format_exc()}")
        sys.exit(1)

def validate_environment():
    """Validate runtime environment"""
    try:
        logging.info("🔄 Validating environment...")
        
        # Check Python version
        logging.info(f"🐍 Python version: {sys.version}")
        logging.info(f"🐍 Python executable: {sys.executable}")
        
        # Check current working directory
        logging.info(f"📂 Current working directory: {os.getcwd()}")
        logging.info(f"📂 Project root: {project_root}")
        
        # Check PYTHONPATH
        logging.info(f"📂 PYTHONPATH: {os.environ.get('PYTHONPATH', 'Not set')}")
        logging.info(f"📂 sys.path (first 5): {sys.path[:5]}")
        
        # Check data directory
        data_dir = os.environ.get('RENDER_DISK_PATH', '/data')
        logging.info(f"📂 Data directory: {data_dir}")
        logging.info(f"📂 Data directory exists: {Path(data_dir).exists()}")
        
        logging.info("✅ Environment validation complete")
        
    except Exception as e:
        logging.error(f"❌ Error validating environment: {e}")
        logging.error(f"Traceback: {traceback.format_exc()}")

def main():
    """Main entry point for user bot with comprehensive error handling"""
    try:
        logging.info(f"🚀 Starting UserBot main function")
        logging.info(f"📋 Command line: {' '.join(sys.argv)}")
        
        # Validate environment
        validate_environment()
        
        # Parse arguments
        args = parse_arguments()
        
        # Handle help test
        if args.help_test:
            logging.info("✅ Help test successful")
            print("✅ User bot help test successful")
            return
        
        # Validate config file exists
        config_path = Path(args.config)
        if not config_path.exists():
            error_msg = f"Config file not found: {args.config}"
            logging.error(f"❌ {error_msg}")
            print(f"Error: {error_msg}", file=sys.stderr)
            sys.exit(1)
        
        logging.info(f"✅ Config file exists: {config_path}")
        
        # Create bot instance
        logging.info(f"🔄 Creating UserBot instance...")
        bot = UserBot(str(config_path), args.bot_id)
        logging.info(f"✅ UserBot instance created")
        
        # Setup signal handlers for graceful shutdown
        def signal_handler(signum, frame):
            logging.info(f"📡 Received signal {signum}, shutting down...")
            bot.is_running = False
            if bot.application:
                # Create task to stop application
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(bot.application.stop())
                else:
                    asyncio.run(bot.application.stop())
        
        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)
        
        # Run bot
        logging.info(f"🚀 Starting UserBot {args.bot_id} main loop...")
        asyncio.run(bot.start_bot())
        
    except KeyboardInterrupt:
        logging.info("🛑 Bot stopped by user (KeyboardInterrupt)")
    except SystemExit as e:
        logging.info(f"🛑 Bot stopped with SystemExit: {e.code}")
        sys.exit(e.code)
    except Exception as e:
        logging.error(f"❌ Fatal error in main: {e}")
        logging.error(f"Traceback: {traceback.format_exc()}")
        print(f"Fatal error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()
