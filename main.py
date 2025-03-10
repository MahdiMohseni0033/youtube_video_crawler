#!/usr/bin/env python3
"""
YouTube Video Crawler
This script crawls YouTube for videos based on a search query and saves the results.
"""

import json
import logging
from typing import List
from dataclasses import dataclass

from utils import (
    setup_logging,
    search_youtube_videos,
    get_video_details,
    sanitize_filename
)

@dataclass
class CrawlerConfig:
    """Configuration for the YouTube crawler."""
    search_query: str
    max_videos: int = 5
    output_format: str = "json"
    log_level: str = "INFO"

def save_json(data: List[dict], filename: str) -> None:
    """Save data as JSON file."""
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def main(config: CrawlerConfig) -> None:
    """Main function to crawl YouTube videos."""
    # Setup logging
    setup_logging(config.log_level)
    logger = logging.getLogger(__name__)
    
    logger.info(f"Starting YouTube crawler for: '{config.search_query}'")
    
    # Search for videos
    logger.info(f"Searching for up to {config.max_videos} videos...")
    video_ids = search_youtube_videos(config.search_query, config.max_videos)
    logger.info(f"Found {len(video_ids)} video IDs")
    
    # Get detailed information for each video
    all_videos = []
    for i, video_id in enumerate(video_ids, 1):
        logger.info(f"Processing video {i}/{len(video_ids)}: {video_id}")
        try:
            video_info = get_video_details(video_id)
            if video_info:
                all_videos.append(video_info)
                logger.info(f"Successfully extracted details for video: {video_info.get('title', video_id)}")
            else:
                logger.warning(f"Couldn't extract details for video ID: {video_id}")
        except Exception as e:
            logger.error(f"Error processing video {video_id}: {str(e)}")
    
    # Save results
    sanitized_query = sanitize_filename(config.search_query)
    output_file = f"youtube_results_{sanitized_query}.json"
    save_json(all_videos, output_file)
    logger.info(f"Saved {len(all_videos)} video details to {output_file}")

if __name__ == "__main__":
    # Example usage
    config = CrawlerConfig(
        search_query="a cat video",
        max_videos=5
    )
    main(config)