import logging
import requests
import os
import re
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(handler)

class MediaSearcher:
    def __init__(self, pixabay_api_key: Optional[str] = None, youtube_api_key: Optional[str] = None):
        self.pixabay_api_key = pixabay_api_key or os.environ.get('PIXABAY_API_KEY', '')
        self.youtube_api_key = youtube_api_key or os.environ.get('YOUTUBE_API_KEY', '')
        
    def extract_search_terms(self, title: str, description: str) -> List[str]:
        text = f"{title} {description}"        
        text = re.sub(r'[^\w\s]', ' ', text.lower())        
        stop_words = {'a', 'an', 'the', 'and', 'or', 'but', 'is', 'are', 'was', 'were', 
                     'in', 'on', 'at', 'to', 'for', 'with', 'by', 'about', 'like', 
                     'through', 'over', 'before', 'after', 'between', 'after', 'says', 'said'}
        words = [word for word in text.split() if word not in stop_words and len(word) > 2]        
        common_news_terms = {'news', 'report', 'breaking', 'latest', 'update', 'reported', 'according'}
        word_freq = {}
        for word in words:
            if word not in common_news_terms:
                word_freq[word] = word_freq.get(word, 0) + 1        
        sorted_terms = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
        return [term for term, _ in sorted_terms[:3]]
    
    def search_images(self, query: str, max_results: int = 3) -> List[Dict]:
        if not self.pixabay_api_key:
            logger.warning("No Pixabay API key provided, cannot search for images")
            return []
        try:
            url = "https://pixabay.com/api/"
            params = {
                "key": self.pixabay_api_key,
                "q": query,
                "image_type": "photo",
                "per_page": max_results
            }
            response = requests.get(url, params=params)
            if response.status_code == 200:
                data = response.json()
                return [
                    {
                        "url": item["webformatURL"],
                        "source": "Pixabay",
                        "source_url": item["pageURL"],
                        "thumbnail": item["previewURL"]
                    }
                    for item in data.get("hits", [])[:max_results]
                ]
            else:
                logger.error(f"Failed to get images: {response.status_code}")
                return []
        except Exception as e:
            logger.error(f"Error searching for images: {e}")
            return []
    
    def search_videos(self, query: str, max_results: int = 2) -> List[Dict]:
        if not self.youtube_api_key:
            logger.warning("No YouTube API key provided, cannot search for videos")
            return []
        try:
            url = "https://www.googleapis.com/youtube/v3/search"
            params = {
                "key": self.youtube_api_key,
                "q": query,
                "part": "snippet",
                "type": "video",
                "maxResults": max_results
            }
            response = requests.get(url, params=params)
            if response.status_code == 200:
                data = response.json()
                return [
                    {
                        "title": item["snippet"]["title"],
                        "url": f"https://www.youtube.com/watch?v={item['id']['videoId']}",
                        "thumbnail": item["snippet"]["thumbnails"]["default"]["url"],
                        "source": "YouTube"
                    }
                    for item in data.get("items", [])[:max_results]
                ]
            else:
                logger.error(f"Failed to get videos: {response.status_code}")
                return []
        except Exception as e:
            logger.error(f"Error searching for videos: {e}")
            return []
            
    # def find_media_for_article(self, title: str, description: str) -> Dict[str, List]:
    #     search_terms = self.extract_search_terms(title, description)
    #     if not search_terms:
    #         return {"images": [], "videos": []}
    #     query = " ".join(search_terms[:2])        
    #     images = self.search_images(query)
    #     videos = self.search_videos(query)
    #     return {
    #         "images": images,
    #         "videos": videos,
    #         "search_terms": search_terms
    #     }

    def find_media_for_article(self, title: str, description: str) -> Dict[str, List]:
        search_terms = self.extract_search_terms(title, description)
        if not search_terms:
            return {"images": [], "videos": []}
        
        query = " ".join(search_terms[:2])
        
        # Try to get images with fallback
        images = []
        try:
            images = self.search_images(query)
            if not images and len(search_terms) > 2:
                # Try alternative terms if first search failed
                alt_query = " ".join([search_terms[0], search_terms[2]])
                images = self.search_images(alt_query)
        except Exception as e:
            logger.error(f"Error searching images: {e}")
        
        # Try to get videos with fallback
        videos = []
        try:
            videos = self.search_videos(query)
            if not videos and len(search_terms) > 2:
                alt_query = " ".join([search_terms[0], search_terms[2]])
                videos = self.search_videos(alt_query)
        except Exception as e:
            logger.error(f"Error searching videos: {e}")
        
        return {
            "images": images,
            "videos": videos,
            "search_terms": search_terms
        }
    
def initialize_media_searcher() -> MediaSearcher:
    pixabay_key = os.environ.get('PIXABAY_API_KEY', '')
    youtube_key = os.environ.get('YOUTUBE_API_KEY', '')
    if not pixabay_key:
        logger.warning("PIXABAY_API_KEY not found in environment variables")
    if not youtube_key:
        logger.warning("YOUTUBE_API_KEY not found in environment variables")
    return MediaSearcher(pixabay_api_key=pixabay_key, youtube_api_key=youtube_key)
