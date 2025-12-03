import os
import asyncio
import logging
import re
from typing import Dict, List, Optional, Callable, Any
from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor

import yt_dlp
from config import config

logger = logging.getLogger(__name__)

class YouTubeDownloader:
    def __init__(self):
        self.executor = ThreadPoolExecutor(max_workers=3)
        self.active_downloads: Dict[int, Any] = {}
        self.cookies_file = self._setup_cookies()
    
    def _setup_cookies(self) -> str:
        """Setup cookies file from environment variable (REQUIRED)"""
        cookies_content = config.COOKIES_TXT
        if not cookies_content:
            raise ValueError(
                "COOKIES_TXT environment variable is required but not set. "
                "Please add your cookies.txt content to Koyeb secrets."
            )
        
        try:
            # Ensure temp directory exists
            os.makedirs(config.TEMP_DIR, exist_ok=True)
            
            # Write cookies to temp file
            cookies_path = os.path.join(config.TEMP_DIR, 'cookies.txt')
            with open(cookies_path, 'w', encoding='utf-8') as f:
                f.write(cookies_content)
            
            logger.info(f"Cookies file created at {cookies_path}")
            return cookies_path
        except Exception as e:
            raise RuntimeError(f"Failed to setup cookies file: {e}")
        
    async def get_available_resolutions(self, url: str) -> List[Dict]:
        """Get available video resolutions with size information"""
        try:
            loop = asyncio.get_event_loop()
            
            def extract_info():
                opts = {
                    'quiet': True,
                    'no_warnings': True,
                    'extract_flat': False,
                    'socket_timeout': 30,
                    'cookiefile': self.cookies_file,  # Required
                }
                
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(url, download=False)
                    
                    if not info:
                        return []
                    
                    # Get basic video info
                    video_info = {
                        'title': info.get('title', 'Unknown'),
                        'duration': str(timedelta(seconds=info.get('duration', 0))),
                        'channel': info.get('channel', 'Unknown'),
                        'thumbnail': info.get('thumbnail'),
                        'formats': []
                    }
                    
                    # Find all video formats with H.264 codec
                    video_formats = []
                    audio_formats = []
                    
                    for f in info.get('formats', []):
                        # Check if format is compatible
                        if not self._is_compatible_format(f):
                            continue
                        
                        format_id = f.get('format_id', '')
                        vcodec = f.get('vcodec', '')
                        acodec = f.get('acodec', '')
                        resolution = f.get('resolution', 'audio only')
                        fps = f.get('fps', 0)
                        filesize = f.get('filesize') or f.get('filesize_approx', 0)
                        
                        format_data = {
                            'format_id': format_id,
                            'resolution': resolution,
                            'fps': str(int(fps)) if fps else '',
                            'vcodec': vcodec,
                            'acodec': acodec,
                            'filesize': filesize,
                            'ext': f.get('ext', ''),
                            'has_video': vcodec != 'none',
                            'has_audio': acodec != 'none',
                        }
                        
                        if vcodec != 'none':
                            video_formats.append(format_data)
                        elif acodec != 'none':
                            audio_formats.append(format_data)
                    
                    # Sort video formats by resolution (highest first)
                    video_formats.sort(key=lambda x: self._parse_resolution(x['resolution']), reverse=True)
                    
                    # Get best audio format
                    best_audio = None
                    if audio_formats:
                        # Prefer AAC audio
                        aac_audio = [a for a in audio_formats if 'aac' in a['acodec'].lower() or 'mp4a' in a['acodec'].lower()]
                        if aac_audio:
                            best_audio = max(aac_audio, key=lambda x: x.get('filesize', 0))
                        else:
                            best_audio = max(audio_formats, key=lambda x: x.get('filesize', 0))
                    
                    # Create resolution options
                    resolution_options = []
                    seen_resolutions = set()
                    
                    for video_format in video_formats:
                        resolution = video_format['resolution']
                        
                        # Skip duplicate resolutions
                        if resolution in seen_resolutions:
                            continue
                        
                        # Skip if resolution is invalid
                        if not resolution or resolution == 'audio only':
                            continue
                        
                        seen_resolutions.add(resolution)
                        
                        # Calculate total size (video + best audio)
                        total_size = video_format['filesize'] or 0
                        format_id = video_format['format_id']
                        
                        # If video doesn't have audio, add best audio format
                        if not video_format['has_audio'] and best_audio:
                            total_size += (best_audio['filesize'] or 0)
                            format_id = f"{video_format['format_id']}+{best_audio['format_id']}"
                        
                        # Skip if too large
                        if total_size > config.MAX_FILE_SIZE:
                            continue
                        
                        # Format resolution string
                        if video_format['fps'] and int(video_format['fps']) > 30:
                            resolution_str = f"{resolution} {video_format['fps']}fps"
                        else:
                            resolution_str = resolution
                        
                        resolution_options.append({
                            'format_id': format_id,
                            'resolution': resolution_str,
                            'size': self._format_size(total_size),
                            'filesize': total_size,
                            'fps': video_format['fps'],
                            'title': video_info['title'],
                            'duration': video_info['duration'],
                            'channel': video_info['channel'],
                            'thumbnail': video_info['thumbnail'],
                        })
                    
                    # Limit to reasonable number of options (max 8)
                    return resolution_options[:8]
            
            resolutions = await loop.run_in_executor(self.executor, extract_info)
            
            if not resolutions:
                # Fallback to best available format
                return [{
                    'format_id': config.YDL_FORMATS,
                    'resolution': 'Best available',
                    'size': 'Unknown',
                    'filesize': 0,
                    'fps': '',
                    'title': 'Video',
                    'duration': 'Unknown',
                    'channel': 'Unknown',
                    'thumbnail': None,
                }]
            
            return resolutions
            
        except Exception as e:
            logger.error(f"Error getting resolutions: {e}")
            return []
    
    async def download_video(
        self, 
        url: str, 
        format_id: str, 
        user_id: int,
        progress_callback: Optional[Callable[[float], None]] = None
    ) -> Optional[str]:
        """Download video with FFmpeg post-processing for merging"""
        try:
            loop = asyncio.get_event_loop()
            
            # Create progress tracking
            download_info = {
                'status': 'starting',
                'percent': 0,
                'speed': 0,
                'eta': 0,
                'filename': None
            }
            self.active_downloads[user_id] = download_info
            
            def progress_hook(d):
                if d['status'] == 'downloading':
                    total = d.get('total_bytes') or d.get('total_bytes_estimate')
                    downloaded = d.get('downloaded_bytes', 0)
                    
                    if total and total > 0:
                        percent = (downloaded / total) * 100
                        download_info['percent'] = percent
                        download_info['speed'] = d.get('speed', 0)
                        download_info['eta'] = d.get('eta', 0)
                        
                        if progress_callback:
                            loop.call_soon_threadsafe(progress_callback, percent)
                
                elif d['status'] == 'finished':
                    download_info['status'] = 'processing'
                    download_info['percent'] = 100
                    if progress_callback:
                        loop.call_soon_threadsafe(progress_callback, 100)
                
                elif d['status'] == 'postprocessing':
                    download_info['status'] = 'postprocessing'
            
            def download():
                opts = config.YDL_OPTS.copy()
                opts['progress_hooks'] = [progress_hook]
                opts['format'] = format_id
                opts['cookiefile'] = self.cookies_file  # Required
                
                # Generate safe filename
                safe_title = re.sub(r'[^\w\s-]', '', url.split('=')[-1] if '=' in url else url[-11:])
                opts['outtmpl'] = os.path.join(config.TEMP_DIR, f'{user_id}_{safe_title}.%(ext)s')
                
                # Ensure MP4 output with proper merging
                opts['merge_output_format'] = 'mp4'
                
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    filename = ydl.prepare_filename(info)
                    
                    # Ensure .mp4 extension
                    if not filename.endswith('.mp4'):
                        base, _ = os.path.splitext(filename)
                        mp4_file = base + '.mp4'
                        if os.path.exists(mp4_file):
                            filename = mp4_file
                    
                    download_info['filename'] = filename
                    return filename
            
            filename = await loop.run_in_executor(self.executor, download)
            
            # Remove from active downloads
            if user_id in self.active_downloads:
                del self.active_downloads[user_id]
            
            # Check file size
            if filename and os.path.exists(filename):
                file_size = os.path.getsize(filename)
                if file_size > config.MAX_FILE_SIZE:
                    logger.warning(f"File too large: {file_size} bytes")
                    os.remove(filename)
                    return None
            
            return filename
            
        except Exception as e:
            logger.error(f"Download error: {e}")
            if user_id in self.active_downloads:
                del self.active_downloads[user_id]
            return None
    
    def _is_compatible_format(self, format_info: Dict) -> bool:
        """Check if format is compatible (H.264 video, AAC/MP4A audio preferred)"""
        ext = format_info.get('ext', '').lower()
        vcodec = format_info.get('vcodec', '').lower()
        acodec = format_info.get('acodec', '').lower()
        
        # Only process formats with video or audio
        if vcodec == 'none' and acodec == 'none':
            return False
        
        # For video formats, require H.264
        if vcodec != 'none':
            if not any(codec in vcodec for codec in ['avc', 'h264', 'h.264']):
                return False
            
            # Prefer MP4 container for video
            if ext not in ['mp4', 'webm', 'mkv']:
                return False
        
        # For audio formats, prefer AAC/MP4A
        if acodec != 'none':
            # Accept any audio codec, but prefer AAC
            if not any(codec in acodec for codec in ['aac', 'mp4a', 'opus', 'vorbis', 'mp3']):
                return False
        
        return True
    
    def _format_size(self, size_bytes: int) -> str:
        """Format size in human readable format"""
        if not size_bytes or size_bytes <= 0:
            return "Unknown"
        
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} TB"
    
    def _parse_resolution(self, resolution_str: str) -> int:
        """Extract numeric resolution from string"""
        try:
            if not resolution_str or resolution_str == 'audio only':
                return 0
            
            # Extract resolution (e.g., "1920x1080" -> 1080, "1080p" -> 1080)
            match = re.search(r'(\d+)[xp]', resolution_str)
            if match:
                return int(match.group(1))
            
            # Try to find just numbers
            match = re.search(r'(\d+)', resolution_str)
            if match:
                return int(match.group(1))
            
            return 0
        except:
            return 0
    
    def cancel_download(self, user_id: int):
        """Cancel an active download"""
        if user_id in self.active_downloads:
            self.active_downloads[user_id]['status'] = 'cancelled'
            return True
        return False