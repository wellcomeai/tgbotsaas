"""
Master Database - управление данными SaaS платформы
Хранит пользователей, их ботов и системные логи
"""

import sqlite3
import os
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from contextlib import contextmanager

class MasterDatabase:
    def __init__(self, db_path: str = None):
        if db_path is None:
            data_dir = os.environ.get('RENDER_DISK_PATH', '/data')
            db_path = os.path.join(data_dir, 'master_database.db')
        
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Initialize database with required tables"""
        with self.get_connection() as conn:
            # Enable WAL mode for better concurrency
            conn.execute('PRAGMA journal_mode=WAL')
            conn.execute('PRAGMA synchronous=NORMAL') 
            conn.execute('PRAGMA cache_size=1000')
            conn.execute('PRAGMA temp_store=memory')
            
            # SaaS users table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS saas_users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    telegram_id INTEGER UNIQUE NOT NULL,
                    username TEXT,
                    first_name TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_active BOOLEAN DEFAULT 1,
                    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # User bots management
            conn.execute('''
                CREATE TABLE IF NOT EXISTS user_bots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    owner_id INTEGER NOT NULL REFERENCES saas_users(id),
                    bot_token TEXT NOT NULL UNIQUE,
                    bot_username TEXT NOT NULL,
                    bot_display_name TEXT,
                    channel_id TEXT,
                    status TEXT DEFAULT 'creating',
                    process_id TEXT NULL,
                    config_path TEXT,
                    database_path TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_ping TIMESTAMP NULL,
                    error_message TEXT NULL
                )
            ''')
            
            # System events logging
            conn.execute('''
                CREATE TABLE IF NOT EXISTS system_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NULL REFERENCES saas_users(id),
                    bot_id INTEGER NULL REFERENCES user_bots(id),
                    event_type TEXT NOT NULL,
                    event_data TEXT NULL,
                    description TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            conn.commit()
            logging.info(f"Master database initialized: {self.db_path}")
    
    @contextmanager
    def get_connection(self):
        """Context manager for database connections with retry logic"""
        max_retries = 5
        retry_delay = 0.1
        
        for attempt in range(max_retries):
            try:
                conn = sqlite3.connect(
                    self.db_path, 
                    timeout=30.0,  # 30 second timeout
                    check_same_thread=False
                )
                conn.row_factory = sqlite3.Row  # Enable dict-like access
                
                # Set additional pragmas for better concurrency
                conn.execute('PRAGMA busy_timeout=30000')  # 30 seconds
                
                try:
                    yield conn
                    conn.commit()
                    break
                except Exception as e:
                    conn.rollback()
                    if "database is locked" in str(e).lower() and attempt < max_retries - 1:
                        logging.warning(f"Database locked, retrying {attempt + 1}/{max_retries}")
                        time.sleep(retry_delay * (2 ** attempt))  # Exponential backoff
                        continue
                    else:
                        logging.error(f"Database error: {e}")
                        raise
                finally:
                    conn.close()
                    
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e).lower() and attempt < max_retries - 1:
                    logging.warning(f"Database connection locked, retrying {attempt + 1}/{max_retries}")
                    time.sleep(retry_delay * (2 ** attempt))
                    continue
                else:
                    logging.error(f"Database connection error: {e}")
                    raise
    
    # User management methods
    def create_user(self, telegram_id: int, username: str = None, first_name: str = None) -> int:
        """Create new SaaS user"""
        try:
            with self.get_connection() as conn:
                cursor = conn.execute('''
                    INSERT INTO saas_users (telegram_id, username, first_name)
                    VALUES (?, ?, ?)
                ''', (telegram_id, username, first_name))
                
                user_id = cursor.lastrowid
                
                # Log registration event
                self.log_event(user_id, None, 'user_registered', 
                             description=f"New user registered: {first_name} (@{username})")
                
                logging.info(f"Created user {user_id} for telegram_id {telegram_id}")
                return user_id
        except Exception as e:
            logging.error(f"Error creating user {telegram_id}: {e}")
            raise
    
    def get_user_by_telegram_id(self, telegram_id: int) -> Optional[Dict]:
        """Get user by telegram ID"""
        try:
            with self.get_connection() as conn:
                cursor = conn.execute('''
                    SELECT * FROM saas_users WHERE telegram_id = ?
                ''', (telegram_id,))
                
                row = cursor.fetchone()
                return dict(row) if row else None
        except Exception as e:
            logging.error(f"Error getting user {telegram_id}: {e}")
            return None
    
    def update_user_activity(self, telegram_id: int):
        """Update last activity timestamp"""
        try:
            with self.get_connection() as conn:
                conn.execute('''
                    UPDATE saas_users 
                    SET last_activity = CURRENT_TIMESTAMP 
                    WHERE telegram_id = ?
                ''', (telegram_id,))
        except Exception as e:
            logging.error(f"Error updating user activity {telegram_id}: {e}")
    
    # Bot management methods
    def create_user_bot(self, owner_id: int, bot_token: str, 
                       bot_username: str, bot_display_name: str = None) -> int:
        """Create new user bot record"""
        try:
            with self.get_connection() as conn:
                cursor = conn.execute('''
                    INSERT INTO user_bots (owner_id, bot_token, bot_username, bot_display_name)
                    VALUES (?, ?, ?, ?)
                ''', (owner_id, bot_token, bot_username, bot_display_name))
                
                bot_id = cursor.lastrowid
                
                # Log bot creation
                self.log_event(owner_id, bot_id, 'bot_created', 
                             description=f"Bot created: @{bot_username}")
                
                logging.info(f"Created bot {bot_id} for user {owner_id}")
                return bot_id
        except Exception as e:
            logging.error(f"Error creating bot for user {owner_id}: {e}")
            raise
    
    def get_bot_by_id(self, bot_id: int) -> Optional[Dict]:
        """Get bot by ID"""
        try:
            with self.get_connection() as conn:
                cursor = conn.execute('''
                    SELECT b.*, u.telegram_id as owner_telegram_id
                    FROM user_bots b
                    JOIN saas_users u ON b.owner_id = u.id
                    WHERE b.id = ?
                ''', (bot_id,))
                
                row = cursor.fetchone()
                return dict(row) if row else None
        except Exception as e:
            logging.error(f"Error getting bot {bot_id}: {e}")
            return None
    
    def get_user_bots(self, user_id: int) -> List[Dict]:
        """Get all bots for a user"""
        try:
            with self.get_connection() as conn:
                cursor = conn.execute('''
                    SELECT * FROM user_bots WHERE owner_id = ? ORDER BY created_at DESC
                ''', (user_id,))
                
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logging.error(f"Error getting bots for user {user_id}: {e}")
            return []
    
    def bot_exists_by_token(self, bot_token: str) -> bool:
        """Check if bot with token already exists"""
        try:
            with self.get_connection() as conn:
                cursor = conn.execute('''
                    SELECT 1 FROM user_bots WHERE bot_token = ?
                ''', (bot_token,))
                
                return cursor.fetchone() is not None
        except Exception as e:
            logging.error(f"Error checking bot token existence: {e}")
            return False
    
    def update_bot_status(self, bot_id: int, status: str, error_message: str = None):
        """Update bot status"""
        try:
            with self.get_connection() as conn:
                conn.execute('''
                    UPDATE user_bots 
                    SET status = ?, error_message = ?, last_ping = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (status, error_message, bot_id))
                
                logging.info(f"Updated bot {bot_id} status to {status}")
        except Exception as e:
            logging.error(f"Error updating bot {bot_id} status: {e}")
    
    def update_bot_config_path(self, bot_id: int, config_path: str, database_path: str):
        """Update bot configuration paths"""
        try:
            with self.get_connection() as conn:
                conn.execute('''
                    UPDATE user_bots 
                    SET config_path = ?, database_path = ?
                    WHERE id = ?
                ''', (config_path, database_path, bot_id))
        except Exception as e:
            logging.error(f"Error updating bot {bot_id} config paths: {e}")
    
    def update_bot_process_id(self, bot_id: int, process_id: str):
        """Update bot process ID"""
        try:
            with self.get_connection() as conn:
                conn.execute('''
                    UPDATE user_bots 
                    SET process_id = ?, last_ping = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (process_id, bot_id))
        except Exception as e:
            logging.error(f"Error updating bot {bot_id} process ID: {e}")
    
    def get_active_bots(self) -> List[Dict]:
        """Get all active bots"""
        try:
            with self.get_connection() as conn:
                cursor = conn.execute('''
                    SELECT b.*, u.telegram_id as owner_telegram_id
                    FROM user_bots b
                    JOIN saas_users u ON b.owner_id = u.id
                    WHERE b.status IN ('active', 'creating')
                    ORDER BY b.created_at DESC
                ''')
                
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logging.error(f"Error getting active bots: {e}")
            return []
    
    # Logging methods
    def log_event(self, user_id: int = None, bot_id: int = None, 
                  event_type: str = None, event_data: str = None, 
                  description: str = None):
        """Log system event"""
        try:
            with self.get_connection() as conn:
                conn.execute('''
                    INSERT INTO system_logs (user_id, bot_id, event_type, event_data, description)
                    VALUES (?, ?, ?, ?, ?)
                ''', (user_id, bot_id, event_type, event_data, description))
        except Exception as e:
            logging.error(f"Error logging event: {e}")
    
    # Statistics methods
    def get_system_stats(self) -> Dict[str, Any]:
        """Get system statistics"""
        try:
            with self.get_connection() as conn:
                stats = {}
                
                # Total users
                cursor = conn.execute('SELECT COUNT(*) FROM saas_users')
                stats['total_users'] = cursor.fetchone()[0]
                
                # Total bots
                cursor = conn.execute('SELECT COUNT(*) FROM user_bots')
                stats['total_bots'] = cursor.fetchone()[0]
                
                # Active bots
                cursor = conn.execute("SELECT COUNT(*) FROM user_bots WHERE status = 'active'")
                stats['active_bots'] = cursor.fetchone()[0]
                
                # Recent registrations (last 24h)
                cursor = conn.execute('''
                    SELECT COUNT(*) FROM saas_users 
                    WHERE created_at > datetime('now', '-1 day')
                ''')
                stats['recent_registrations'] = cursor.fetchone()[0]
                
                stats['timestamp'] = datetime.now().isoformat()
                return stats
        except Exception as e:
            logging.error(f"Error getting system stats: {e}")
            return {
                'total_users': 0,
                'total_bots': 0,
                'active_bots': 0,
                'recent_registrations': 0,
                'timestamp': datetime.now().isoformat(),
                'error': str(e)
            }
    
    def get_recent_users(self, limit: int = 10) -> List[Dict]:
        """Get recent users"""
        try:
            with self.get_connection() as conn:
                cursor = conn.execute('''
                    SELECT * FROM saas_users 
                    ORDER BY created_at DESC 
                    LIMIT ?
                ''', (limit,))
                
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logging.error(f"Error getting recent users: {e}")
            return []
