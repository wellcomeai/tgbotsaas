"""
Flask Application - HTTP server for webhook endpoints and health checks
Main entry point for the SaaS platform
ИСПРАВЛЕНО: Добавлено автовосстановление user ботов после перезагрузки
"""

import os
import logging
import tempfile
import sys
import subprocess
import time
import traceback
import json
import asyncio
from pathlib import Path
from flask import Flask, jsonify, request
from datetime import datetime

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'dev-secret-key-change-in-production')

def get_data_directory() -> Path:
    """Get data directory path with fallback"""
    render_disk_path = os.environ.get('RENDER_DISK_PATH', '/data')
    data_dir = Path(render_disk_path)
    
    # Check if directory exists and is writable
    if data_dir.exists() and os.access(data_dir, os.W_OK):
        return data_dir
    
    # Fallback to temporary directory for local development
    temp_dir = Path(tempfile.gettempdir()) / 'bot_factory_temp'
    logging.warning(f"Using temporary directory: {temp_dir} (disk not available)")
    return temp_dir

def ensure_data_directory():
    """Ensure data directory exists with proper fallback"""
    try:
        data_dir = get_data_directory()
        
        # Try to create main directory
        try:
            data_dir.mkdir(parents=True, exist_ok=True)
            logging.info(f"Data directory ensured: {data_dir}")
        except PermissionError:
            logging.error(f"Permission denied creating {data_dir}")
            if not data_dir.exists():
                logging.info("Continuing without data directory for first deploy")
                return
        
        # Create subdirectories if main directory exists
        if data_dir.exists() and os.access(data_dir, os.W_OK):
            subdirs = ['bot_configs', 'user_databases', 'logs']
            for subdir in subdirs:
                try:
                    subdir_path = data_dir / subdir
                    subdir_path.mkdir(exist_ok=True)
                    logging.info(f"Subdirectory ensured: {subdir_path}")
                except Exception as e:
                    logging.warning(f"Could not create subdirectory {subdir}: {e}")
        else:
            logging.info("Data directory not writable, skipping subdirectory creation")
    
    except Exception as e:
        logging.error(f"Error in ensure_data_directory: {e}")

# Global variable to track master bot process
master_bot_process = None

def start_master_bot_process():
    """Start master bot as separate process"""
    global master_bot_process
    
    try:
        master_bot_token = os.environ.get('MASTER_BOT_TOKEN')
        if not master_bot_token:
            logging.error("MASTER_BOT_TOKEN not set, master bot will not start")
            return False
        
        data_dir = get_data_directory()
        if not data_dir.exists():
            logging.error("Data directory not available, master bot will not start")
            return False
        
        # Check if process is already running
        if master_bot_process and master_bot_process.poll() is None:
            logging.info("Master bot process already running")
            return True
        
        # Start master bot as separate process
        cmd = [sys.executable, 'run_master_bot.py']
        env = os.environ.copy()
        env['PYTHONPATH'] = str(project_root)
        
        # ВАЖНО: Перенаправляем STDOUT и STDERR в файлы для отладки
        log_dir = data_dir / 'logs'
        log_dir.mkdir(exist_ok=True)
        
        stdout_log = log_dir / 'master_bot_stdout.log'
        stderr_log = log_dir / 'master_bot_stderr.log'
        
        master_bot_process = subprocess.Popen(
            cmd,
            env=env,
            cwd=str(project_root),
            stdout=open(stdout_log, 'w'),
            stderr=open(stderr_log, 'w')
        )
        
        # Wait a moment to check if process started
        time.sleep(3)
        
        if master_bot_process.poll() is None:
            logging.info(f"Master bot process started with PID {master_bot_process.pid}")
            return True
        else:
            # Process failed - read error logs
            try:
                with open(stderr_log, 'r') as f:
                    error_content = f.read()
                logging.error(f"Master bot process failed to start:")
                logging.error(f"STDERR: {error_content}")
            except:
                logging.error("Master bot failed and no error log available")
            return False
            
    except Exception as e:
        logging.error(f"Error starting master bot process: {e}")
        return False

