"""
User Bot Database - изолированная база данных для каждого пользовательского бота
"""

import sqlite3
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from contextlib import contextmanager

class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.init_database()
        logging.info(f"User bot database initialized: {db_path}")
    
    def init_database(self):
        """Initialize database with required tables"""
        with self.get_connection() as conn:
            # Users table - channel subscribers
            conn.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_active INTEGER DEFAULT 1,
                    bot_started INTEGER DEFAULT 0,
                    utm_source TEXT,
                    utm_campaign TEXT,
                    utm_medium TEXT,
                    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Messages table - sent messages tracking
            conn.execute('''
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    message_type TEXT NOT NULL,
                    content TEXT,
                    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    status TEXT DEFAULT 'sent',
                    utm_source TEXT,
                    utm_campaign TEXT,
                    utm_medium TEXT
                )
            ''')
            
            # Link clicks tracking
            conn.execute('''
                CREATE TABLE IF NOT EXISTS link_clicks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    original_url TEXT NOT NULL,
                    utm_url TEXT,
                    clicked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    utm_source TEXT,
                    utm_campaign TEXT,
                    utm_medium TEXT,
                    ip_address TEXT
                )
            ''')
            
            # Broadcasts table - mass messages
            conn.execute('''
                CREATE TABLE IF NOT EXISTS broadcasts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT,
                    content TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    scheduled_at TIMESTAMP NULL,
                    sent_at TIMESTAMP NULL,
                    status TEXT DEFAULT 'draft',
                    total_recipients INTEGER DEFAULT 0,
                    successful_sends INTEGER DEFAULT 0,
                    failed_sends INTEGER DEFAULT 0,
                    utm_source TEXT,
                    utm_campaign TEXT
                )
            ''')
            
            # Channel settings
            conn.execute('''
                CREATE TABLE IF NOT EXISTS channel_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Bot metadata
            conn.execute('''
                CREATE TABLE IF NOT EXISTS bot_metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Statistics cache
            conn.execute('''
                CREATE TABLE IF NOT EXISTS stats_cache (
                    metric_name TEXT PRIMARY KEY,
                    metric_value TEXT,
                    calculated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            conn.commit()
    
    @contextmanager
    def get_connection(self):
        """Context manager for database connections"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Enable dict-like access
        try:
            yield conn
        except Exception as e:
            conn.rollback()
            logging.error(f"Database error: {e}")
            raise
        finally:
            conn.close()
    
    # User management
    def add_user(self, user_id: int, username: str = None, first_name: str = None, 
                 last_name: str = None, utm_source: str = None, utm_campaign: str = None):
        """Add new user to database"""
        with self.get_connection() as conn:
            conn.execute('''
                INSERT OR REPLACE INTO users 
                (user_id, username, first_name, last_name, utm_source, utm_campaign, last_activity)
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ''', (user_id, username, first_name, last_name, utm_source, utm_campaign))
            conn.commit()
    
    def get_user(self, user_id: int) -> Optional[Dict]:
        """Get user by ID"""
        with self.get_connection() as conn:
            cursor = conn.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def update_user_activity(self, user_id: int):
        """Update user last activity"""
        with self.get_connection() as conn:
            conn.execute('''
                UPDATE users SET last_activity = CURRENT_TIMESTAMP WHERE user_id = ?
            ''', (user_id,))
            conn.commit()
    
    def set_user_bot_started(self, user_id: int):
        """Mark user as having started the bot"""
        with self.get_connection() as conn:
            conn.execute('''
                UPDATE users SET bot_started = 1, last_activity = CURRENT_TIMESTAMP 
                WHERE user_id = ?
            ''', (user_id,))
            conn.commit()
    
    def get_active_users(self) -> List[Dict]:
        """Get all active users"""
        with self.get_connection() as conn:
            cursor = conn.execute('''
                SELECT * FROM users WHERE is_active = 1 ORDER BY joined_at DESC
            ''')
            return [dict(row) for row in cursor.fetchall()]
    
    def get_user_count(self) -> int:
        """Get total user count"""
        with self.get_connection() as conn:
            cursor = conn.execute('SELECT COUNT(*) FROM users WHERE is_active = 1')
            return cursor.fetchone()[0]
    
    # Message tracking
    def log_message(self, user_id: int = None, message_type: str = 'broadcast', 
                   content: str = None, utm_source: str = None, utm_campaign: str = None):
        """Log sent message"""
        with self.get_connection() as conn:
            conn.execute('''
                INSERT INTO messages (user_id, message_type, content, utm_source, utm_campaign)
                VALUES (?, ?, ?, ?, ?)
            ''', (user_id, message_type, content, utm_source, utm_campaign))
            conn.commit()
    
    def get_message_stats(self, days: int = 30) -> Dict:
        """Get message statistics"""
        with self.get_connection() as conn:
            cursor = conn.execute('''
                SELECT 
                    COUNT(*) as total_messages,
                    COUNT(DISTINCT user_id) as unique_recipients,
                    message_type,
                    COUNT(*) as count
                FROM messages 
                WHERE sent_at > datetime('now', '-{} days')
                GROUP BY message_type
            '''.format(days))
            
            stats = {'total_messages': 0, 'unique_recipients': 0, 'by_type': {}}
            for row in cursor.fetchall():
                stats['by_type'][row['message_type']] = row['count']
                stats['total_messages'] += row['count']
            
            # Get unique recipients
            cursor = conn.execute('''
                SELECT COUNT(DISTINCT user_id) as unique_recipients
                FROM messages 
                WHERE sent_at > datetime('now', '-{} days')
            '''.format(days))
            
            result = cursor.fetchone()
            stats['unique_recipients'] = result['unique_recipients'] if result else 0
            
            return stats
    
    # Link tracking
    def log_link_click(self, user_id: int, original_url: str, utm_url: str = None,
                      utm_source: str = None, utm_campaign: str = None, ip_address: str = None):
        """Log link click"""
        with self.get_connection() as conn:
            conn.execute('''
                INSERT INTO link_clicks 
                (user_id, original_url, utm_url, utm_source, utm_campaign, ip_address)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (user_id, original_url, utm_url, utm_source, utm_campaign, ip_address))
            conn.commit()
    
    def get_click_stats(self, days: int = 30) -> Dict:
        """Get click statistics"""
        with self.get_connection() as conn:
            cursor = conn.execute('''
                SELECT 
                    COUNT(*) as total_clicks,
                    COUNT(DISTINCT user_id) as unique_clickers,
                    COUNT(DISTINCT original_url) as unique_urls
                FROM link_clicks 
                WHERE clicked_at > datetime('now', '-{} days')
            '''.format(days))
            
            row = cursor.fetchone()
            return {
                'total_clicks': row['total_clicks'] if row else 0,
                'unique_clickers': row['unique_clickers'] if row else 0,
                'unique_urls': row['unique_urls'] if row else 0
            }
    
    # Broadcast management
    def create_broadcast(self, title: str, content: str, utm_source: str = None, 
                        utm_campaign: str = None) -> int:
        """Create new broadcast"""
        with self.get_connection() as conn:
            cursor = conn.execute('''
                INSERT INTO broadcasts (title, content, utm_source, utm_campaign)
                VALUES (?, ?, ?, ?)
            ''', (title, content, utm_source, utm_campaign))
            conn.commit()
            return cursor.lastrowid
    
    def get_broadcast(self, broadcast_id: int) -> Optional[Dict]:
        """Get broadcast by ID"""
        with self.get_connection() as conn:
            cursor = conn.execute('SELECT * FROM broadcasts WHERE id = ?', (broadcast_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def update_broadcast_stats(self, broadcast_id: int, total_recipients: int,
                              successful_sends: int, failed_sends: int):
        """Update broadcast statistics"""
        with self.get_connection() as conn:
            conn.execute('''
                UPDATE broadcasts 
                SET total_recipients = ?, successful_sends = ?, failed_sends = ?,
                    sent_at = CURRENT_TIMESTAMP, status = 'sent'
                WHERE id = ?
            ''', (total_recipients, successful_sends, failed_sends, broadcast_id))
            conn.commit()
    
    # Settings management
    def set_setting(self, key: str, value: str):
        """Set channel setting"""
        with self.get_connection() as conn:
            conn.execute('''
                INSERT OR REPLACE INTO channel_settings (key, value, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
            ''', (key, value))
            conn.commit()
    
    def get_setting(self, key: str, default: str = None) -> str:
        """Get channel setting"""
        with self.get_connection() as conn:
            cursor = conn.execute('SELECT value FROM channel_settings WHERE key = ?', (key,))
            row = cursor.fetchone()
            return row['value'] if row else default
    
    # Metadata management
    def set_metadata(self, key: str, value: str):
        """Set bot metadata"""
        with self.get_connection() as conn:
            conn.execute('''
                INSERT OR REPLACE INTO bot_metadata (key, value, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
            ''', (key, value))
            conn.commit()
    
    def get_metadata(self, key: str, default: str = None) -> str:
        """Get bot metadata"""
        with self.get_connection() as conn:
            cursor = conn.execute('SELECT value FROM bot_metadata WHERE key = ?', (key,))
            row = cursor.fetchone()
            return row['value'] if row else default
    
    # Dashboard statistics
    def get_dashboard_stats(self) -> Dict[str, Any]:
        """Get comprehensive dashboard statistics"""
        stats = {}
        
        with self.get_connection() as conn:
            # Total subscribers
            cursor = conn.execute('SELECT COUNT(*) FROM users WHERE is_active = 1')
            stats['total_subscribers'] = cursor.fetchone()[0]
            
            # Active users (last 7 days)
            cursor = conn.execute('''
                SELECT COUNT(*) FROM users 
                WHERE is_active = 1 AND last_activity > datetime('now', '-7 days')
            ''')
            stats['active_users'] = cursor.fetchone()[0]
            
            # Messages sent (last 30 days)
            cursor = conn.execute('''
                SELECT COUNT(*) FROM messages 
                WHERE sent_at > datetime('now', '-30 days')
            ''')
            stats['messages_sent'] = cursor.fetchone()[0]
            
            # Link clicks (last 30 days)
            cursor = conn.execute('''
                SELECT COUNT(*) FROM link_clicks 
                WHERE clicked_at > datetime('now', '-30 days')
            ''')
            stats['link_clicks'] = cursor.fetchone()[0]
            
            # Recent broadcasts
            cursor = conn.execute('''
                SELECT COUNT(*) FROM broadcasts 
                WHERE created_at > datetime('now', '-30 days')
            ''')
            stats['recent_broadcasts'] = cursor.fetchone()[0]
            
            # Bot started users
            cursor = conn.execute('SELECT COUNT(*) FROM users WHERE bot_started = 1')
            stats['bot_interactions'] = cursor.fetchone()[0]
        
        return stats
    
    # Cache management
    def cache_stat(self, metric_name: str, value: str):
        """Cache calculated statistic"""
        with self.get_connection() as conn:
            conn.execute('''
                INSERT OR REPLACE INTO stats_cache (metric_name, metric_value, calculated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
            ''', (metric_name, value))
            conn.commit()
    
    def get_cached_stat(self, metric_name: str, max_age_minutes: int = 60) -> Optional[str]:
        """Get cached statistic if not too old"""
        with self.get_connection() as conn:
            cursor = conn.execute('''
                SELECT metric_value FROM stats_cache 
                WHERE metric_name = ? 
                AND calculated_at > datetime('now', '-{} minutes')
            '''.format(max_age_minutes), (metric_name,))
            
            row = cursor.fetchone()
            return row['metric_value'] if row else None
