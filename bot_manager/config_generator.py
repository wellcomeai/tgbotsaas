"""
Bot Configuration Generator - создание конфигурационных файлов для пользовательских ботов
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

class BotConfigGenerator:
    def __init__(self):
        data_dir = os.environ.get('RENDER_DISK_PATH', '/data')
        self.configs_dir = Path(data_dir) / "bot_configs"
        self.configs_dir.mkdir(parents=True, exist_ok=True)
    
    async def generate_config(self, bot_id: int) -> Optional[Path]:
        """
        Generate configuration file for user bot
        
        Args:
            bot_id: Bot ID from master database
            
        Returns:
            Path to generated config file or None if failed
        """
        try:
            # Get bot info from database
            from master_bot.database import MasterDatabase
            db = MasterDatabase()
            bot_info = db.get_bot_by_id(bot_id)
            
            if not bot_info:
                logging.error(f"Bot {bot_id} not found in database")
                return None
            
            # Generate config
            config = {
                # Bot identification
                "BOT_ID": bot_id,
                "BOT_TOKEN": bot_info['bot_token'],
                "BOT_USERNAME": bot_info['bot_username'],
                "BOT_DISPLAY_NAME": bot_info['bot_display_name'],
                
                # Admin settings
                "ADMIN_CHAT_ID": bot_info['owner_telegram_id'],
                "OWNER_ID": bot_info['owner_id'],
                
                # Database settings
                "DATABASE_PATH": str(Path(os.environ.get('RENDER_DISK_PATH', '/data')) / 
                                  "user_databases" / f"bot_{bot_id}.db"),
                
                # Channel settings (will be configured later by user)
                "CHANNEL_ID": bot_info.get('channel_id'),
                "CHANNEL_USERNAME": None,  # To be set by user
                
                # Bot behavior settings
                "AUTO_APPROVE_REQUESTS": True,
                "WELCOME_MESSAGE_ENABLED": True,
                "FAREWELL_MESSAGE_ENABLED": True,
                "UTM_TRACKING_ENABLED": True,
                
                # Default messages
                "WELCOME_MESSAGE": "👋 Добро пожаловать в наш канал! Мы рады видеть тебя здесь.",
                "FAREWELL_MESSAGE": "👋 До свидания! Будем скучать.",
                "AUTO_APPROVE_MESSAGE": "✅ Твоя заявка одобрена! Добро пожаловать в канал.",
                
                # System settings
                "LOG_LEVEL": "INFO",
                "HEALTH_CHECK_INTERVAL": 300,  # 5 minutes
                "MAX_MESSAGE_LENGTH": 4000,
                "RATE_LIMIT_ENABLED": True,
                
                # Statistics settings
                "STATS_ENABLED": True,
                "ANALYTICS_RETENTION_DAYS": 90,
                
                # Broadcasting settings
                "BROADCAST_DELAY": 1,  # seconds between messages
                "MAX_BROADCAST_SIZE": 1000,  # max recipients per broadcast
                
                # Configuration metadata
                "_generated_at": datetime.now().isoformat(),
                "_version": "1.0.0",
                "_master_bot_version": "mvp",
            }
            
            # Save configuration file
            config_path = self.configs_dir / f"bot_{bot_id}_config.json"
            
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            
            logging.info(f"Generated config for bot {bot_id}: {config_path}")
            return config_path
            
        except Exception as e:
            logging.error(f"Error generating config for bot {bot_id}: {e}")
            return None
    
    def load_config(self, bot_id: int) -> Optional[dict]:
        """Load configuration for a bot"""
        try:
            config_path = self.configs_dir / f"bot_{bot_id}_config.json"
            
            if not config_path.exists():
                logging.error(f"Config file not found for bot {bot_id}")
                return None
            
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            return config
            
        except Exception as e:
            logging.error(f"Error loading config for bot {bot_id}: {e}")
            return None
    
    def update_config(self, bot_id: int, updates: dict) -> bool:
        """Update specific configuration values"""
        try:
            config = self.load_config(bot_id)
            if not config:
                return False
            
            # Update configuration
            config.update(updates)
            config['_updated_at'] = datetime.now().isoformat()
            
            # Save updated config
            config_path = self.configs_dir / f"bot_{bot_id}_config.json"
            
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            
            logging.info(f"Updated config for bot {bot_id}")
            return True
            
        except Exception as e:
            logging.error(f"Error updating config for bot {bot_id}: {e}")
            return False
    
    def delete_config(self, bot_id: int) -> bool:
        """Delete configuration file"""
        try:
            config_path = self.configs_dir / f"bot_{bot_id}_config.json"
            
            if config_path.exists():
                config_path.unlink()
                logging.info(f"Deleted config for bot {bot_id}")
            
            return True
            
        except Exception as e:
            logging.error(f"Error deleting config for bot {bot_id}: {e}")
            return False
    
    def validate_config(self, config: dict) -> tuple[bool, str]:
        """Validate configuration structure"""
        required_fields = [
            'BOT_ID', 'BOT_TOKEN', 'BOT_USERNAME', 
            'ADMIN_CHAT_ID', 'DATABASE_PATH'
        ]
        
        for field in required_fields:
            if field not in config:
                return False, f"Missing required field: {field}"
        
        # Validate bot token format
        if not config['BOT_TOKEN'] or ':' not in config['BOT_TOKEN']:
            return False, "Invalid bot token format"
        
        # Validate admin chat ID
        try:
            int(config['ADMIN_CHAT_ID'])
        except (ValueError, TypeError):
            return False, "Invalid admin chat ID"
        
        return True, "Configuration is valid"
