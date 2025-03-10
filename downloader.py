#!/usr/bin/env python3
"""
YouTube Video Downloader using yt-dlp
This script downloads YouTube videos from a JSON file created by the crawler.
"""

import os
import json
import logging
import argparse
import subprocess
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

from tqdm import tqdm

from utils import setup_logging, sanitize_filename

# Check if yt-dlp is installed
try:
    import yt_dlp
    YTDLP_AVAILABLE = True
except ImportError:
    YTDLP_AVAILABLE = False

@dataclass
class DownloaderConfig:
    """Configuration for the YouTube downloader."""
    json_file: str
    output_dir: str = "downloads"
    resolution: str = "best"  # "best", "worst", or specific like "720"
    file_format: str = "mp4"
    limit: Optional[int] = None
    log_level: str = "INFO"
    use_ytdlp_lib: bool = True  # Use yt-dlp library (True) or command line (False)


def load_json(file_path: str) -> List[Dict[str, Any]]:
    """Load video data from JSON file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError) as e:
        logging.error(f"Error loading JSON file: {str(e)}")
        return []


def get_format_string(config: DownloaderConfig) -> str:
    """
    Get the yt-dlp format string based on configuration.
    
    Args:
        config: Downloader configuration
        
    Returns:
        Format string for yt-dlp
    """
    if config.resolution == "best":
        return f"bestvideo[ext={config.file_format}]+bestaudio/best[ext={config.file_format}]/best"
    elif config.resolution == "worst":
        return f"worstvideo[ext={config.file_format}]+worstaudio/worst[ext={config.file_format}]/worst"
    else:
        # Try to get specific resolution
        return f"bestvideo[height<={config.resolution}][ext={config.file_format}]+bestaudio/best[height<={config.resolution}][ext={config.file_format}]/best[height<={config.resolution}]"


def download_with_ytdlp_lib(video_info: Dict[str, Any], config: DownloaderConfig, output_path: str) -> bool:
    """
    Download a video using the yt-dlp library.
    
    Args:
        video_info: Dictionary containing video information
        config: Downloader configuration
        output_path: Full path where to save the video
        
    Returns:
        True if download successful, False otherwise
    """
    video_id = video_info.get('video_id')
    video_url = f"https://www.youtube.com/watch?v={video_id}"
    
    # Create progress hook for tqdm
    progress_bar = None
    
    def progress_hook(d):
        nonlocal progress_bar
        
        if d['status'] == 'downloading':
            if progress_bar is None and 'total_bytes' in d:
                # Initialize progress bar
                progress_bar = tqdm(
                    total=d['total_bytes'],
                    unit='B',
                    unit_scale=True,
                    desc=f"Downloading {video_info.get('title', video_id)[:30]}{'...' if len(video_info.get('title', '')) > 30 else ''}"
                )
            
            if progress_bar and 'downloaded_bytes' in d:
                # Update progress
                progress_bar.update(d['downloaded_bytes'] - progress_bar.n)
                
        elif d['status'] == 'finished' and progress_bar:
            progress_bar.close()
            logging.info(f"Download complete, now converting...")
    
    # Set up yt-dlp options
    format_string = get_format_string(config)
    ydl_opts = {
        'format': format_string,
        'outtmpl': output_path,
        'progress_hooks': [progress_hook],
        'quiet': True,
        'no_warnings': True
    }
    
    try:
        # Download the video
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=True)
            
            # Update video_info with the format that was downloaded
            if info:
                downloaded_format = {
                    'format_id': info.get('format_id', 'unknown'),
                    'resolution': f"{info.get('width', '?')}x{info.get('height', '?')}",
                    'quality': f"{info.get('height', '?')}p",
                    'downloaded': True
                }
                video_info['downloaded_format'] = downloaded_format
                
                logging.info(f"Downloaded video in format: {downloaded_format['resolution']}")
                
        return True
    except Exception as e:
        if progress_bar:
            progress_bar.close()
        logging.error(f"Error downloading video {video_id} with yt-dlp library: {str(e)}")
        return False


def download_with_ytdlp_cli(video_info: Dict[str, Any], config: DownloaderConfig, output_path: str) -> bool:
    """
    Download a video using the yt-dlp command line.
    
    Args:
        video_info: Dictionary containing video information
        config: Downloader configuration
        output_path: Full path where to save the video
        
    Returns:
        True if download successful, False otherwise
    """
    video_id = video_info.get('video_id')
    video_url = f"https://www.youtube.com/watch?v={video_id}"
    
    format_string = get_format_string(config)
    
    # Build the yt-dlp command
    cmd = [
        'yt-dlp',
        '-f', format_string,
        '-o', output_path,
        '--no-warnings',
        '--progress',
        video_url
    ]
    
    try:
        logging.info(f"Running yt-dlp command: {' '.join(cmd)}")
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True
        )
        
        print(f"Downloading {video_info.get('title', video_id)}")
        
        stdout, stderr = process.communicate()
        
        if process.returncode != 0:
            logging.error(f"yt-dlp error: {stderr}")
            return False
            
        logging.info(f"Successfully downloaded video using yt-dlp command line")
        
        # Try to extract format information from stdout/stderr
        resolution_match = None
        for line in stdout.split('\n') + stderr.split('\n'):
            if 'x' in line and ('p' in line or 'resolution' in line.lower()):
                # Try to find something like "1280x720" or "720p"
                import re
                res_pattern = r'(\d+x\d+|(\d+)p)'
                matches = re.findall(res_pattern, line)
                if matches:
                    resolution_match = matches[0][0]
                    break
                    
        # Update video_info with the format that was downloaded
        downloaded_format = {
            'format_id': 'yt-dlp_cli',
            'resolution': resolution_match or 'unknown',
            'downloaded': True
        }
        video_info['downloaded_format'] = downloaded_format
        
        return True
    except Exception as e:
        logging.error(f"Error running yt-dlp command for {video_id}: {str(e)}")
        return False


def check_ytdlp_available() -> bool:
    """Check if yt-dlp is available as a command line tool."""
    try:
        subprocess.run(['yt-dlp', '--version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return True
    except (subprocess.SubprocessError, FileNotFoundError):
        return False


def download_video(video_info: Dict[str, Any], config: DownloaderConfig) -> bool:
    """
    Download a single YouTube video.
    
    Args:
        video_info: Dictionary containing video information
        config: Downloader configuration
        
    Returns:
        True if download successful, False otherwise
    """
    video_id = video_info.get('video_id')
    if not video_id:
        logging.error("Video ID missing from video info")
        return False
    
    # Create output directory if it doesn't exist
    os.makedirs(config.output_dir, exist_ok=True)
    
    # Create a subdirectory for this channel
    channel_name = video_info.get('channel', {}).get('name', 'unknown_channel')
    channel_dir = sanitize_filename(channel_name)
    channel_path = os.path.join(config.output_dir, channel_dir)
    os.makedirs(channel_path, exist_ok=True)
    
    # Prepare filename
    title = video_info.get('title', video_id)
    filename = f"{sanitize_filename(title)}_{video_id}.{config.file_format}"
    output_path = os.path.join(channel_path, filename)
    
    # Check if file already exists
    if os.path.exists(output_path):
        logging.info(f"Video already downloaded: {output_path}")
        return True
    
    # Try to download with yt-dlp
    try:
        logging.info(f"Initializing download for video ID: {video_id}")
        
        # Determine download method
        ytdlp_cli_available = check_ytdlp_available()
        
        if config.use_ytdlp_lib and YTDLP_AVAILABLE:
            logging.info(f"Using yt-dlp library for download")
            success = download_with_ytdlp_lib(video_info, config, output_path)
        elif ytdlp_cli_available:
            logging.info(f"Using yt-dlp command line for download")
            success = download_with_ytdlp_cli(video_info, config, output_path)
        else:
            logging.error(f"yt-dlp is not available (neither as library nor command line)")
            return False
        
        if success:
            # Create metadata file
            metadata_path = os.path.join(channel_path, f"{sanitize_filename(title)}_{video_id}_info.json")
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(video_info, f, ensure_ascii=False, indent=2)
                
            logging.info(f"Successfully downloaded: {title}")
            return True
        else:
            logging.error(f"Failed to download video {video_id}")
            return False
            
    except Exception as e:
        logging.error(f"Error in download process for video {video_id}: {str(e)}")
        # Print traceback for debugging
        import traceback
        logging.error(traceback.format_exc())
        return False


def main(config: DownloaderConfig) -> None:
    """
    Main function to download videos from JSON file.
    
    Args:
        config: Downloader configuration
    """
    # Setup logging
    setup_logging(config.log_level)
    logger = logging.getLogger(__name__)
    
    logger.info(f"Starting YouTube downloader with configuration: {config}")
    
    # Check for yt-dlp
    if not YTDLP_AVAILABLE and not check_ytdlp_available():
        logger.error("yt-dlp is not available. Please install it with 'pip install yt-dlp' or as a system package.")
        return
    
    # Load video information from JSON file
    videos = load_json(config.json_file)
    if not videos:
        logger.error(f"No videos found in {config.json_file}")
        return
        
    logger.info(f"Loaded {len(videos)} videos from {config.json_file}")
    
    # Limit number of videos if specified
    if config.limit and config.limit > 0:
        videos = videos[:config.limit]
        logger.info(f"Limited to downloading {config.limit} videos")
    
    # Create output directory
    os.makedirs(config.output_dir, exist_ok=True)
    
    # Download videos
    successful = 0
    for i, video_info in enumerate(videos, 1):
        logger.info(f"Processing video {i}/{len(videos)}: {video_info.get('title', video_info.get('video_id', 'Unknown'))}")
        if download_video(video_info, config):
            successful += 1
    
    logger.info(f"Download complete. Successfully downloaded {successful}/{len(videos)} videos to {config.output_dir}")


if __name__ == "__main__":
    # parser = argparse.ArgumentParser(description="Download YouTube videos from a JSON file using yt-dlp")
    # parser.add_argument("json_file", help="Path to the JSON file containing video information")
    # parser.add_argument("--output-dir", "-o", default="downloads", help="Directory to save downloaded videos")
    # parser.add_argument("--resolution", "-r", default="best", help="Video resolution to download (best, worst, or specific like 720)")
    # parser.add_argument("--format", "-f", default="mp4", help="Video file format")
    # parser.add_argument("--limit", "-l", type=int, help="Limit the number of videos to download")
    # parser.add_argument("--log-level", default="INFO", help="Logging level")
    # parser.add_argument("--use-cli", action="store_true", help="Force use of yt-dlp command line even if library is available")
    
    # args = parser.parse_args()
    
    # config = DownloaderConfig(
    #     json_file=args.json_file,
    #     output_dir=args.output_dir,
    #     resolution=args.resolution,
    #     file_format=args.format,
    #     limit=args.limit,
    #     log_level=args.log_level,
    #     use_ytdlp_lib=not args.use_cli
    # )
    # from downloader import DownloaderConfig, main

    config = DownloaderConfig(
        json_file="youtube_results_a_cat_video.json",
        output_dir="cat_videos",
        resolution="1080",  # Download 720p or lower
        limit=5  # Download only 2 videos
    )


    
    main(config)