def restore_user_bots():
    """НОВАЯ ФУНКЦИЯ: Восстановить активные user боты после перезагрузки"""
    try:
        logging.info("🔄 Checking for active user bots to restore...")
        
        data_dir = get_data_directory()
        if not data_dir.exists():
            logging.warning("Data directory not available, skipping user bot restoration")
            return
        
        # Import database here to avoid circular imports
        try:
            from master_bot.database import MasterDatabase
            from bot_manager.process_manager import BotProcessManager
        except ImportError as e:
            logging.error(f"Failed to import required modules for bot restoration: {e}")
            return
        
        # Get active bots from database
        db = MasterDatabase()
        active_bots = db.get_active_bots()
        
        if not active_bots:
            logging.info("No active bots found in database")
            return
        
        logging.info(f"Found {len(active_bots)} active bots in database")
        
        # Initialize process manager
        manager = BotProcessManager()
        
        # Check which bots need to be restored
        restored_count = 0
        failed_count = 0
        
        for bot in active_bots:
            bot_id = bot['id']
            bot_username = bot.get('bot_username', 'unknown')
            
            try:
                logging.info(f"🔄 Checking bot {bot_id} (@{bot_username})...")
                
                # Check if bot process is already running
                if manager.get_bot_process_info(bot_id):
                    logging.info(f"✅ Bot {bot_id} process already running")
                    continue
                
                # Check if config file exists
                config_path = manager.bot_configs_dir / f"bot_{bot_id}_config.json"
                if not config_path.exists():
                    logging.warning(f"❌ Config file missing for bot {bot_id}: {config_path}")
                    db.update_bot_status(bot_id, 'error', 'Config file missing')
                    failed_count += 1
                    continue
                
                # Attempt to restart the bot
                logging.info(f"🚀 Restoring bot {bot_id} (@{bot_username})...")
                
                # Use asyncio to run the async method
                import asyncio
                success = asyncio.run(manager.restart_bot(bot_id))
                
                if success:
                    logging.info(f"✅ Successfully restored bot {bot_id}")
                    restored_count += 1
                else:
                    logging.error(f"❌ Failed to restore bot {bot_id}")
                    failed_count += 1
                    
            except Exception as e:
                logging.error(f"❌ Error restoring bot {bot_id}: {e}")
                db.update_bot_status(bot_id, 'error', f'Restoration failed: {str(e)}')
                failed_count += 1
        
        logging.info(f"🎯 Bot restoration complete: {restored_count} restored, {failed_count} failed")
        
        # Log restoration event
        if restored_count > 0 or failed_count > 0:
            db.log_event(
                event_type='system_restart',
                description=f"Auto-restored {restored_count} bots, {failed_count} failed after server restart"
            )
        
    except Exception as e:
        logging.error(f"❌ Error in restore_user_bots: {e}")
        logging.error(f"Traceback: {traceback.format_exc()}")

@app.route('/health')
def health_check():
    """Health check endpoint for Render"""
    try:
        data_dir = get_data_directory()
        
        # Check master bot process status
        master_bot_running = False
        master_bot_status = "not_started"
        
        if master_bot_process:
            poll_result = master_bot_process.poll()
            if poll_result is None:
                master_bot_running = True
                master_bot_status = "running"
            else:
                master_bot_status = f"exited_with_code_{poll_result}"
        
        response_data = {
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'data_directory': str(data_dir),
            'data_directory_exists': data_dir.exists(),
            'version': '1.0.0-mvp',
            'master_bot_token_set': bool(os.environ.get('MASTER_BOT_TOKEN')),
            'master_bot_running': master_bot_running,
            'master_bot_status': master_bot_status,
            'master_bot_pid': master_bot_process.pid if master_bot_process else None
        }
        
        # Try to check database only if data directory exists
        if data_dir.exists():
            try:
                from master_bot.database import MasterDatabase
                db = MasterDatabase()
                stats = db.get_system_stats()
                response_data.update({
                    'database_connected': True,
                    'total_users': stats.get('total_users', 0),
                    'total_bots': stats.get('total_bots', 0),
                    'active_bots': stats.get('active_bots', 0)
                })
                
                # Check user bot statuses
                try:
                    from bot_manager.process_manager import BotProcessManager
                    manager = BotProcessManager()
                    running_bots = manager.get_running_bots()
                    response_data.update({
                        'running_user_bots': len(running_bots),
                        'running_bot_ids': running_bots
                    })
                except Exception as e:
                    response_data.update({
                        'user_bot_manager_error': str(e)
                    })
                    
            except Exception as db_error:
                logging.warning(f"Database check failed: {db_error}")
                response_data.update({
                    'database_connected': False,
                    'database_error': str(db_error)
                })
        else:
            response_data.update({
                'database_connected': False,
                'note': 'Data directory not available yet'
            })
        
        return jsonify(response_data)
        
    except Exception as e:
        logging.error(f"Health check failed: {e}")
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

