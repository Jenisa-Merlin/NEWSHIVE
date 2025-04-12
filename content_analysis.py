import logging
from typing import List, Dict, Tuple
from collections import Counter
import nltk
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize, sent_tokenize

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(handler)

try:
    nltk.data.find('tokenizers/punkt')
    nltk.data.find('corpora/stopwords')
except LookupError:
    logger.info("Downloading NLTK resources")
    nltk.download('punkt')
    nltk.download('stopwords')

class ContentAnalyzer:
    def __init__(self, language='english'):
        self.language = language
        self.stop_words = set(stopwords.words(language))
        self.stop_words.update(['says', 'said', 'reuters', 'ap', 'afp', 'according'])
    
    def extract_keywords(self, text: str, top_n: int = 5) -> List[str]:
        if not text:
            return []
        words = word_tokenize(text.lower())
        words = [word for word in words if word.isalnum() and word not in self.stop_words and len(word) > 2]        
        word_freq = Counter(words)        
        return [word for word, _ in word_freq.most_common(top_n)]
    
    # def extract_topics(self, articles: List[Dict]) -> List[Tuple[str, float]]:
    #     all_text = []
    #     for article in articles:
    #         title = article.get('title', '')
    #         desc = article.get('description', '')
    #         content = article.get('content', '')
    #         all_text.append(f"{title} {desc} {content}")
    #     combined_text = " ".join(all_text)        
    #     keywords = self.extract_keywords(combined_text, top_n=10)        
    #     keyword_scores = []
    #     for keyword in keywords:
    #         count = 0
    #         for text in all_text:
    #             count += len(re.findall(r'\b' + re.escape(keyword) + r'\b', text.lower()))            
    #         score = count / max(1, len(articles))
    #         keyword_scores.append((keyword, score))        
    #     keyword_scores.sort(key=lambda x: x[1], reverse=True)
    #     return keyword_scores
    
    def extract_topics(self, articles: List[Dict]) -> List[Tuple[str, float]]:
        # Combine all text with higher weight on titles
        title_text = []
        description_text = []
        content_text = []
        
        for article in articles:
            title = article.get('title', '')
            desc = article.get('description', '')
            content = article.get('content', '')
            
            if title:
                title_text.append(title)
            if desc:
                description_text.append(desc)
            if content:
                content_text.append(content)
        
        # Extract keywords from each section with different weights
        title_keywords = self._extract_keywords_from_texts(title_text, weight=3.0)
        desc_keywords = self._extract_keywords_from_texts(description_text, weight=1.5)
        content_keywords = self._extract_keywords_from_texts(content_text, weight=1.0)
        
        # Combine scores from different sources
        combined_scores = {}
        for keyword, score in title_keywords + desc_keywords + content_keywords:
            if keyword in combined_scores:
                combined_scores[keyword] += score
            else:
                combined_scores[keyword] = score
        
        # Return sorted topics
        sorted_topics = sorted(combined_scores.items(), key=lambda x: x[1], reverse=True)
        return sorted_topics[:10]

    def _extract_keywords_from_texts(self, texts: List[str], weight: float = 1.0) -> List[Tuple[str, float]]:
        if not texts:
            return []
        
        combined_text = " ".join(texts)
        words = word_tokenize(combined_text.lower())
        # Filter more strictly
        filtered_words = [word for word in words if 
                        word.isalnum() and 
                        word not in self.stop_words and 
                        len(word) > 3]  # Longer words are often more meaningful
        
        # Consider bigrams for multi-word topics
        bigrams = list(nltk.bigrams(filtered_words))
        bigram_phrases = [f"{w1}_{w2}" for w1, w2 in bigrams]
        
        # Count occurrences
        word_freq = Counter(filtered_words)
        bigram_freq = Counter(bigram_phrases)
        
        # Weight scores
        word_scores = [(word, count * weight / max(1, len(texts))) for word, count in word_freq.most_common(20)]
        bigram_scores = [(bigram.replace('_', ' '), count * weight * 1.5 / max(1, len(texts))) 
                        for bigram, count in bigram_freq.most_common(10)]
        
        # Combine single words and bigrams
        all_scores = word_scores + bigram_scores
        all_scores.sort(key=lambda x: x[1], reverse=True)
        
        return all_scores[:20]
    def summarize_text(self, text: str, max_sentences: int = 3) -> str:
        if not text or len(text) < 100:
            return text  
        try:
            sentences = sent_tokenize(text)
            if len(sentences) <= max_sentences:
                return text
            word_freq = Counter()
            for sentence in sentences:
                words = word_tokenize(sentence.lower())
                words = [word for word in words if word.isalnum() and word not in self.stop_words]
                word_freq.update(words)                
            sentence_scores = []
            for i, sentence in enumerate(sentences):
                words = word_tokenize(sentence.lower())
                words = [word for word in words if word.isalnum()]                
                score = sum(word_freq.get(word, 0) for word in words) / max(1, len(words))
                sentence_scores.append((i, score))                
            top_indices = sorted([idx for idx, _ in sorted(sentence_scores, key=lambda x: x[1], reverse=True)[:max_sentences]])
            summary = " ".join([sentences[idx] for idx in top_indices])
            return summary
        except Exception as e:
            logger.error(f"Error summarizing text: {e}")
            return text[:200] + "..." if len(text) > 200 else text
    
    def categorize_sentiment(self, text: str) -> str:
        positive_words = {'up', 'rise', 'gain', 'growth', 'positive', 'bullish', 'increase', 'higher', 'success', 'improve'}
        negative_words = {'down', 'fall', 'drop', 'decline', 'negative', 'bearish', 'decrease', 'lower', 'fail', 'worse'}
        text = text.lower()
        words = word_tokenize(text)
        positive_count = sum(1 for word in words if word in positive_words)
        negative_count = sum(1 for word in words if word in negative_words)        
        negations = {'not', 'no', "n't", 'never', 'without'}
        for i, word in enumerate(words[:-1]):
            if word in negations:
                next_word = words[i+1]
                if next_word in positive_words:
                    positive_count -= 1
                    negative_count += 1
                elif next_word in negative_words:
                    negative_count -= 1
                    positive_count += 1        
        if positive_count > negative_count:
            return "positive"
        elif negative_count > positive_count:
            return "negative"
        else:
            return "neutral"

def enhance_article_summaries(articles: List[Dict]) -> List[Dict]:
    analyzer = ContentAnalyzer()    
    for article in articles:
        text = f"{article.get('title', '')} {article.get('description', '')}"
        article['keywords'] = analyzer.extract_keywords(text)
        article['sentiment'] = analyzer.categorize_sentiment(text)
        description = article.get('description', '')
        if description and len(description) > 300:
            article['description'] = analyzer.summarize_text(description, max_sentences=2)
    return articles

