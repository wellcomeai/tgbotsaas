"""
Telegram Utilities - вспомогательные функции для работы с Telegram API
"""

import httpx
import logging
from typing import Optional, Dict

async def verify_bot_token(token: str) -> Optional[Dict]:
    """
    Verify bot token by calling getMe method
    
    Args:
        token: Bot token from BotFather
        
    Returns:
        Dict with bot info if valid, None if invalid
    """
    try:
        url = f"https://api.telegram.org/bot{token}/getMe"
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=10.0)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('ok'):
                    bot_info = data['result']
                    return {
                        'id': bot_info['id'],
                        'username': bot_info['username'],
                        'first_name': bot_info['first_name'],
                        'is_bot': bot_info['is_bot']
                    }
                else:
                    logging.warning(f"Bot API returned error: {data.get('description')}")
                    return None
            else:
                logging.warning(f"HTTP error verifying token: {response.status_code}")
                return None
                
    except httpx.TimeoutException:
        logging.error("Timeout verifying bot token")
        return None
    except Exception as e:
        logging.error(f"Error verifying bot token: {e}")
        return None

async def send_telegram_message(token: str, chat_id: int, text: str, 
                               parse_mode: str = None) -> bool:
    """
    Send message via Telegram Bot API
    
    Args:
        token: Bot token
        chat_id: Chat ID to send to
        text: Message text
        parse_mode: Parse mode (Markdown, HTML, etc.)
        
    Returns:
        True if sent successfully, False otherwise
    """
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        
        payload = {
            'chat_id': chat_id,
            'text': text
        }
        
        if parse_mode:
            payload['parse_mode'] = parse_mode
        
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, timeout=10.0)
            
            if response.status_code == 200:
                data = response.json()
                return data.get('ok', False)
            else:
                logging.warning(f"Failed to send message: {response.status_code}")
                return False
                
    except Exception as e:
        logging.error(f"Error sending telegram message: {e}")
        return False

def format_username(username: str) -> str:
    """Format username with @ prefix if not present"""
    if username and not username.startswith('@'):
        return f"@{username}"
    return username or ""

def extract_bot_username(token: str) -> Optional[str]:
    """Extract bot username from token (basic validation)"""
    try:
        # Token format: bot_id:auth_token
        bot_id = token.split(':')[0]
        return f"bot{bot_id}"  # Approximate username
    except:
        return None