# НОВЫЙ ENDPOINT для ручного восстановления ботов
@app.route('/restore_user_bots', methods=['POST'])
def restore_user_bots_endpoint():
    """Manual endpoint to restore user bots"""
    try:
        restore_user_bots()
        return jsonify({
            'success': True,
            'message': 'User bot restoration completed, check logs for details'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# Все остальные endpoint'ы остаются без изменений...
# (оставляю только ключевые, остальные не изменились)

# NEW DIAGNOSTIC ENDPOINTS
@app.route('/api/test_import')
def test_import():
    """Test importing all critical modules"""
    import_results = {}
    
    # Test core imports
    modules_to_test = [
        'master_bot.database',
        'master_bot.main', 
        'bot_manager.process_manager',
        'bot_manager.config_generator',
        'user_bot_template.main',
        'user_bot_template.database',
        'shared.telegram_utils'
    ]
    
    for module_name in modules_to_test:
        try:
            __import__(module_name)
            import_results[module_name] = {
                'status': 'success',
                'error': None
            }
        except Exception as e:
            import_results[module_name] = {
                'status': 'failed',
                'error': str(e),
                'traceback': traceback.format_exc()
            }
    
    # Test specific class imports
    class_tests = {}
    
    try:
        from master_bot.database import MasterDatabase
        db = MasterDatabase()
        class_tests['MasterDatabase'] = 'success'
    except Exception as e:
        class_tests['MasterDatabase'] = f'failed: {e}'
    
    try:
        from bot_manager.process_manager import BotProcessManager
        manager = BotProcessManager()
        class_tests['BotProcessManager'] = 'success'
    except Exception as e:
        class_tests['BotProcessManager'] = f'failed: {e}'
    
    try:
        from bot_manager.config_generator import BotConfigGenerator
        config_gen = BotConfigGenerator()
        class_tests['BotConfigGenerator'] = 'success'
    except Exception as e:
        class_tests['BotConfigGenerator'] = f'failed: {e}'
    
    return jsonify({
        'module_imports': import_results,
        'class_instantiation': class_tests,
        'python_path': sys.path[:10],  # First 10 entries
        'project_root': str(project_root),
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/debug_files')
def debug_files():
    """Check what files were created in data directory"""
    try:
        data_dir = get_data_directory()
        
        file_info = {
            'data_dir': str(data_dir),
            'data_dir_exists': data_dir.exists(),
            'subdirectories': {},
            'bot_configs': {},
            'user_databases': {},
            'logs': {}
        }
        
        if not data_dir.exists():
            return jsonify(file_info)
        
        # Check subdirectories
        subdirs = ['bot_configs', 'user_databases', 'logs']
        for subdir in subdirs:
            subdir_path = data_dir / subdir
            file_info['subdirectories'][subdir] = {
                'exists': subdir_path.exists(),
                'is_dir': subdir_path.is_dir() if subdir_path.exists() else False,
                'files': []
            }
            
            if subdir_path.exists() and subdir_path.is_dir():
                try:
                    files = list(subdir_path.glob('*'))
                    file_info['subdirectories'][subdir]['files'] = [
                        {
                            'name': f.name,
                            'size': f.stat().st_size if f.is_file() else 0,
                            'is_file': f.is_file(),
                            'modified': datetime.fromtimestamp(f.stat().st_mtime).isoformat() if f.exists() else None
                        }
                        for f in files
                    ]
                except Exception as e:
                    file_info['subdirectories'][subdir]['error'] = str(e)
        
        # Check specific bot config files
        bot_configs_dir = data_dir / 'bot_configs'
        if bot_configs_dir.exists():
            try:
                for config_file in bot_configs_dir.glob('bot_*_config.json'):
                    try:
                        with open(config_file, 'r') as f:
                            content = f.read()
                        file_info['bot_configs'][config_file.name] = {
                            'size': len(content),
                            'valid_json': True,
                            'preview': content[:200] + '...' if len(content) > 200 else content
                        }
                    except json.JSONDecodeError:
                        file_info['bot_configs'][config_file.name] = {
                            'size': config_file.stat().st_size,
                            'valid_json': False,
                            'error': 'Invalid JSON'
                        }
                    except Exception as e:
                        file_info['bot_configs'][config_file.name] = {
                            'error': str(e)
                        }
            except Exception as e:
                file_info['bot_configs']['error'] = str(e)
        
        return jsonify(file_info)
        
    except Exception as e:
        return jsonify({
            'error': str(e),
            'traceback': traceback.format_exc(),
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/api/debug_database')
def debug_database():
    """Check database contents and recent operations"""
    try:
        data_dir = get_data_directory()
        
        if not data_dir.exists():
            return jsonify({
                'error': 'Data directory does not exist',
                'data_dir': str(data_dir)
            })
        
        # Try to connect to database
        try:
            from master_bot.database import MasterDatabase
            db = MasterDatabase()
            
            # Get all users
            with db.get_connection() as conn:
                cursor = conn.execute('SELECT * FROM saas_users ORDER BY created_at DESC LIMIT 10')
                users = [dict(row) for row in cursor.fetchall()]
                
                cursor = conn.execute('SELECT * FROM user_bots ORDER BY created_at DESC LIMIT 10')
                bots = [dict(row) for row in cursor.fetchall()]
                
                cursor = conn.execute('SELECT * FROM system_logs ORDER BY created_at DESC LIMIT 20')
                logs = [dict(row) for row in cursor.fetchall()]
            
            return jsonify({
                'database_connected': True,
                'recent_users': users,
                'recent_bots': bots,
                'recent_logs': logs,
                'system_stats': db.get_system_stats(),
                'timestamp': datetime.now().isoformat()
            })
            
        except Exception as db_error:
            return jsonify({
                'database_connected': False,
                'database_error': str(db_error),
                'traceback': traceback.format_exc(),
                'timestamp': datetime.now().isoformat()
            })
        
    except Exception as e:
        return jsonify({
            'error': str(e),
            'traceback': traceback.format_exc(),
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/api/debug_bot_deployment')
def debug_bot_deployment():
    """Test bot deployment process step by step"""
    try:
        # Simulate bot deployment process
        results = {
            'step1_imports': {},
            'step2_config_generation': {},
            'step3_database_creation': {},
            'step4_process_start': {},
            'overall_status': 'testing'
        }
        
        # Step 1: Test imports
        try:
            from bot_manager.process_manager import BotProcessManager
            from bot_manager.config_generator import BotConfigGenerator
            results['step1_imports'] = {
                'status': 'success',
                'message': 'All required modules imported successfully'
            }
        except Exception as e:
            results['step1_imports'] = {
                'status': 'failed',
                'error': str(e),
                'traceback': traceback.format_exc()
            }
            return jsonify(results)
        
        # Step 2: Test config generation (simulation)
        try:
            config_gen = BotConfigGenerator()
            results['step2_config_generation'] = {
                'status': 'success',
                'configs_dir': str(config_gen.configs_dir),
                'configs_dir_exists': config_gen.configs_dir.exists()
            }
        except Exception as e:
            results['step2_config_generation'] = {
                'status': 'failed',
                'error': str(e)
            }
        
        # Step 3: Test process manager initialization
        try:
            manager = BotProcessManager()
            results['step3_database_creation'] = {
                'status': 'success',
                'bot_configs_dir': str(manager.bot_configs_dir),
                'user_databases_dir': str(manager.user_databases_dir),
                'directories_exist': {
                    'bot_configs': manager.bot_configs_dir.exists(),
                    'user_databases': manager.user_databases_dir.exists()
                }
            }
        except Exception as e:
            results['step3_database_creation'] = {
                'status': 'failed',
                'error': str(e)
            }
        
        # Step 4: Check what would happen with subprocess
        try:
            python_executable = sys.executable
            cmd = [python_executable, '-m', 'user_bot_template.main', '--help']
            
            results['step4_process_start'] = {
                'status': 'simulated',
                'python_executable': python_executable,
                'command': cmd,
                'project_root': str(project_root),
                'pythonpath': str(project_root),
                'note': 'This is a simulation - actual subprocess not started'
            }
        except Exception as e:
            results['step4_process_start'] = {
                'status': 'failed',
                'error': str(e)
            }
        
        results['overall_status'] = 'completed'
        return jsonify(results)
        
    except Exception as e:
        return jsonify({
            'error': str(e),
            'traceback': traceback.format_exc(),
            'timestamp': datetime.now().isoformat()
        }), 500

# NEW: User bot logs endpoint
@app.route('/api/user_bot_logs')
def user_bot_logs():
    """Get logs from user bot processes"""
    try:
        bot_id = request.args.get('bot_id', type=int)
        data_dir = get_data_directory()
        log_dir = data_dir / 'logs'
        
        result = {
            'data_dir': str(data_dir),
            'log_dir': str(log_dir),
            'log_dir_exists': log_dir.exists(),
            'bot_logs': {},
            'all_bot_logs': {},
            'timestamp': datetime.now().isoformat()
        }
        
        if not log_dir.exists():
            return jsonify(result)
        
        # Get logs for specific bot if bot_id provided
        if bot_id:
            bot_logs = {}
            log_patterns = [
                f"bot_{bot_id}_stdout.log",
                f"bot_{bot_id}_stderr.log", 
                f"user_bot_{bot_id}.log",
                f"user_bot_{bot_id}_internal.log"
            ]
            
            for pattern in log_patterns:
                log_file = log_dir / pattern
                if log_file.exists():
                    try:
                        with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()
                        bot_logs[pattern] = {
                            'size': len(content),
                            'content': content[-3000:] if len(content) > 3000 else content,  # Last 3000 chars
                            'full_content_available': len(content) > 3000
                        }
                    except Exception as e:
                        bot_logs[pattern] = {
                            'error': str(e),
                            'size': log_file.stat().st_size if log_file.exists() else 0
                        }
                else:
                    bot_logs[pattern] = {
                        'exists': False,
                        'note': 'Log file does not exist'
                    }
            
            result['bot_logs'] = bot_logs
        
        # Get all user bot logs summary
        all_logs = {}
        try:
            for log_file in log_dir.glob('bot_*_*.log'):
                try:
                    with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                    all_logs[log_file.name] = {
                        'size': len(content),
                        'last_modified': datetime.fromtimestamp(log_file.stat().st_mtime).isoformat(),
                        'preview': content[-500:] if content else 'Empty file'  # Last 500 chars preview
                    }
                except Exception as e:
                    all_logs[log_file.name] = {
                        'error': str(e),
                        'size': log_file.stat().st_size if log_file.exists() else 0
                    }
            
            # Also check for internal logs
            for log_file in log_dir.glob('user_bot_*.log'):
                try:
                    with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                    all_logs[log_file.name] = {
                        'size': len(content),
                        'last_modified': datetime.fromtimestamp(log_file.stat().st_mtime).isoformat(),
                        'preview': content[-500:] if content else 'Empty file'
                    }
                except Exception as e:
                    all_logs[log_file.name] = {
                        'error': str(e),
                        'size': log_file.stat().st_size if log_file.exists() else 0
                    }
                    
        except Exception as e:
            all_logs['error'] = str(e)
        
        result['all_bot_logs'] = all_logs
        return jsonify(result)
        
    except Exception as e:
        return jsonify({
            'error': str(e),
            'traceback': traceback.format_exc(),
            'timestamp': datetime.now().isoformat()
        }), 500

# END NEW DIAGNOSTIC ENDPOINTS

@app.route('/logs')
def show_logs():
    """Show log files content - ДОБАВЛЕН ДЛЯ ОТЛАДКИ"""
    try:
        log_files = []
        data_dir = get_data_directory()
        log_dir = data_dir / 'logs'
        
        if log_dir.exists():
            for log_file in log_dir.glob('*.log'):
                try:
                    with open(log_file, 'r') as f:
                        content = f.read()
                    
                    log_files.append({
                        'file': str(log_file.name),
                        'size': len(content),
                        'content': content[-2000:] if len(content) > 2000 else content  # Последние 2000 символов
                    })
                except Exception as e:
                    log_files.append({
                        'file': str(log_file.name),
                        'error': str(e)
                    })
        
        # Также проверим системные процессы
        try:
            import subprocess as sp
            ps_result = sp.run(['ps', 'aux'], capture_output=True, text=True)
            ps_output = ps_result.stdout
            
            # Найдем python процессы
            python_processes = [line for line in ps_output.split('\n') if 'python' in line.lower()]
        except:
            python_processes = ["Could not get process list"]
        
        return jsonify({
            'logs': log_files,
            'log_dir_exists': log_dir.exists(),
            'log_dir_path': str(log_dir),
            'python_processes': python_processes,
            'data_dir': str(data_dir),
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/bot_info')
def bot_info():
    """Get Master Bot information from Telegram API"""
    try:
        import httpx
        
        master_bot_token = os.environ.get('MASTER_BOT_TOKEN')
        if not master_bot_token:
            return jsonify({'error': 'Master bot token not configured'}), 400
        
        # Call Telegram getMe API
        url = f"https://api.telegram.org/bot{master_bot_token}/getMe"
        
        try:
            with httpx.Client() as client:
                response = client.get(url, timeout=10.0)
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get('ok'):
                        bot_info = data['result']
                        return jsonify({
                            'success': True,
                            'bot_info': {
                                'id': bot_info['id'],
                                'username': bot_info['username'],
                                'first_name': bot_info['first_name'],
                                'is_bot': bot_info['is_bot'],
                                'telegram_link': f"https://t.me/{bot_info['username']}"
                            },
                            'raw_response': data
                        })
                    else:
                        return jsonify({
                            'success': False,
                            'error': data.get('description', 'Unknown error')
                        }), 400
                else:
                    return jsonify({
                        'success': False,
                        'error': f'HTTP {response.status_code}',
                        'response': response.text
                    }), 400
        except Exception as e:
            return jsonify({
                'success': False,
                'error': f'Request failed: {str(e)}'
            }), 500
        
    except Exception as e:
        return jsonify({
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/debug')
def debug_info():
    """Debug information endpoint"""
    try:
        data_dir = get_data_directory()
        
        # Check if run_master_bot.py exists
        master_bot_script = project_root / 'run_master_bot.py'
        
        # Check current working directory and files
        current_files = list(project_root.glob('*.py'))
        
        debug_info = {
            'project_root': str(project_root),
            'current_directory': os.getcwd(),
            'python_path': sys.path[:5],  # First 5 entries
            'master_bot_script_exists': master_bot_script.exists(),
            'python_files_in_root': [f.name for f in current_files],
            'environment_vars': {
                'MASTER_BOT_TOKEN': bool(os.environ.get('MASTER_BOT_TOKEN')),
                'RENDER_DISK_PATH': os.environ.get('RENDER_DISK_PATH'),
                'PYTHONPATH': os.environ.get('PYTHONPATH')
            },
            'data_directory_info': {
                'path': str(data_dir),
                'exists': data_dir.exists(),
                'is_writable': os.access(data_dir, os.W_OK) if data_dir.exists() else False
            }
        }
        
        return jsonify(debug_info)
        
    except Exception as e:
        return jsonify({
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/api/status')
def api_status():
    """API status endpoint"""
    try:
        data_dir = get_data_directory()
        
        # Check master bot process
        master_bot_running = False
        master_bot_pid = None
        
        if master_bot_process:
            poll_result = master_bot_process.poll()
            master_bot_running = poll_result is None
            master_bot_pid = master_bot_process.pid
        
        status_data = {
            'flask_running': True,
            'master_bot_running': master_bot_running,
            'master_bot_pid': master_bot_pid,
            'data_directory_available': data_dir.exists(),
            'master_bot_token_configured': bool(os.environ.get('MASTER_BOT_TOKEN')),
            'timestamp': datetime.now().isoformat()
        }
        
        if not data_dir.exists():
            status_data.update({
                'status': 'initializing',
                'message': 'Data directory not available yet'
            })
            return jsonify(status_data)
        
        try:
            from bot_manager.process_manager import BotProcessManager
            from master_bot.database import MasterDatabase
            
            db = MasterDatabase()
            manager = BotProcessManager()
            
            active_bots = db.get_active_bots()
            running_bots = manager.get_running_bots()
            
            status_data.update({
                'active_bots_db': len(active_bots),
                'running_processes': len(running_bots),
                'running_bot_ids': running_bots,
                'bots_needing_restoration': len(active_bots) - len(running_bots)
            })
            
        except ImportError as e:
            logging.warning(f"Could not import modules: {e}")
            status_data.update({
                'active_bots_db': 0,
                'running_processes': 0,
                'import_error': str(e)
            })
        except Exception as e:
            logging.warning(f"Could not get bot status: {e}")
            status_data.update({
                'active_bots_db': 0,
                'running_processes': 0,
                'status_error': str(e)
            })
        
        return jsonify(status_data)
        
    except Exception as e:
        logging.error(f"Status check failed: {e}")
        return jsonify({
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/start_master_bot', methods=['POST'])
def start_master_bot_endpoint():
    """Manual endpoint to start master bot"""
    try:
        success = start_master_bot_process()
        
        if success:
            return jsonify({
                'success': True,
                'message': 'Master bot process started',
                'pid': master_bot_process.pid if master_bot_process else None
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Failed to start master bot process'
            }), 500
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/stop_master_bot', methods=['POST'])
def stop_master_bot_endpoint():
    """Manual endpoint to stop master bot"""
    global master_bot_process
    
    try:
        if master_bot_process and master_bot_process.poll() is None:
            master_bot_process.terminate()
            master_bot_process.wait(timeout=10)
            logging.info("Master bot process stopped")
            
            return jsonify({
                'success': True,
                'message': 'Master bot process stopped'
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Master bot process not running'
            })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/')
def index():
    """Simple index page"""
    master_bot_running = False
    if master_bot_process:
        master_bot_running = master_bot_process.poll() is None
    
    return jsonify({
        'service': 'Telegram Bot Factory',
        'status': 'running',
        'version': '1.0.0-mvp',
        'endpoints': {
            'health': '/health',
            'status': '/api/status', 
            'logs': '/logs',
            'debug': '/debug',
            'bot_info': '/bot_info',
            'test_import': '/api/test_import',
            'debug_files': '/api/debug_files',
            'debug_database': '/api/debug_database',
            'debug_bot_deployment': '/api/debug_bot_deployment',
            'user_bot_logs': '/api/user_bot_logs?bot_id=X',
            'restore_user_bots': '/restore_user_bots (POST)',  # НОВЫЙ
            'start_master_bot': '/start_master_bot (POST)',
            'stop_master_bot': '/stop_master_bot (POST)'
        },
        'data_directory_available': get_data_directory().exists(),
        'master_bot_token_configured': bool(os.environ.get('MASTER_BOT_TOKEN')),
        'master_bot_running': master_bot_running,
        'master_bot_pid': master_bot_process.pid if master_bot_process else None,
        'instructions': 'Master bot and user bots run as separate processes. Use POST endpoints to control them.'
    })

if __name__ == '__main__':
    # Ensure data directory exists
    ensure_data_directory()
    
    # Log environment info
    logging.info("=== Bot Factory Starting ===")
    logging.info(f"Data directory: {get_data_directory()}")
    logging.info(f"Master bot token configured: {bool(os.environ.get('MASTER_BOT_TOKEN'))}")
    
    # Try to start master bot process automatically
    data_dir = get_data_directory()
    master_token = os.environ.get('MASTER_BOT_TOKEN')
    
    if master_token and data_dir.exists():
        logging.info("Attempting to start master bot process...")
        success = start_master_bot_process()
        if success:
            logging.info("Master bot process started successfully")
        else:
            logging.warning("Master bot process failed to start - check /logs endpoint")
    else:
        logging.info("Master bot will not start automatically:")
        logging.info(f"  - Token configured: {bool(master_token)}")
        logging.info(f"  - Data directory exists: {data_dir.exists()}")
        logging.info("Use POST /start_master_bot to start manually")
    
    # НОВОЕ: Восстановить user ботов после старта master bot
    if master_token and data_dir.exists():
        logging.info("Attempting to restore user bots...")
        try:
            # Даем время master bot'у полностью запуститься
            time.sleep(5)
            restore_user_bots()
        except Exception as e:
            logging.error(f"Error during user bot restoration: {e}")
            logging.info("You can manually restore user bots using POST /restore_user_bots")
    
    # Start Flask app
    port = int(os.environ.get('PORT', 10000))
    logging.info(f"Starting Flask app on port {port}")
    
    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)
