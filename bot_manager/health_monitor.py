"""
Health Monitor - мониторинг состояния ботов
"""

import logging
import asyncio
import psutil
from datetime import datetime
from typing import Dict, List, Optional

class HealthMonitor:
    def __init__(self, process_manager):
        self.process_manager = process_manager
        self.monitoring = False
        self.check_interval = 300  # 5 minutes
    
    async def start_monitoring(self):
        """Start health monitoring loop"""
        self.monitoring = True
        logging.info("Health monitoring started")
        
        while self.monitoring:
            try:
                await self.check_all_bots()
                await asyncio.sleep(self.check_interval)
            except Exception as e:
                logging.error(f"Health monitoring error: {e}")
                await asyncio.sleep(60)  # Wait 1 minute on error
    
    def stop_monitoring(self):
        """Stop health monitoring"""
        self.monitoring = False
        logging.info("Health monitoring stopped")
    
    async def check_all_bots(self):
        """Check health of all running bots"""
        running_bots = self.process_manager.get_running_bots()
        
        for bot_id in running_bots:
            is_healthy = await self.process_manager.check_bot_health(bot_id)
            
            if not is_healthy:
                logging.warning(f"Bot {bot_id} is unhealthy, attempting restart")
                await self.process_manager.restart_bot(bot_id)
    
    def get_system_metrics(self) -> Dict:
        """Get system performance metrics"""
        try:
            return {
                'cpu_percent': psutil.cpu_percent(),
                'memory_percent': psutil.virtual_memory().percent,
                'disk_percent': psutil.disk_usage('/').percent,
                'timestamp': datetime.now().isoformat()
            }
        except Exception as e:
            logging.error(f"Error getting system metrics: {e}")
            return {}
