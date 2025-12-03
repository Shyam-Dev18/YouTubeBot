import os
import glob
import logging
import hashlib
import asyncio
from datetime import datetime, timedelta
from typing import List, Optional
from urllib.parse import urlparse, parse_qs

logger = logging.getLogger(__name__)

def format_size(size_bytes: int) -> str:
    """Format size in human readable format"""
    if not size_bytes or size_bytes <= 0:
        return "Unknown"
    
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} TB"

def cleanup_temp_files(files_to_keep: List[str] = None):
    """Clean up old temporary files"""
    temp_dir = "temp"
    if not os.path.exists(temp_dir):
        return
    
    try:
        # Get all files in temp directory
        all_files = glob.glob(os.path.join(temp_dir, "*"))
        
        for file_path in all_files:
            # Skip files we want to keep
            if files_to_keep and file_path in files_to_keep:
                continue
            
            if os.path.exists(file_path):
                try:
                    # Check if file is older than 10 minutes
                    file_age = datetime.now() - datetime.fromtimestamp(
                        os.path.getmtime(file_path)
                    )
                    
                    if file_age > timedelta(minutes=10):
                        os.remove(file_path)
                        logger.debug(f"Cleaned up: {file_path}")
                except Exception as e:
                    logger.warning(f"Could not remove {file_path}: {e}")
    
    except Exception as e:
        logger.error(f"Error during cleanup: {e}")

def is_valid_youtube_url(url: str) -> bool:
    """Validate YouTube URL"""
    youtube_domains = [
        'youtube.com',
        'youtu.be',
        'm.youtube.com',
        'www.youtube.com',
        'youtube-nocookie.com'
    ]
    
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        
        # Remove www. prefix if present
        if domain.startswith('www.'):
            domain = domain[4:]
        
        # Check if domain is YouTube
        if domain not in youtube_domains and not any(domain.endswith(d) for d in youtube_domains):
            return False
        
        # Check if it's a valid YouTube video URL
        if domain == 'youtu.be':
            return len(parsed.path) > 1  # Should have video ID after /
        
        # Check for watch parameter
        query = parse_qs(parsed.query)
        if 'v' in query:
            return len(query['v'][0]) > 0
        
        # Check for embed URL
        if '/embed/' in parsed.path:
            return True
        
        return False
        
    except Exception:
        return False

def get_video_id(url: str) -> Optional[str]:
    """Extract video ID from YouTube URL"""
    try:
        parsed = urlparse(url)
        
        if parsed.netloc == 'youtu.be':
            return parsed.path[1:]  # Remove leading slash
        
        query = parse_qs(parsed.query)
        if 'v' in query:
            return query['v'][0]
        
        # Check for embed URL
        if '/embed/' in parsed.path:
            return parsed.path.split('/embed/')[1].split('/')[0]
        
        return None
    except Exception:
        return None

async def run_async(func, *args, **kwargs):
    """Run a synchronous function asynchronously"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, func, *args, **kwargs)

def safe_filename(filename: str, max_length: int = 200) -> str:
    """Create a safe filename from title"""
    # Remove invalid characters
    invalid_chars = '<>:"/\\|?*\'"'
    for char in invalid_chars:
        filename = filename.replace(char, '')
    
    # Limit length
    if len(filename) > max_length:
        name, ext = os.path.splitext(filename)
        filename = name[:max_length - len(ext)] + ext
    
    return filename.strip()

def generate_file_hash(content: str) -> str:
    """Generate a hash for file identification"""
    return hashlib.md5(content.encode()).hexdigest()[:8]