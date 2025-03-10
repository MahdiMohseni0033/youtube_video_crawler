# YouTube Video Crawler

A lightweight, configurable tool that searches YouTube for videos based on custom queries and extracts detailed video information.

## Features

- Search YouTube videos using custom queries
- Extract comprehensive video metadata
- Configurable search parameters
- Flexible output formatting
- Robust error handling and logging

## Installation

### Prerequisites

- Python 3.8+

### Setup

1. Clone this repository:
   ```bash
   git clone https://github.com/yourusername/youtube-video-crawler.git
   cd youtube-video-crawler
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

Run the crawler with your search query:

```bash
# Basic usage
python youtube_crawler.py --query "data science"

# Custom number of videos
python youtube_crawler.py --query "artificial intelligence" --max-videos 15
```

## Configuration Options

| Parameter | Description | Default |
|-----------|-------------|---------|
| `search_query` | The search term to look for on YouTube | Required |
| `max_videos` | Maximum number of videos to retrieve | 5 |
| `output_format` | Format for saving results | "json" |
| `log_level` | Logging verbosity (DEBUG, INFO, WARNING, ERROR) | "INFO" |

## Output

The crawler generates a JSON file with detailed information about each video, including:

- Video ID and title
- Description
- Channel information
- View counts, likes, and comments
- Publication date
- Duration
- Tags
- Thumbnail URL

## Project Structure

```
youtube-video-crawler/
├── youtube_crawler.py   # Main crawler script
├── utils/               # Utility functions
├── requirements.txt     # Project dependencies
└── README.md            # Project documentation
```

## Author
This README was written by Mahdi Mohseni
Email: mahdimohseni0333@gmail.com