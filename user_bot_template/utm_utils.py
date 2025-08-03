"""
UTM Utils - утилиты для автоматического добавления UTM-меток
"""

import re
import logging
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from typing import Optional

def add_utm_to_url(url: str, user_id: int, source: str = 'bot', 
                   campaign: str = 'auto', medium: str = 'telegram') -> str:
    """
    Add UTM parameters to URL
    
    Args:
        url: Original URL
        user_id: User ID for utm_id parameter  
        source: UTM source (default: 'bot')
        campaign: UTM campaign (default: 'auto')
        medium: UTM medium (default: 'telegram')
        
    Returns:
        URL with UTM parameters
    """
    try:
        # Parse URL
        parsed = urlparse(url)
        
        # Skip if not http/https
        if parsed.scheme not in ['http', 'https']:
            return url
            
        query_params = parse_qs(parsed.query)
        
        # Add UTM parameters if not already present
        utm_params = {
            'utm_source': source,
            'utm_medium': medium, 
            'utm_campaign': campaign,
            'utm_id': str(user_id)
        }
        
        for key, value in utm_params.items():
            if key not in query_params:
                query_params[key] = [value]
        
        # Rebuild URL
        new_query = urlencode(query_params, doseq=True)
        new_parsed = parsed._replace(query=new_query)
        
        return urlunparse(new_parsed)
        
    except Exception as e:
        logging.error(f"Error adding UTM to URL {url}: {e}")
        return url  # Return original URL if error

def process_text_links(text: str, user_id: int, source: str = 'bot', 
                      campaign: str = 'auto') -> str:
    """
    Process all links in text and add UTM parameters
    
    Args:
        text: Text containing URLs
        user_id: User ID for UTM tracking
        source: UTM source
        campaign: UTM campaign
        
    Returns:
        Text with UTM-enhanced URLs
    """
    try:
        # Pattern for URLs
        url_pattern = r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
        
        def replace_url(match):
            original_url = match.group(0)
            utm_url = add_utm_to_url(original_url, user_id, source, campaign)
            return utm_url
        
        # Replace all URLs with UTM versions
        processed_text = re.sub(url_pattern, replace_url, text)
        
        return processed_text
        
    except Exception as e:
        logging.error(f"Error processing text links: {e}")
        return text  # Return original text if error

def extract_utm_params(url: str) -> dict:
    """
    Extract UTM parameters from URL
    
    Args:
        url: URL to extract UTM parameters from
        
    Returns:
        Dictionary with UTM parameters
    """
    try:
        parsed = urlparse(url)
        query_params = parse_qs(parsed.query)
        
        utm_params = {}
        utm_keys = ['utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'utm_term', 'utm_id']
        
        for key in utm_keys:
            if key in query_params and query_params[key]:
                utm_params[key] = query_params[key][0]  # Take first value
        
        return utm_params
        
    except Exception as e:
        logging.error(f"Error extracting UTM params from {url}: {e}")
        return {}

def is_utm_url(url: str) -> bool:
    """
    Check if URL already contains UTM parameters
    
    Args:
        url: URL to check
        
    Returns:
        True if URL contains UTM parameters
    """
    utm_params = extract_utm_params(url)
    return len(utm_params) > 0

def remove_utm_params(url: str) -> str:
    """
    Remove UTM parameters from URL
    
    Args:
        url: URL to clean
        
    Returns:
        URL without UTM parameters
    """
    try:
        parsed = urlparse(url)
        query_params = parse_qs(parsed.query)
        
        # Remove UTM parameters
        utm_keys = ['utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'utm_term', 'utm_id']
        for key in utm_keys:
            if key in query_params:
                del query_params[key]
        
        # Rebuild URL
        new_query = urlencode(query_params, doseq=True)
        new_parsed = parsed._replace(query=new_query)
        
        return urlunparse(new_parsed)
        
    except Exception as e:
        logging.error(f"Error removing UTM params from {url}: {e}")
        return url

def generate_campaign_name(message_type: str, user_count: int = None) -> str:
    """
    Generate campaign name based on message type
    
    Args:
        message_type: Type of message ('welcome', 'broadcast', 'auto_message', etc.)
        user_count: Number of users (for broadcasts)
        
    Returns:
        Generated campaign name
    """
    try:
        from datetime import datetime
        timestamp = datetime.now().strftime('%Y%m%d')
        
        if message_type == 'welcome':
            return f'welcome_{timestamp}'
        elif message_type == 'broadcast':
            if user_count:
                return f'broadcast_{user_count}users_{timestamp}'
            return f'broadcast_{timestamp}'
        elif message_type == 'auto_message':
            return f'auto_sequence_{timestamp}'
        elif message_type == 'scheduled':
            return f'scheduled_{timestamp}'
        else:
            return f'{message_type}_{timestamp}'
            
    except Exception as e:
        logging.error(f"Error generating campaign name: {e}")
        return 'default_campaign'

def validate_url(url: str) -> bool:
    """
    Validate URL format
    
    Args:
        url: URL to validate
        
    Returns:
        True if URL is valid
    """
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc]) and result.scheme in ['http', 'https']
    except Exception:
        return False

def format_utm_report(utm_stats: dict) -> str:
    """
    Format UTM statistics for reporting
    
    Args:
        utm_stats: Dictionary with UTM statistics
        
    Returns:
        Formatted report string
    """
    try:
        report = "📊 **UTM Трекинг - Отчет**\n\n"
        
        if 'total_clicks' in utm_stats:
            report += f"🔗 Всего кликов: {utm_stats['total_clicks']}\n"
        
        if 'unique_users' in utm_stats:
            report += f"👥 Уникальных пользователей: {utm_stats['unique_users']}\n"
        
        if 'by_source' in utm_stats:
            report += "\n**По источникам:**\n"
            for source, count in utm_stats['by_source'].items():
                report += f"• {source}: {count} кликов\n"
        
        if 'by_campaign' in utm_stats:
            report += "\n**По кампаниям:**\n"
            for campaign, count in utm_stats['by_campaign'].items():
                report += f"• {campaign}: {count} кликов\n"
        
        if 'top_urls' in utm_stats:
            report += "\n**Популярные ссылки:**\n"
            for url, count in utm_stats['top_urls'].items():
                # Shorten URL for display
                display_url = url[:50] + "..." if len(url) > 50 else url
                report += f"• {display_url}: {count} кликов\n"
        
        return report
        
    except Exception as e:
        logging.error(f"Error formatting UTM report: {e}")
        return "Ошибка при формировании отчета"

def create_tracking_link(base_url: str, user_id: int, message_type: str, 
                        button_text: str = None) -> str:
    """
    Create tracking link with specific parameters
    
    Args:
        base_url: Base URL to track
        user_id: User ID
        message_type: Type of message containing the link
        button_text: Text of button (if applicable)
        
    Returns:
        Tracking URL
    """
    try:
        campaign = generate_campaign_name(message_type)
        source = 'bot'
        medium = 'telegram'
        
        # Add content parameter if button text provided
        utm_url = add_utm_to_url(base_url, user_id, source, campaign, medium)
        
        if button_text:
            # Add utm_content for button tracking
            parsed = urlparse(utm_url)
            query_params = parse_qs(parsed.query)
            query_params['utm_content'] = [button_text.lower().replace(' ', '_')]
            
            new_query = urlencode(query_params, doseq=True)
            new_parsed = parsed._replace(query=new_query)
            utm_url = urlunparse(new_parsed)
        
        return utm_url
        
    except Exception as e:
        logging.error(f"Error creating tracking link: {e}")
        return base_url
