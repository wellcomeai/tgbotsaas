#!/usr/bin/env python3
"""
Master Bot Runner - отдельный скрипт для запуска главного бота
Запускается как отдельный процесс для избежания threading проблем
"""

import os
import sys
import logging
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - MasterBot - %(name)s - %(levelname)s - %(message)s'
)

def main():
    """Run the master bot - СИНХРОННАЯ ВЕРСИЯ"""
    try:
        # Check for bot token
        master_bot_token = os.environ.get('MASTER_BOT_TOKEN')
        if not master_bot_token:
            logging.error("MASTER_BOT_TOKEN environment variable is required")
            sys.exit(1)
        
        # Check data directory
        data_dir = Path(os.environ.get('RENDER_DISK_PATH', '/data'))
        if not data_dir.exists():
            logging.error(f"Data directory does not exist: {data_dir}")
            sys.exit(1)
        
        logging.info("Starting Master Bot process...")
        logging.info(f"Token configured: {bool(master_bot_token)}")
        logging.info(f"Data directory: {data_dir}")
        
        # Import and run master bot
        try:
            from master_bot.main import MasterBot
        except ImportError as e:
            logging.error(f"Failed to import MasterBot: {e}")
            logging.error("Make sure all dependencies are installed")
            sys.exit(1)
        
        master_bot = MasterBot(master_bot_token)
        
        # Run the bot (синхронно)
        master_bot.run()
        
    except KeyboardInterrupt:
        logging.info("Master bot stopped by user")
    except Exception as e:
        logging.error(f"Fatal error in master bot: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
