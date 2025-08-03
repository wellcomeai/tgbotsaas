"""
Database Utilities - общие функции для работы с базами данных
"""

import os
import sqlite3
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List
from contextlib import contextmanager

def ensure_directory_exists(directory_path: Path):
    """Ensure directory exists, create if not"""
    try:
        directory_path.mkdir(parents=True, exist_ok=True)
        logging.info(f"Directory ensured: {directory_path}")
    except Exception as e:
        logging.error(f"Failed to create directory {directory_path}: {e}")
        raise

def get_data_directory() -> Path:
    """Get data directory path"""
    data_dir = os.environ.get('RENDER_DISK_PATH', '/data')
    return Path(data_dir)

def get_database_path(db_name: str) -> Path:
    """Get full path for database file"""
    data_dir = get_data_directory()
    return data_dir / db_name

def backup_database(db_path: str, backup_dir: str = None) -> Optional[str]:
    """Create database backup"""
    try:
        if backup_dir is None:
            backup_dir = get_data_directory() / 'backups'
        
        ensure_directory_exists(Path(backup_dir))
        
        # Generate backup filename with timestamp
        from datetime import datetime
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        db_name = Path(db_path).name
        backup_filename = f"{db_name}_{timestamp}.backup"
        backup_path = Path(backup_dir) / backup_filename
        
        # Copy database file
        import shutil
        shutil.copy2(db_path, backup_path)
        
        logging.info(f"Database backed up: {db_path} -> {backup_path}")
        return str(backup_path)
        
    except Exception as e:
        logging.error(f"Failed to backup database {db_path}: {e}")
        return None

def optimize_database(db_path: str):
    """Optimize database performance"""
    try:
        with sqlite3.connect(db_path) as conn:
            # Run VACUUM to reclaim space
            conn.execute('VACUUM')
            
            # Analyze tables for query optimization
            conn.execute('ANALYZE')
            
            # Update table statistics
            conn.execute('PRAGMA optimize')
            
            conn.commit()
            
        logging.info(f"Database optimized: {db_path}")
        
    except Exception as e:
        logging.error(f"Failed to optimize database {db_path}: {e}")

def get_database_info(db_path: str) -> Dict[str, Any]:
    """Get database information and statistics"""
    try:
        info = {
            'path': db_path,
            'exists': os.path.exists(db_path),
            'size_bytes': 0,
            'tables': [],
            'total_rows': 0
        }
        
        if not info['exists']:
            return info
        
        # Get file size
        info['size_bytes'] = os.path.getsize(db_path)
        info['size_mb'] = round(info['size_bytes'] / 1024 / 1024, 2)
        
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            
            # Get table list
            cursor = conn.execute('''
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name NOT LIKE 'sqlite_%'
                ORDER BY name
            ''')
            
            tables = []
            total_rows = 0
            
            for row in cursor.fetchall():
                table_name = row['name']
                
                # Get row count for each table
                count_cursor = conn.execute(f'SELECT COUNT(*) FROM {table_name}')
                row_count = count_cursor.fetchone()[0]
                
                tables.append({
                    'name': table_name,
                    'rows': row_count
                })
                
                total_rows += row_count
            
            info['tables'] = tables
            info['total_rows'] = total_rows
            
            # Get database version/user_version
            cursor = conn.execute('PRAGMA user_version')
            info['version'] = cursor.fetchone()[0]
            
        return info
        
    except Exception as e:
        logging.error(f"Failed to get database info for {db_path}: {e}")
        return {'path': db_path, 'error': str(e)}

