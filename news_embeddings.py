import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
import numpy as np
from sentence_transformers import SentenceTransformer
import os
import pickle 
from datetime import datetime

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
stream_handler = logging.StreamHandler()
formatter = logging.Formatter(fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s', datefmt='%d-%b-%y %H:%M:%S')
stream_handler.setFormatter(formatter)
logger.addHandler(stream_handler)

@dataclass
class NewsVectorStore:
    model_name: str = "all-MiniLM-L6-v2"
    embedding_dim: int = None  
    cache_dir: str = "/embeddings_cache"
    max_articles: int = 1000
    similarity_threshold: float = 0.6
    articles: List[Dict] = field(default_factory=list)
    embeddings: Optional[np.ndarray] = None
    model: Any = None

    def __post_init__(self):
        logger.info(f"Initializing vector store with model: {self.model_name}")
        try:
            self.model = SentenceTransformer(self.model_name)
            self.embedding_dim = self.model.get_sentence_embedding_dimension()
            logger.info(f"Model loaded successfully with embedding dimension: {self.embedding_dim}")
        except Exception as e:
            logger.error(f"Error loading model: {e}")
            raise ValueError(f"Error loading model loading model: {str(e)}")
        try:
            if not os.path.exists(self.cache_dir):
                os.makedirs(self.cache_dir)
                logger.info(f"Created cache directory: {self.cache_dir}")
        except Exception as e:
            logger.error(f"Error creating cache directory: {e}")
            self.cache_dir = "."
            logger.info(f"Using current directory as fallback cache")
        try:
            self._load_cached_data()
        except Exception as e:
            logger.error(f"Error loading cached data: {e}")
            logger.info("Initializing with empty vectors")
            self.articles = []
            self.embeddings = None

    def _load_cached_data(self):
        cache_file = os.path.join(self.cache_dir, "news_vectors.pkl")
        if os.path.exists(cache_file):
            logger.info(f"Loading cached data from {cache_file}")
            try:
                with open(cache_file, "rb") as f:
                    cached_data = pickle.load(f)
                    self.articles = cached_data.get("articles", [])
                    self.embeddings = cached_data.get("embeddings", None)
                    logger.info(f"Loaded {len(self.articles)} articles and {self.embeddings.shape[0]} embeddings")
            except Exception as e:
                logger.error(f"Error loading cached data: {e}")
                self.articles = []
                self.embeddings = None

    def _save_cached_data(self):
        cache_file = os.path.join(self.cache_dir, "news_vectors.pkl")
        logger.info(f"Saving data to cache file: {cache_file}")
        try:
            with open(cache_file, "wb") as f:
                pickle.dump({"articles": self.articles, "embeddings": self.embeddings}, f)
            logger.info(f"Saved {len(self.articles)} articles and {self.embeddings.shape[0]} embeddings")
        except Exception as e:
            logger.error(f"Error saving cached data: {e}")

    def add_articles(self, news_articles: List[Dict]):
        if not news_articles:
            return
        logger.info(f"Adding {len(news_articles)} articles to store")
        texts = []
        for article in news_articles:
            combined_text = article.get("title", "") + " " + article.get("description", "")
            texts.append(combined_text)
        try:
            new_embeddings = self.model.encode(texts)
            if self.embeddings is None:
                self.embeddings = new_embeddings
                self.articles = news_articles
            else:
                unique_articles = []
                unique_embeddings = []
                for i, new_embedding in enumerate(new_embeddings):
                    if len(self.embeddings) > 0:
                        similarities = np.dot(self.embeddings, new_embedding) / (np.linalg.norm(self.embeddings, axis=1) * np.linalg.norm(new_embedding))
                        max_similarity = np.max(similarities)

                        if max_similarity < self.similarity_threshold:
                            unique_articles.append(news_articles[i])
                            unique_embeddings.append(new_embedding)
                    else:
                        unique_articles.append(news_articles[i])
                        unique_embeddings.append(new_embedding)
                if len(unique_articles) > 0:
                    self.articles.extend(unique_articles)
                    self.embeddings = np.vstack([self.embeddings, unique_embeddings])
                    if len(self.articles) > self.max_articles:
                        self.articles = self.articles[-self.max_articles:]
                        self.embeddings = self.embeddings[-self.max_articles:]
            logger.info(f"Total articles in store: {len(self.articles)}")
            self._save_cached_data()
        except Exception as e:
            logger.error(f"Error adding articles to store: {e}")

    def semantic_search(self, query: str, top_k: int = 3) -> List[Dict]:
        if not self.articles or self.embeddings is None:
            logger.warning("No articles in store. Please add articles before searching.")
            return []
        try:
            query_embedding = self.model.encode(query)
            similarities = np.dot(self.embeddings, query_embedding) / (np.linalg.norm(self.embeddings, axis=1) * np.linalg.norm(query_embedding))
            top_indices = np.argsort(similarities)[::-1][:top_k]
            results = []
            for idx in top_indices:
                article = self.articles[idx].copy()
                article["similarity_score"] = float(similarities[idx])  
                results.append(article)
            return results
        except Exception as e:
            logger.error(f"Error searching articles: {e}")
            return []
    
    def filter_by_time(self, days:int) -> None:
        if not self.articles:
            return
        current_time = datetime.now()
        filtered_indices = []
        for i, article in enumerate(self.articles):
            published_at = article.get("publishedAt", "")
            if published_at:
                try:
                    if 'T' in published_at:
                        pub_date = datetime.strptime(published_at.split('T')[0], '%Y-%m-%d')
                    else:
                        pub_date = datetime.strptime(published_at, '%Y-%m-%d') 
                    delta = (current_time - pub_date).days
                    if delta <= days:
                        filtered_indices.append(i)
                except Exception as e:
                    logger.warning(f"Failed too parse data {published_at}: {e}")
                    filtered_indices.append(i)
            else:
                filtered_indices.append(i)
        if filtered_indices:
            self.articles = [self.articles[i] for i in filtered_indices]
            self.embeddings = self.embeddings[filtered_indices]
            logger.info(f"Filtered vector store to {len(self.articles)} articles within {days} days")
            self._save_cached_data()

    # def hybrid_search(self, query:str, boost_domains: List[str], top_k:int=3) -> List[Dict]:
    #     semantic_results = self.semantic_search(query, top_k=min(top_k * 2, len(self.articles)))
    #     if boost_domains:
    #         for result in semantic_results:
    #             source_domain = result.get("source", {}).get("name", "").lower()
    #             if any(domain.lower() in source_domain for domain in boost_domains):
    #                 result["similarity_score"] *= 1.2 
    #     semantic_results.sort(key=lambda x: x["similarity_score"], reverse=True)
    #     return semantic_results[:top_k]

    def hybrid_search(self, query:str, boost_domains: List[str], top_k:int=3) -> List[Dict]:
        semantic_results = self.semantic_search(query, top_k=min(top_k * 3, len(self.articles)))        
        for result in semantic_results:
            source_domain = result.get("source", {}).get("name", "").lower()
            if any(domain.lower() == source_domain for domain in boost_domains):
                result["similarity_score"] *= 1.5
            elif any(domain.lower() in source_domain for domain in boost_domains):
                result["similarity_score"] *= 1.2
            desc_length = len(result.get("description", ""))
            if desc_length > 200:
                result["similarity_score"] *= 1.1
            if result.get("publishedAt"):
                try:
                    pub_date = datetime.strptime(result["publishedAt"].split('T')[0], '%Y-%m-%d')
                    days_old = (datetime.now() - pub_date).days
                    if days_old <= 1:  # Very recent news
                        result["similarity_score"] *= 1.3
                    elif days_old <= 3:  # Recent news
                        result["similarity_score"] *= 1.15
                except Exception:
                    pass
        semantic_results.sort(key=lambda x: x["similarity_score"], reverse=True)
        return semantic_results[:top_k]
        
def preprocess_articles_for_vector_store(article: Dict) -> Dict:
    return {
        'source': article.get('source', {}),
        'author': article.get('author', ''),
        'title': article.get('title', ''),
        'description': article.get('description', ''),
        'url': article.get('url', ''),
        'publishedAt': article.get('publishedAt', ''),
        'content': article.get('content', '')
    }

def create_article_from_vector_result(result: Dict) -> Dict:
    return {
        'source': {'name': result.get('source', {}).get('name', 'Unknown')},
        'author': result.get('author', 'Unknown'),
        'title': result.get('title', ''),
        'description': result.get('description', ''),
        'url': result.get('url', ''),
        'publishedAt': result.get('publishedAt', ''),
        'relevance_score': result.get('similarity_score', 0)
    }