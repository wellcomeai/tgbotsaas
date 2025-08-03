"""
Bot Process Manager - управление жизненным циклом пользовательских ботов
УЛУЧШЕНО: Добавлено надежное восстановление процессов и отслеживание статусов
"""

import asyncio
import json
import logging
import os
import subprocess
import signal
import psutil
import sys
import traceback
import time
from datetime import datetime
from typing import Dict, Optional, List
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    from .config_generator import BotConfigGenerator
    logging.info("✅ Successfully imported BotConfigGenerator")
except ImportError as e:
    logging.error(f"❌ Import error in process_manager: {e}")
    logging.error(f"Traceback: {traceback.format_exc()}")
    sys.exit(1)

class BotProcessManager:
    def __init__(self):
        self.running_processes: Dict[int, subprocess.Popen] = {}
        self.config_generator = BotConfigGenerator()
        
        # Data directories
        data_dir = os.environ.get('RENDER_DISK_PATH', '/data')
        self.bot_configs_dir = Path(data_dir) / "bot_configs"
        self.user_databases_dir = Path(data_dir) / "user_databases"
        
        # Ensure directories exist
        self._ensure_directories()
        
        # НОВОЕ: Попытаться восстановить информацию о запущенных процессах
        self._discover_running_processes()
        
        logging.info("✅ BotProcessManager initialized successfully")
    
    def _ensure_directories(self):
        """Ensure all required directories exist"""
        try:
            self.bot_configs_dir.mkdir(parents=True, exist_ok=True)
            self.user_databases_dir.mkdir(parents=True, exist_ok=True)
            logging.info(f"✅ Ensured directories: {self.bot_configs_dir}, {self.user_databases_dir}")
        except Exception as e:
            logging.error(f"❌ Failed to create directories: {e}")
    
    def _discover_running_processes(self):
        """НОВОЕ: Попытаться найти уже запущенные user bot процессы"""
        try:
            logging.info("🔍 Discovering existing user bot processes...")
            
            discovered_count = 0
            
            # Поиск процессов python с аргументом user_bot_template.main
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    if proc.info['name'] and 'python' in proc.info['name'].lower():
                        cmdline = proc.info['cmdline']
                        if cmdline and 'user_bot_template.main' in ' '.join(cmdline):
                            # Извлекаем bot-id из командной строки
                            bot_id = None
                            for i, arg in enumerate(cmdline):
                                if arg == '--bot-id' and i + 1 < len(cmdline):
                                    try:
                                        bot_id = int(cmdline[i + 1])
                                        break
                                    except ValueError:
                                        continue
                            
                            if bot_id:
                                # Создаем Popen объект для существующего процесса
                                # Это хак, но позволяет отслеживать существующий процесс
                                mock_process = type('MockProcess', (), {
                                    'pid': proc.info['pid'],
                                    'poll': lambda: None,  # Процесс работает
                                    'terminate': lambda: proc.terminate(),
                                    'kill': lambda: proc.kill(),
                                    'wait': lambda timeout=None: proc.wait(timeout)
                                })()
                                
                                self.running_processes[bot_id] = mock_process
                                discovered_count += 1
                                
                                logging.info(f"🔍 Discovered running bot {bot_id} (PID: {proc.info['pid']})")
                
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue
                except Exception as e:
                    logging.warning(f"Error checking process: {e}")
                    continue
            
            if discovered_count > 0:
                logging.info(f"🔍 Discovered {discovered_count} existing user bot processes")
            else:
                logging.info("🔍 No existing user bot processes found")
                
        except Exception as e:
            logging.error(f"❌ Error discovering processes: {e}")
    
    async def deploy_user_bot(self, bot_id: int) -> bool:
        """Deploy and start a user bot instance"""
        try:
            logging.info(f"🚀 Starting deployment of bot {bot_id}")
            
            # Generate bot configuration
            logging.info(f"🔄 Generating config for bot {bot_id}...")
            config_path = await self.config_generator.generate_config(bot_id)
            if not config_path:
                logging.error(f"❌ Failed to generate config for bot {bot_id}")
                return False
            
            logging.info(f"✅ Config generated: {config_path}")
            
            # Create isolated database
            database_path = self.user_databases_dir / f"bot_{bot_id}.db"
            logging.info(f"🔄 Initializing database: {database_path}")
            await self._initialize_bot_database(database_path, bot_id)
            logging.info(f"✅ Database initialized: {database_path}")
            
            # Update database with paths
            try:
                from master_bot.database import MasterDatabase
                db = MasterDatabase()
                db.update_bot_config_path(bot_id, str(config_path), str(database_path))
                logging.info(f"✅ Updated master database with paths for bot {bot_id}")
            except Exception as e:
                logging.warning(f"⚠️ Failed to update master database: {e}")
            
            # Start bot process
            logging.info(f"🔄 Starting bot process for bot {bot_id}...")
            process_id = await self._start_bot_process(bot_id, config_path)
            
            if process_id:
                # Update database with process ID and status
                try:
                    db = MasterDatabase()
                    db.update_bot_process_id(bot_id, process_id)
                    db.update_bot_status(bot_id, 'active')
                    logging.info(f"✅ Updated bot {bot_id} status to active with PID {process_id}")
                except Exception as e:
                    logging.warning(f"⚠️ Failed to update bot status in master DB: {e}")
                
                logging.info(f"🎉 Bot {bot_id} deployed successfully with PID {process_id}")
                return True
            else:
                try:
                    db = MasterDatabase()
                    db.update_bot_status(bot_id, 'error', 'Failed to start process')
                except:
                    pass
                logging.error(f"❌ Failed to start bot {bot_id}")
                return False
                
        except Exception as e:
            logging.error(f"❌ Error deploying bot {bot_id}: {e}")
            logging.error(f"Traceback: {traceback.format_exc()}")
            
            # Update database with error status
            try:
                from master_bot.database import MasterDatabase
                db = MasterDatabase()
                db.update_bot_status(bot_id, 'error', str(e))
            except:
                pass  # Don't fail deployment due to database error
                
            return False
    
    async def _start_bot_process(self, bot_id: int, config_path: Path) -> Optional[str]:
        """Start bot process as subprocess - IMPROVED WITH BETTER TRACKING"""
        try:
            # Проверим, не запущен ли уже этот бот
            if bot_id in self.running_processes:
                existing_process = self.running_processes[bot_id]
                if existing_process.poll() is None:
                    logging.info(f"🔄 Bot {bot_id} process already running (PID: {existing_process.pid})")
                    return str(existing_process.pid)
                else:
                    # Процесс умер, удаляем из списка
                    del self.running_processes[bot_id]
            
            # Use python from current environment and explicit path to main module
            python_executable = sys.executable
            logging.info(f"🔄 Using Python executable: {python_executable}")
            
            # IMPROVED COMMAND STRUCTURE FOR RENDER
            cmd = [
                python_executable, '-m', 'user_bot_template.main',
                '--config', str(config_path),
                '--bot-id', str(bot_id)
            ]
            
            logging.info(f"🔄 Command to execute: {' '.join(cmd)}")
            logging.info(f"🔄 Working directory: {project_root}")
            logging.info(f"🔄 Config path: {config_path}")
            logging.info(f"🔄 Config exists: {config_path.exists()}")
            
            # Verify config file is readable
            if not config_path.exists():
                logging.error(f"❌ Config file does not exist: {config_path}")
                return None
            
            try:
                with open(config_path, 'r') as f:
                    config_content = f.read()
                logging.info(f"✅ Config file readable, size: {len(config_content)} bytes")
            except Exception as e:
                logging.error(f"❌ Cannot read config file: {e}")
                return None
            
            # IMPROVED ENVIRONMENT SETUP FOR RENDER
            env = os.environ.copy()
            
            # Critical: Set PYTHONPATH to include project root
            current_pythonpath = env.get('PYTHONPATH', '')
            if current_pythonpath:
                env['PYTHONPATH'] = f"{project_root}:{current_pythonpath}"
            else:
                env['PYTHONPATH'] = str(project_root)
            
            env['BOT_ID'] = str(bot_id)
            
            logging.info(f"🔄 PYTHONPATH set to: {env['PYTHONPATH']}")
            logging.info(f"🔄 BOT_ID set to: {env['BOT_ID']}")
            
            # Create log files for the bot
            log_dir = Path(os.environ.get('RENDER_DISK_PATH', '/tmp')) / 'logs'
            log_dir.mkdir(exist_ok=True, parents=True)
            
            stdout_log = log_dir / f"bot_{bot_id}_stdout.log"
            stderr_log = log_dir / f"bot_{bot_id}_stderr.log"
            
            logging.info(f"🔄 Log files will be: {stdout_log}, {stderr_log}")
            
            # FIRST: Test the command with --help-test to verify it works
            logging.info(f"🔄 Testing command with --help-test...")
            test_cmd = [
                python_executable, '-m', 'user_bot_template.main',
                '--config', str(config_path),
                '--bot-id', str(bot_id),
                '--help-test'
            ]
            
            try:
                test_result = subprocess.run(
                    test_cmd,
                    capture_output=True,
                    text=True,
                    timeout=30,
                    env=env,
                    cwd=str(project_root)
                )
                
                logging.info(f"🔄 Test command exit code: {test_result.returncode}")
                if test_result.stdout:
                    logging.info(f"📄 Test stdout: {test_result.stdout}")
                if test_result.stderr:
                    logging.info(f"📄 Test stderr: {test_result.stderr}")
                
                if test_result.returncode != 0:
                    logging.error(f"❌ Test command failed with exit code {test_result.returncode}")
                    return None
                else:
                    logging.info(f"✅ Test command successful")
                    
            except subprocess.TimeoutExpired:
                logging.error(f"❌ Test command timed out")
                return None
            except Exception as e:
                logging.error(f"❌ Test command failed: {e}")
                return None
            
            # NOW: Start the real process
            logging.info(f"🔄 Starting real bot process...")
            logging.info(f"🔄 Log files to be created: {stdout_log}, {stderr_log}")
            
            # Ensure log files can be created
            try:
                # Test creating log files
                with open(stdout_log, 'w') as f:
                    f.write(f"=== Bot {bot_id} started at {datetime.now()} ===\n")
                with open(stderr_log, 'w') as f:
                    f.write(f"=== Bot {bot_id} started at {datetime.now()} ===\n")
                logging.info(f"✅ Log files created successfully")
            except Exception as e:
                logging.error(f"❌ Cannot create log files: {e}")
                return None
            
            try:
                logging.info(f"🔄 About to execute: {' '.join(cmd)}")
                logging.info(f"🔄 Working dir: {project_root}")
                logging.info(f"🔄 Environment PYTHONPATH: {env.get('PYTHONPATH')}")
                
                # Start process with improved error handling
                process = subprocess.Popen(
                    cmd,
                    stdout=open(stdout_log, 'a'),  # Append mode
                    stderr=open(stderr_log, 'a'),  # Append mode
                    env=env,
                    cwd=str(project_root),
                    preexec_fn=os.setsid  # Create new process group
                )
                
                logging.info(f"🔄 Process started with PID {process.pid}")
                
                # Immediately check if process is still alive
                initial_poll = process.poll()
                if initial_poll is not None:
                    logging.error(f"❌ Process died immediately with exit code: {initial_poll}")
                    await self._log_process_failure(bot_id, stdout_log, stderr_log)
                    return None
                
                logging.info(f"✅ Process {process.pid} started successfully, waiting for initialization...")
                
                # Wait for process to initialize (longer wait)
                for i in range(15):  # Check every 2 seconds for 30 seconds total
                    await asyncio.sleep(2)
                    poll_result = process.poll()
                    
                    if poll_result is not None:
                        # Process died
                        logging.error(f"❌ Process {process.pid} died after {i*2} seconds with exit code: {poll_result}")
                        await self._log_process_failure(bot_id, stdout_log, stderr_log)
                        return None
                    else:
                        logging.info(f"🔄 Process {process.pid} still running after {(i+1)*2} seconds...")
                
                # Process survived 30 seconds - consider it successful
                self.running_processes[bot_id] = process
                logging.info(f"✅ Bot {bot_id} process started successfully with PID {process.pid} (survived 30s)")
                return str(process.pid)
                    
            except FileNotFoundError as e:
                logging.error(f"❌ File not found when starting process: {e}")
                logging.error(f"❌ Command that failed: {cmd}")
                logging.error(f"❌ Working directory: {project_root}")
                logging.error(f"❌ Python executable exists: {Path(python_executable).exists()}")
                return None
                
        except Exception as e:
            logging.error(f"❌ Error starting bot process {bot_id}: {e}")
            logging.error(f"Traceback: {traceback.format_exc()}")
            return None
    
    async def _log_process_failure(self, bot_id: int, stdout_log: Path, stderr_log: Path):
        """Log detailed process failure information"""
        try:
            logging.error(f"📋 Process failure details for bot {bot_id}:")
            
            # Read stderr logs
            if stderr_log.exists():
                try:
                    with open(stderr_log, 'r') as f:
                        error_content = f.read()
                    if error_content.strip():
                        logging.error(f"❌ STDERR content: {error_content[-2000:]}")  # Last 2000 chars
                    else:
                        logging.error(f"❌ STDERR file is empty")
                except Exception as e:
                    logging.error(f"❌ Could not read stderr log: {e}")
            else:
                logging.error(f"❌ STDERR log file does not exist: {stderr_log}")
            
            # Read stdout logs
            if stdout_log.exists():
                try:
                    with open(stdout_log, 'r') as f:
                        stdout_content = f.read()
                    if stdout_content.strip():
                        logging.error(f"📄 STDOUT content: {stdout_content[-2000:]}")  # Last 2000 chars
                    else:
                        logging.error(f"📄 STDOUT file is empty")
                except Exception as e:
                    logging.error(f"❌ Could not read stdout log: {e}")
            else:
                logging.error(f"❌ STDOUT log file does not exist: {stdout_log}")
                
        except Exception as e:
            logging.error(f"❌ Error logging process failure: {e}")
    
    async def stop_bot(self, bot_id: int) -> bool:
        """Stop bot process gracefully"""
        try:
            logging.info(f"🔄 Stopping bot {bot_id}...")
            
            if bot_id in self.running_processes:
                process = self.running_processes[bot_id]
                
                # Send SIGTERM for graceful shutdown
                try:
                    if hasattr(process, 'pid'):
                        os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                        logging.info(f"🔄 Sent SIGTERM to bot {bot_id}")
                    else:
                        process.terminate()
                        logging.info(f"🔄 Sent terminate to bot {bot_id}")
                except:
                    # Fallback to regular terminate
                    process.terminate()
                    logging.info(f"🔄 Sent terminate to bot {bot_id}")
                
                # Wait for graceful shutdown
                try:
                    process.wait(timeout=10)
                    logging.info(f"✅ Bot {bot_id} stopped gracefully")
                except subprocess.TimeoutExpired:
                    # Force kill if not responding
                    try:
                        if hasattr(process, 'pid'):
                            os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                        else:
                            process.kill()
                    except:
                        process.kill()
                    process.wait()
                    logging.warning(f"⚠️ Bot {bot_id} force killed")
                
                del self.running_processes[bot_id]
                
                # Update database
                try:
                    from master_bot.database import MasterDatabase
                    db = MasterDatabase()
                    db.update_bot_status(bot_id, 'stopped')
                    logging.info(f"✅ Updated bot {bot_id} status to stopped")
                except Exception as e:
                    logging.warning(f"⚠️ Failed to update bot status: {e}")
                
                return True
            else:
                logging.info(f"ℹ️ Bot {bot_id} not found in running processes")
                return True  # Consider it stopped if not running
                
        except Exception as e:
            logging.error(f"❌ Error stopping bot {bot_id}: {e}")
            return False
    
    async def restart_bot(self, bot_id: int) -> bool:
        """Restart bot process - IMPROVED WITH STATUS CHECKING"""
        try:
            logging.info(f"🔄 Restarting bot {bot_id}")
            
            # Stop if running
            await self.stop_bot(bot_id)
            
            # Wait a moment for cleanup
            await asyncio.sleep(2)
            
            # Get config path
            config_path = self.bot_configs_dir / f"bot_{bot_id}_config.json"
            
            if not config_path.exists():
                logging.error(f"❌ Config file not found for bot {bot_id}: {config_path}")
                try:
                    from master_bot.database import MasterDatabase
                    db = MasterDatabase()
                    db.update_bot_status(bot_id, 'error', 'Config file not found')
                except:
                    pass
                return False
            
            # Start again
            process_id = await self._start_bot_process(bot_id, config_path)
            
            if process_id:
                try:
                    from master_bot.database import MasterDatabase
                    db = MasterDatabase()
                    db.update_bot_process_id(bot_id, process_id)
                    db.update_bot_status(bot_id, 'active')
                    logging.info(f"✅ Bot {bot_id} restarted successfully")
                except Exception as e:
                    logging.warning(f"⚠️ Failed to update master database: {e}")
                return True
            else:
                logging.error(f"❌ Failed to restart bot {bot_id}")
                try:
                    from master_bot.database import MasterDatabase
                    db = MasterDatabase()
                    db.update_bot_status(bot_id, 'error', 'Failed to restart process')
                except:
                    pass
                return False
                
        except Exception as e:
            logging.error(f"❌ Error restarting bot {bot_id}: {e}")
            try:
                from master_bot.database import MasterDatabase
                db = MasterDatabase()
                db.update_bot_status(bot_id, 'error', f'Restart failed: {str(e)}')
            except:
                pass
            return False
    
    async def check_bot_health(self, bot_id: int) -> bool:
        """Check if bot process is healthy - IMPROVED"""
        try:
            if bot_id not in self.running_processes:
                logging.warning(f"⚠️ Bot {bot_id} not in running processes list")
                return False
            
            process = self.running_processes[bot_id]
            
            # Check if process is still running
            if process.poll() is not None:
                # Process has terminated
                del self.running_processes[bot_id]
                logging.warning(f"⚠️ Bot {bot_id} process terminated unexpectedly")
                
                # Update status in database
                try:
                    from master_bot.database import MasterDatabase
                    db = MasterDatabase()
                    db.update_bot_status(bot_id, 'error', 'Process terminated unexpectedly')
                except:
                    pass
                
                return False
            
            # Check process resource usage if we have PID
            try:
                if hasattr(process, 'pid'):
                    proc = psutil.Process(process.pid)
                    
                    # Check if process is responsive (not zombie)
                    if proc.status() == psutil.STATUS_ZOMBIE:
                        logging.warning(f"⚠️ Bot {bot_id} process is zombie")
                        return False
                    
                    # Check memory usage (shouldn't exceed 200MB per bot)
                    memory_mb = proc.memory_info().rss / 1024 / 1024
                    if memory_mb > 200:
                        logging.warning(f"⚠️ Bot {bot_id} using excessive memory: {memory_mb:.1f}MB")
                        # Don't kill, just warn for now
                    
                    # Update last ping in database
                    try:
                        from master_bot.database import MasterDatabase
                        db = MasterDatabase()
                        db.update_bot_status(bot_id, 'active')
                    except:
                        pass
                    
                    return True
                else:
                    # Mock process from discovery, assume healthy
                    return True
                
            except psutil.NoSuchProcess:
                logging.warning(f"⚠️ Bot {bot_id} process no longer exists")
                del self.running_processes[bot_id]
                
                # Update status in database
                try:
                    from master_bot.database import MasterDatabase
                    db = MasterDatabase()
                    db.update_bot_status(bot_id, 'error', 'Process no longer exists')
                except:
                    pass
                
                return False
                
        except Exception as e:
            logging.error(f"❌ Error checking bot {bot_id} health: {e}")
            return False
    
    async def _initialize_bot_database(self, database_path: Path, bot_id: int):
        """Initialize database for new bot"""
        try:
            from user_bot_template.database import Database
            
            # Create database with bot-specific path
            db = Database(str(database_path))
            
            # Set bot metadata
            db.set_metadata('bot_id', str(bot_id))
            db.set_metadata('created_at', datetime.now().isoformat())
            
            logging.info(f"✅ Initialized database for bot {bot_id}: {database_path}")
            
        except Exception as e:
            logging.error(f"❌ Error initializing database for bot {bot_id}: {e}")
            raise
    
    def get_running_bots(self) -> List[int]:
        """Get list of currently running bot IDs - IMPROVED"""
        # Clean up dead processes
        dead_bots = []
        for bot_id, process in self.running_processes.items():
            try:
                if process.poll() is not None:
                    dead_bots.append(bot_id)
            except Exception as e:
                logging.warning(f"Error checking process for bot {bot_id}: {e}")
                dead_bots.append(bot_id)
        
        for bot_id in dead_bots:
            del self.running_processes[bot_id]
            logging.info(f"🧹 Cleaned up dead process for bot {bot_id}")
            
            # Update database status
            try:
                from master_bot.database import MasterDatabase
                db = MasterDatabase()
                db.update_bot_status(bot_id, 'error', 'Process died unexpectedly')
            except:
                pass
        
        return list(self.running_processes.keys())
    
    async def shutdown_all_bots(self):
        """Gracefully shutdown all running bots"""
        logging.info("🔄 Shutting down all running bots...")
        
        for bot_id in list(self.running_processes.keys()):
            await self.stop_bot(bot_id)
        
        logging.info("✅ All bots shut down")
    
    def get_bot_process_info(self, bot_id: int) -> Optional[Dict]:
        """Get process information for a bot - IMPROVED"""
        if bot_id not in self.running_processes:
            return None
        
        try:
            process = self.running_processes[bot_id]
            
            if hasattr(process, 'pid'):
                try:
                    proc = psutil.Process(process.pid)
                    
                    return {
                        'pid': process.pid,
                        'status': proc.status(),
                        'memory_mb': round(proc.memory_info().rss / 1024 / 1024, 2),
                        'cpu_percent': proc.cpu_percent(),
                        'create_time': datetime.fromtimestamp(proc.create_time()).isoformat(),
                        'is_running': proc.is_running()
                    }
                except psutil.NoSuchProcess:
                    return {
                        'pid': process.pid,
                        'status': 'not_found',
                        'error': 'Process no longer exists'
                    }
            else:
                # Mock process from discovery
                return {
                    'pid': process.pid,
                    'status': 'discovered',
                    'note': 'Process discovered during startup'
                }
        except Exception as e:
            logging.error(f"❌ Error getting process info for bot {bot_id}: {e}")
            return {
                'error': str(e)
            }
    
    async def health_check_all_bots(self):
        """НОВОЕ: Проверить здоровье всех запущенных ботов и восстановить при необходимости"""
        try:
            logging.info("🏥 Running health check for all bots...")
            
            running_bots = self.get_running_bots()  # Это также очистит мертвые процессы
            
            if not running_bots:
                logging.info("🏥 No running bots to check")
                return
            
            unhealthy_bots = []
            
            for bot_id in running_bots:
                is_healthy = await self.check_bot_health(bot_id)
                if not is_healthy:
                    unhealthy_bots.append(bot_id)
                    logging.warning(f"🏥 Bot {bot_id} is unhealthy")
            
            # Попытаться восстановить нездоровые боты
            for bot_id in unhealthy_bots:
                logging.info(f"🏥 Attempting to restart unhealthy bot {bot_id}")
                success = await self.restart_bot(bot_id)
                if success:
                    logging.info(f"🏥 Successfully restarted bot {bot_id}")
                else:
                    logging.error(f"🏥 Failed to restart bot {bot_id}")
            
            logging.info(f"🏥 Health check complete: {len(running_bots)} checked, {len(unhealthy_bots)} needed restart")
            
        except Exception as e:
            logging.error(f"❌ Error in health check: {e}")