def migrate_database(db_path: str, migrations: List[str]) -> bool:
    """Run database migrations"""
    try:
        with sqlite3.connect(db_path) as conn:
            # Get current version
            cursor = conn.execute('PRAGMA user_version')
            current_version = cursor.fetchone()[0]
            
            # Run migrations starting from current version
            for i, migration_sql in enumerate(migrations[current_version:], current_version):
                logging.info(f"Running migration {i + 1} on {db_path}")
                
                try:
                    conn.executescript(migration_sql)
                    
                    # Update version
                    conn.execute(f'PRAGMA user_version = {i + 1}')
                    conn.commit()
                    
                    logging.info(f"Migration {i + 1} completed successfully")
                    
                except Exception as e:
                    logging.error(f"Migration {i + 1} failed: {e}")
                    conn.rollback()
                    return False
            
            logging.info(f"All migrations completed for {db_path}")
            return True
            
    except Exception as e:
        logging.error(f"Failed to migrate database {db_path}: {e}")
        return False

def export_table_to_csv(db_path: str, table_name: str, output_path: str) -> bool:
    """Export table data to CSV"""
    try:
        import csv
        
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(f'SELECT * FROM {table_name}')
            
            rows = cursor.fetchall()
            if not rows:
                logging.warning(f"No data in table {table_name}")
                return True
            
            # Write CSV file
            with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                
                # Write header
                writer.writerow(rows[0].keys())
                
                # Write data
                for row in rows:
                    writer.writerow([row[col] for col in row.keys()])
            
            logging.info(f"Exported {len(rows)} rows from {table_name} to {output_path}")
            return True
            
    except Exception as e:
        logging.error(f"Failed to export table {table_name}: {e}")
        return False

def cleanup_old_records(db_path: str, table_name: str, date_column: str, 
                       days_to_keep: int) -> int:
    """Clean up old records from database"""
    try:
        with sqlite3.connect(db_path) as conn:
            # Count records to be deleted
            cursor = conn.execute(f'''
                SELECT COUNT(*) FROM {table_name} 
                WHERE {date_column} < datetime('now', '-{days_to_keep} days')
            ''')
            
            records_to_delete = cursor.fetchone()[0]
            
            if records_to_delete == 0:
                return 0
            
            # Delete old records
            cursor = conn.execute(f'''
                DELETE FROM {table_name} 
                WHERE {date_column} < datetime('now', '-{days_to_keep} days')
            ''')
            
            conn.commit()
            
            logging.info(f"Cleaned up {records_to_delete} old records from {table_name}")
            return records_to_delete
            
    except Exception as e:
        logging.error(f"Failed to cleanup old records from {table_name}: {e}")
        return 0

@contextmanager
def database_transaction(db_path: str):
    """Context manager for database transactions"""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        logging.error(f"Database transaction error: {e}")
        raise
    finally:
        conn.close()

def test_database_connection(db_path: str) -> bool:
    """Test database connection"""
    try:
        with sqlite3.connect(db_path, timeout=5) as conn:
            cursor = conn.execute('SELECT 1')
            result = cursor.fetchone()
            return result is not None
            
    except Exception as e:
        logging.error(f"Database connection test failed for {db_path}: {e}")
        return False

def create_indexes(db_path: str, indexes: Dict[str, str]) -> bool:
    """Create database indexes"""
    try:
        with sqlite3.connect(db_path) as conn:
            for index_name, index_sql in indexes.items():
                try:
                    conn.execute(f'CREATE INDEX IF NOT EXISTS {index_name} {index_sql}')
                    logging.info(f"Created index: {index_name}")
                except Exception as e:
                    logging.warning(f"Failed to create index {index_name}: {e}")
            
            conn.commit()
            return True
            
    except Exception as e:
        logging.error(f"Failed to create indexes: {e}")
        return False

def get_table_schema(db_path: str, table_name: str) -> Optional[List[Dict]]:
    """Get table schema information"""
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.execute(f'PRAGMA table_info({table_name})')
            columns = []
            
            for row in cursor.fetchall():
                columns.append({
                    'cid': row[0],
                    'name': row[1],
                    'type': row[2],
                    'notnull': bool(row[3]),
                    'default_value': row[4],
                    'pk': bool(row[5])
                })
            
            return columns
            
    except Exception as e:
        logging.error(f"Failed to get schema for table {table_name}: {e}")
        return None
