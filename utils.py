#!/usr/bin/env python3
"""
Utility functions for YouTube video crawling
"""

import re
import json
import logging
import requests
from typing import List, Dict, Any, Optional
from urllib.parse import quote
from bs4 import BeautifulSoup

# Constants
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
YOUTUBE_SEARCH_URL = 'https://www.youtube.com/results?search_query={}'
YOUTUBE_VIDEO_URL = 'https://www.youtube.com/watch?v={}'
YOUTUBE_BASE_URL = 'https://www.youtube.com'


def setup_logging(level: str = "INFO") -> None:
    """Configure logging for the application."""
    numeric_level = getattr(logging, level.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError(f"Invalid log level: {level}")
    
    logging.basicConfig(
        level=numeric_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )


def sanitize_filename(filename: str) -> str:
    """Remove special characters from filename."""
    return re.sub(r'[\\/*?:"<>|]', "", filename).replace(' ', '_')


def get_session() -> requests.Session:
    """Create and return a requests session with headers."""
    session = requests.Session()
    session.headers.update({
        'User-Agent': USER_AGENT,
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept': 'text/html,application/xhtml+xml,application/xml'
    })
    return session


def search_youtube_videos(query: str, max_results: int = 50) -> List[str]:
    """
    Search YouTube and extract video IDs.
    
    Args:
        query: Search query string
        max_results: Maximum number of video IDs to return
        
    Returns:
        List of YouTube video IDs
    """
    session = get_session()
    encoded_query = quote(query)
    url = YOUTUBE_SEARCH_URL.format(encoded_query)
    
    try:
        response = session.get(url)
        response.raise_for_status()
        
        # Extract video IDs using regex pattern
        video_ids = []
        pattern = r'\/watch\?v=([a-zA-Z0-9_-]{11})'
        matches = re.findall(pattern, response.text)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_ids = [x for x in matches if not (x in seen or seen.add(x))]
        
        return unique_ids[:max_results]
        
    except requests.RequestException as e:
        logging.error(f"Error during YouTube search: {str(e)}")
        return []


def extract_tags(soup: BeautifulSoup) -> List[str]:
    """Extract video tags from the video page."""
    tags = []
    
    # Method 1: Check meta keywords
    meta_keywords = soup.find('meta', attrs={'name': 'keywords'})
    if meta_keywords and meta_keywords.get('content'):
        tags = [tag.strip() for tag in meta_keywords.get('content').split(',')]
    
    # Method 2: Look for hashtags in description
    description_element = soup.select_one('meta[name="description"]')
    if description_element and description_element.get('content'):
        description = description_element.get('content')
        hashtags = re.findall(r'#\w+', description)
        for tag in hashtags:
            if tag not in tags:
                tags.append(tag)
    
    return tags


def extract_description(soup: BeautifulSoup) -> str:
    """Extract video description from the video page."""
    description_meta = soup.find('meta', attrs={'name': 'description'})
    if description_meta and description_meta.get('content'):
        return description_meta.get('content')
    return ""


def extract_video_resolutions(video_id: str) -> List[Dict[str, Any]]:
    """
    Extract available video resolutions and formats by parsing player response.
    
    Args:
        video_id: YouTube video ID
        
    Returns:
        List of dictionaries with resolution and format information
    """
    session = get_session()
    url = YOUTUBE_VIDEO_URL.format(video_id)
    
    try:
        response = session.get(url)
        response.raise_for_status()
        
        # Look for player_response in the page - more robust pattern
        player_response_pattern = r'ytInitialPlayerResponse\s*=\s*({.+?});(?:\s*var\s|\s*</script>)'
        matches = re.search(player_response_pattern, response.text, re.DOTALL)
        
        if not matches:
            # Try alternative pattern
            alt_pattern = r'ytInitialPlayerResponse\s*=\s*({.+?});'
            matches = re.search(alt_pattern, response.text, re.DOTALL)
            if not matches:
                logging.warning(f"Could not find player response for video {video_id}")
                return []
        
        try:
            # Extract just the JSON object without extra text
            json_text = matches.group(1)
            player_response = json.loads(json_text)
            formats = []
            
            # Check for streaming data
            streaming_data = player_response.get('streamingData', {})
            
            # Extract formats
            for format_type in ['formats', 'adaptiveFormats']:
                if format_type in streaming_data:
                    for fmt in streaming_data[format_type]:
                        format_info = {
                            'itag': fmt.get('itag'),
                            'mime_type': fmt.get('mimeType', '').split(';')[0] if fmt.get('mimeType') else 'unknown',
                            'quality': fmt.get('qualityLabel', fmt.get('quality', 'unknown'))
                        }
                        
                        # Add resolution info if available
                        if 'width' in fmt and 'height' in fmt:
                            format_info['resolution'] = f"{fmt['width']}x{fmt['height']}"
                        
                        formats.append(format_info)
            
            return formats
            
        except json.JSONDecodeError as e:
            # Use a more basic method if JSON parsing fails
            logging.warning(f"JSON parsing failed for {video_id}, trying simpler extraction method")
            
            # Try to extract resolution information from the page metadata
            soup = BeautifulSoup(response.text, 'html.parser')
            formats = []
            
            # Check for og:video dimensions
            og_video_width = soup.find('meta', property='og:video:width')
            og_video_height = soup.find('meta', property='og:video:height')
            
            if og_video_width and og_video_height:
                width = og_video_width.get('content')
                height = og_video_height.get('content')
                formats.append({
                    'resolution': f"{width}x{height}",
                    'quality': f"{height}p",
                    'mime_type': 'video/mp4',
                    'itag': 'unknown'
                })
            
            return formats
            
    except requests.RequestException as e:
        logging.error(f"Error fetching video formats for {video_id}: {str(e)}")
        return []

def get_video_details(video_id: str) -> Optional[Dict[str, Any]]:
    """
    Get detailed information about a YouTube video.
    
    Args:
        video_id: YouTube video ID
        
    Returns:
        Dictionary containing video details, or None if extraction fails
    """
    session = get_session()
    url = YOUTUBE_VIDEO_URL.format(video_id)
    
    try:
        response = session.get(url)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Extract basic video information
        title = ""
        title_meta = soup.find('meta', property='og:title')
        if title_meta:
            title = title_meta.get('content', '')
        
        # Extract video details
        description = extract_description(soup)
        tags = extract_tags(soup)
        
        # Extract upload date if available
        upload_date = ""
        date_meta = soup.find('meta', itemprop='datePublished')
        if date_meta:
            upload_date = date_meta.get('content', '')
        
        # Extract channel information
        channel_name = ""
        channel_url = ""
        channel_meta = soup.find('link', itemprop='name')
        if channel_meta:
            channel_name = channel_meta.get('content', '')
        
        channel_url_meta = soup.find('link', itemprop='url')
        if channel_url_meta:
            channel_url = channel_url_meta.get('href', '')
            if channel_url and not channel_url.startswith('http'):
                channel_url = YOUTUBE_BASE_URL + channel_url
        
        # Try to extract additional information from embedded JSON
        additional_info = {}
        for script in soup.find_all('script', type='application/ld+json'):
            try:
                if script.string:
                    json_data = json.loads(script.string)
                    if isinstance(json_data, dict) and json_data.get('@type') == 'VideoObject':
                        if 'uploadDate' in json_data and not upload_date:
                            upload_date = json_data['uploadDate']
                        if 'author' in json_data and isinstance(json_data['author'], dict):
                            if not channel_name and 'name' in json_data['author']:
                                channel_name = json_data['author']['name']
                        if 'interactionStatistic' in json_data:
                            for stat in json_data['interactionStatistic']:
                                if stat.get('@type') == 'InteractionCounter':
                                    if stat.get('interactionType') == 'http://schema.org/WatchAction':
                                        additional_info['view_count'] = stat.get('userInteractionCount')
                                    elif stat.get('interactionType') == 'http://schema.org/LikeAction':
                                        additional_info['like_count'] = stat.get('userInteractionCount')
            except (json.JSONDecodeError, AttributeError):
                pass
        
        # Get video duration if available
        duration = ""
        duration_meta = soup.find('meta', itemprop='duration')
        if duration_meta:
            duration = duration_meta.get('content', '')
        if duration:
            additional_info['duration'] = duration
        
        # Get thumbnail URL
        thumbnail_url = ""
        thumbnail_meta = soup.find('meta', property='og:image')
        if thumbnail_meta:
            thumbnail_url = thumbnail_meta.get('content', '')
        if thumbnail_url:
            additional_info['thumbnail_url'] = thumbnail_url
        
        # Extract video resolutions
        formats = extract_video_resolutions(video_id)
        
        # Get default resolution information from og:video if available
        if not formats:
            og_video_width = soup.find('meta', property='og:video:width')
            og_video_height = soup.find('meta', property='og:video:height')
            
            if og_video_width and og_video_height:
                width = og_video_width.get('content')
                height = og_video_height.get('content')
                formats.append({
                    'resolution': f"{width}x{height}",
                    'quality': f"{height}p",
                    'mime_type': 'video/mp4',
                    'itag': 'default'
                })
            
        video_info = {
            'video_id': video_id,
            'url': url,
            'title': title,
            'description': description,
            'tags': tags,
            'upload_date': upload_date,
            'channel': {
                'name': channel_name,
                'url': channel_url
            }
        }
        
        # Add formats only if we have any
        if formats:
            video_info['formats'] = formats
        
        # Add additional information if available
        if additional_info:
            video_info.update(additional_info)
        
        return video_info
        
    except requests.RequestException as e:
        logging.error(f"Error fetching video details for {video_id}: {str(e)}")
        return None