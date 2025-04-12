import logging
import configparser
from dataclasses import dataclass
from newsapi import NewsApiClient
from typing import Any
from newsapi.newsapi_exception import NewsAPIException
from news_embeddings import NewsVectorStore, preprocess_articles_for_vector_store, create_article_from_vector_result
from media_search import initialize_media_searcher

def configure_logger():
	logger_newsapi = logging.getLogger(__name__)
	logger_newsapi.setLevel(logging.DEBUG)
	stream_formatter = logging.Formatter(fmt='%(asctime)s - %(message)s', datefmt='%d-%b-%y %H:%M:%S')
	stream_handler = logging.StreamHandler()
	stream_handler.setFormatter(stream_formatter)
	logger_newsapi.addHandler(stream_handler)
	return logger_newsapi

@dataclass()
class Article:
    source_name: str
    author: str
    title: str
    description: str
    published: str
    url: str
    relevance_score: float = 0.0
    media: dict = None

    def __init__(self, source_name, author, title, description, published, url, relevance_score=0.0, media=None):
        self.source_name = source_name
        self.author = author
        self.title = title
        self.description = description
        self.published = published
        self.url = url
        self.relevance_score = relevance_score
        self.media = media or {}

    def __str__(self):
        msg = f'\N{hourglass}: '
        msg += f'{self._format_time()}\n'
        msg += f"\N{personal computer}Source: "
        msg += f'{self.source_name}\n'
        msg += f'\N{postal horn} Title: {self.title}\n'
        msg += f'\N{newspaper} Summary: {self.description}\n'
        msg += f'\N{link symbol}Original article: {self.url}\n'
        
        if self.media and (self.media.get('images') or self.media.get('videos')):
            msg += f'\N{camera} Related Media:\n'
            
        if self.media.get('images'):
                images = self.media['images']
                if images:
                    img = images[0]  
                    msg += f'  🖼️ Image: {img["url"]}\n'
            
        if self.media.get('videos'):
            videos = self.media['videos']
            if videos:
                vid = videos[0]  
                msg += f'  🎬 Video: {vid["title"]} - {vid["url"]}\n'
        
        if self.relevance_score > 0:
            msg += f'\N{chart with upwards trend} Relevance: {self.relevance_score:.2f}\n'
        return msg

    def _format_time(self):
        logging.debug(msg=f'changing time format {self.published}')
        if 'T' in self.published:
            date_published, time_published = self.published.split('T')
            return f'{date_published} - {time_published}'
        return self.published
	
class Aggregator:
    __slots__ = ['topics', 'newsapi', 'from_time', 'to_time', 'domains', 'vector_store', 'use_vector_db', 'max_results', 'media_searcher', 'enable_media']	
    topics: list[str]
    newsapi: NewsApiClient
    from_time: str
    to_time: str
    domains: str 
    vector_store: NewsVectorStore
    use_vector_db: bool
    max_results: int
    media_searcher: Any
    enable_media: bool
    aggregate_logger = configure_logger()
	
    def __init__(self, topics_of_interest, newsapi_key, from_time, to_time):
        config = configparser.ConfigParser()
        config.read("configuration.ini")
        configurations = config["NEWS"]
        logging.debug(msg=f"Creating Aggregator class")
        self.topics = topics_of_interest
        self.newsapi = NewsApiClient(api_key=newsapi_key)
        self.from_time = from_time
        self.to_time = to_time
        self.domains = self._define_domains(configurations)

        self.use_vector_db = configurations.get("use_vector_db", "true").lower() == "true"
        self.max_results = int(configurations.get("max_results", "3"))
		
        self.enable_media = configurations.get("enable_media", "true").lower() == "true"
        self.media_searcher = initialize_media_searcher() if self.enable_media else None
        self.vector_store = None 

        if self.use_vector_db:
            try:
                self.vector_store = NewsVectorStore(
					model_name=configurations.get("embedding_model", "all-MiniLM-L6-v2"),
					max_articles=int(configurations.get("max_stored_articles", "1000")),
                    similarity_threshold=float(configurations.get("similarity_threshold", "0.6"))
                )
                days_old = int(configurations.get("days_old", "4"))
                self.vector_store.filter_by_time(days_old)
            except Exception as e:
                self.aggregate_logger.error(f"Failed to initialize vector store: {e}")
                self.use_vector_db = False
				
    def _define_domains(self, configuration):
        domain_from_config_file = configuration['sources']
        return domain_from_config_file

    def _filter_articles(self, bundle_articles: dict, max_articles: int=3):
        filter_articles = bundle_articles['articles'][0:max_articles]
        return filter_articles

    def _parse_articles(self, bundle_articles: list, add_relevance: bool = False):
        parse_data = []
        for article in bundle_articles:
            media = {}
            if self.enable_media and self.media_searcher:
                try:
                    title = article['title']
                    description = article['description'] if article['description'] else ''
                    media = self.media_searcher.find_media_for_article(title, description)
                except Exception as e:
                    self.aggregate_logger.error(f"Error finding media for article: {e}")
            relevance_score = article.get('relevance_score', 0) if add_relevance else 0
            article_info = Article(
                source_name=article['source']['name'],
                author=article['author'] if article['author'] else 'Unknown',
                title=article['title'],
                description=article['description'] if article['description'] else 'No description available',
                published=article['publishedAt'],
                url=article['url'],
                relevance_score=relevance_score,
                media=media,
            )
            parse_data.append(article_info.__str__())
        return parse_data

    def fetch_articles(self, topic: str, specific_date: str = None):
        if specific_date:
            self.from_time = specific_date
            self.to_time = specific_date
        self.aggregate_logger.debug(msg=f'Fetching articles for topic {topic} from {self.from_time} to {self.to_time}')
        news_articles = []
        try:
            new = self.newsapi.get_everything(
                q=topic,
                from_param=self.from_time,
                to=self.to_time,
                domains=self.domains,
                language='en',
                sort_by='relevancy',
                page=1,
                page_size=20  
            )
            self.aggregate_logger.debug(msg=f'Fetching articles topic {topic} status: {new["status"]}')
            if self.use_vector_db and new["status"] == "ok":
                try:
                    preprocessed_articles = [
                        preprocess_articles_for_vector_store(article) 
                        for article in new['articles']
                    ]
                    self.vector_store.add_articles(preprocessed_articles)
                    
                    boost_domains = [domain.strip() for domain in self.domains.replace('"', '').split(',')]
                    vector_results = self.vector_store.hybrid_search(
                        query=topic, 
                        top_k=self.max_results,
                        boost_domains=boost_domains
                    )
                    if vector_results and len(vector_results) > 0:
                        article_format = [create_article_from_vector_result(result) for result in vector_results]
                        news_articles = self._parse_articles(article_format, add_relevance=True)
                        return news_articles
                except Exception as e:
                    self.aggregate_logger.error(f"Vector DB search failed: {e}")
            filtered_articles = self._filter_articles(new, self.max_results)
            news_articles = self._parse_articles(filtered_articles)
        except NewsAPIException as e:
            self.aggregate_logger.error(msg=f'error information \n{e}')
        except UnboundLocalError as e:
            self.aggregate_logger.error(msg=f'error {e}')
        return news_articles
    
    def get_news(self):
        list_articles = {}
        for topic in self.topics:
            news_articles = self.fetch_articles(topic=topic)
            list_articles[topic] = news_articles
        return list_articles
    
    def get_news_by_date(self, specific_date: str):
        list_articles = {}
        for topic in self.topics:
            news_articles = self.fetch_articles(topic=topic, specific_date=specific_date)
            list_articles[topic] = news_articles
        return list_articles
