from content_analysis import ContentAnalyzer
from news_embeddings import create_article_from_vector_result
from news import Article  
import utilities
from news import Aggregator
import os
import telebot
from telebot import types
import logging
import re
from gsheet import fetch_service, create_spreadsheet, write_single
import configparser
from datetime import datetime
from dotenv import load_dotenv

def configure_logger():
	global logger
	logger = logging.getLogger(__name__)
	logger.setLevel(logging.DEBUG)
	stream_formatter = logging.Formatter(
						fmt='%(asctime)s - %(message)s',
						datefmt='%d-%b-%y %H:%M:%S')
	stream_handler = logging.StreamHandler()
	stream_handler.setFormatter(stream_formatter)
	logger.addHandler(stream_handler)

bot = telebot.TeleBot(token=os.environ['BOTAPIKEY'])

class MainFilter(telebot.custom_filters.AdvancedCustomFilter):
	key = 'text'
	@staticmethod
	def check(message, text):
		logger.debug(f'message comes from the message {message.text} and text come from the decorator {text}')
		return message.text in text

@bot.message_handler(commands=['start', 'help', 'settings'])
def send_welcome(message):
	welcome_message = """
            👋 *Welcome to NewsHive - News Aggregator Bot!*

            You can fetch the latest news, explore trends, and even save articles to Google Sheets. Here's what you can do:

            ---

            📰 *News Commands*:
            /news or just type *News [keyword]* - Get the latest 3 articles on a topic  
            /semantic [query] - Semantic search for more relevant results  
            /news_by_date [YYYY-MM-DD] [keyword] - Fetch news from a specific date  
            /news_with_media [keyword] - News results with attached media  
            /media [keyword] - View image and video gallery for a topic  

            ---

            ⚙️ *Configuration & Options*:
            /options - Show configuration menu  
            /domains - View or update allowed news domains  
            /timeframe - View or set how many days back to fetch news  

            ---

            📄 *Google Sheets Integration*:
            /save_to_sheets [keyword] - Save recent articles to Google Sheets  
            /export_daily - Export today's news for configured topics  

            ---

            Use these commands anytime or simply type your topic as:
            `News climate change` or `Semantic AI breakthroughs`

            Need help again? Just type */help* or */settings*.
            """
	bot.reply_to(message, welcome_message)

def verify_key(message):
	logger.debug(msg=f'string receive: {message.text}')
	text = message.text.split()
	tag, key_word = text[0].lower(), " ".join(text[1:])
	if tag in ('news', 'News') and len(key_word) > 1:
		return True

def bot_create_msg(message, news):
	for new in news:
		logger.debug(msg=f'Sending message with {new}')
		bot.send_message(message.chat.id, new, disable_web_page_preview=True)

@bot.message_handler(commands=['news', 'News'])
@bot.message_handler(func=verify_key)
def bot_get_news(message):
    text = message.text.split()
    _, key_words = text[0], text[1:]
    today, older = utilities.get_timeframe()
    news = Aggregator(
        topics_of_interest=key_words,
        newsapi_key=os.environ['NEWS_API'],
        from_time=older,
        to_time=today
    )
    msg = news.get_news()
    logger.debug(msg=f"getting the news: \n{msg}")
    if len(key_words) > 1:
        analyzer = ContentAnalyzer()
        try:
            all_articles_dict = []
            for topic, articles_list in msg.items():
                for article_str in articles_list:
                    title = ""
                    description = ""                    
                    title_match = re.search(r'\N{postal horn} Title: (.*?)\n', article_str)
                    if title_match:
                        title = title_match.group(1)
                    desc_match = re.search(r'\N{newspaper} Summary: (.*?)\n', article_str)
                    if desc_match:
                        description = desc_match.group(1)
                    all_articles_dict.append({
                        "title": title,
                        "description": description,
                        "content": ""  
                    })                
            if len(all_articles_dict) >= 3:
                bot.send_message(message.chat.id, "🔍 TRENDING TOPICS")
                topics = analyzer.extract_topics(all_articles_dict)
                topics_str = ", ".join([f"#{topic}" for topic, _ in topics[:5]])
                bot.send_message(message.chat.id, topics_str)
        except Exception as e:
            logger.error(f"Error analyzing trending topics: {e}")
        
    for topics, news in msg.items():
        bot.send_message(message.chat.id, topics.replace(',', '').upper())
        bot_create_msg(message=message, news=news)

def options_screen() -> types.ReplyKeyboardMarkup:
	markup = types.ReplyKeyboardMarkup(row_width=2, one_time_keyboard=True)
	options_domains = types.KeyboardButton('Domains')
	options_old_articles = types.KeyboardButton('Timeframe')
	options_add_domains = types.KeyboardButton('Add Domains')
	markup.add(options_domains, options_old_articles, options_add_domains)
	return markup

@bot.message_handler(text=['options', 'Options', 'option', 'Option'])
@bot.message_handler(commands=['options', 'Options'])
def bot_options(message):
	markup = options_screen()
	bot.send_message(chat_id=message.chat.id, text="These are your options:", reply_markup=markup)
	bot.register_next_step_handler(message=message,callback=select_options)

@bot.message_handler(commands=['semantic'])
def semantic_search(message):
    text = message.text.split(' ', 1)
    if len(text) < 2:
        bot.reply_to(message, "Please provide a search query after /semantic")
        return
    query = text[1]
    today, older = utilities.get_timeframe()    
    news = Aggregator(
        topics_of_interest=[query],
        newsapi_key=os.environ['NEWS_API'],
        from_time=older,
        to_time=today
    )
    if not news.use_vector_db:
        bot.reply_to(message, "Vector database is disabled in configuration. Semantic search unavailable.")
        return 
    try:
        results = news.vector_store.semantic_search(query, top_k=5)
        if not results:
            bot.reply_to(message, f"No semantic results found for: {query}")
            return
        bot.send_message(message.chat.id, f"🔍 SEMANTIC SEARCH: {query}")
        for result in results:
            article = create_article_from_vector_result(result)
            article_obj = Article(
                source_name=article['source']['name'],
                author=article['author'],
                title=article['title'],
                description=article['description'],
                published=article['publishedAt'],
                url=article['url'],
                relevance_score=article['relevance_score']
            )
            bot.send_message(message.chat.id, article_obj.__str__(), disable_web_page_preview=True)
    except Exception as e:
        logger.error(f"Error in semantic search: {e}")
        bot.reply_to(message, f"Error performing semantic search: {str(e)}")
		
def select_options(message):
	if message.text in "Domains":
		get_domain(message)
	elif message.text in "Add Domains":
		request_new_domains(message)
	elif message.text in "Timeframe":
		prepare_time_frame(message)

@bot.message_handler(commands=['domains', 'domain', 'Domains', 'Domain'])
def get_domain(message):
	domains_or_sources = utilities.read_configuration_file("sources").replace('"', '')
	bot.send_message(message.chat.id, domains_or_sources)

def request_new_domains(message):
	explanation_text = "Add new domain(s) (example of domain forbes.com) more than one domains? use commas."
	bot.send_message(chat_id=message.chat.id, text=explanation_text)
	bot.register_next_step_handler(message=message, callback=prepare_new_domain)

def prepare_new_domain(message):
	domains_to_add,  incorrect_domains = utilities.prepare_new_domains_to_add(message=message)
	list_domains_to_add = ', '.join(domains_to_add)
	bot.send_message(chat_id=message.chat.id, text=f"added domain(s)\n{list_domains_to_add}")
	if len(incorrect_domains) > 0:
		bot.send_message(chat_id=message.chat.id,text=f"domain(s) not added\n{', '.join(incorrect_domains)}")
	utilities.save_configuration_file(config_key="sources", value=list_domains_to_add)

def is_date_change() -> types.ReplyKeyboardMarkup:
	markup = types.ReplyKeyboardMarkup(row_width=2, one_time_keyboard=True)
	options_yes = types.KeyboardButton('YES')
	options_no = types.KeyboardButton('NO')
	markup.add(options_yes, options_no)
	return markup

@bot.message_handler(commands=['timeframe', 'Timeframe'])
def prepare_time_frame(message):
	days_old = utilities.read_configuration_file('days_old')
	explanation_text = f"bot search maximum of {days_old} days old news.\ndo you want to change this number?"
	markup = is_date_change()
	bot.send_message(chat_id=message.chat.id, text=explanation_text, reply_markup=markup)
	bot.register_next_step_handler(message=message, callback=input_date)

def input_date(message):
	if message.text in 'YES':
		bot.send_message(chat_id=message.chat.id, text="input the number")
		bot.register_next_step_handler(message=message, callback=change_number)
	else:
		bot.send_message(chat_id=message.chat.id, text="/start")

def change_number(message):
	new_date = message.text.strip()
	original_message = message.message_id
	if not new_date.isdigit():
		print(f'it is not a digit {new_date}')
		bot.send_message(chat_id=message.chat.id, text=f"{new_date} is not a number", reply_to_message_id=original_message)
		bot.send_message(chat_id=message.chat.id, text="Try again, input a number", reply_to_message_id=original_message)
		bot.register_next_step_handler(message=message, callback=change_number)
	utilities.save_configuration_file(config_key='days_old',value=new_date)
	bot.send_message(chat_id=message.chat.id, text=f"{new_date} days set.")
	bot.send_message(chat_id=message.chat.id, text="/start")
	bot.register_next_step_handler(message=message, callback=send_welcome)

bot.add_custom_filter(MainFilter())

@bot.message_handler(commands=['news_by_date'])
def bot_get_news_by_date(message):
    text = message.text.split(' ', 2) 
    if len(text) < 3:
        bot.reply_to(message, "❌ Please provide a date (YYYY-MM-DD) and a keyword.\nExample: /news_by_date 2025-03-25 AI")
        return
    input_date, keyword = text[1], " ".join(text[2:])  
    try:
        user_date = datetime.strptime(input_date, "%Y-%m-%d").date()
    except ValueError:
        bot.reply_to(message, "❌ Invalid date format! Use YYYY-MM-DD.\nExample: /news_by_date 2025-03-25 AI")
        return
    news = Aggregator(
        topics_of_interest=[keyword],
        newsapi_key=os.environ['NEWS_API'],
        from_time=user_date,
        to_time=user_date  
    )
    msg = news.get_news_by_date(user_date)
    logger.debug(msg=f"News for {user_date}: \n{msg}")
    if not msg:
        bot.reply_to(message, f"No news found for {keyword} on {user_date}.")
    else:
        bot.send_message(message.chat.id, f"📰 News for {keyword} on {user_date}:")
        bot_create_msg(message=message, news=msg.get(keyword, []))

@bot.message_handler(commands=['media'])
def show_media_gallery(message):
    text = message.text.split(' ', 1)
    if len(text) < 2:
        bot.reply_to(message, "Please provide a keyword after /media command.\nExample: /media Ukraine")
        return
    keyword = text[1]
    today, older = utilities.get_timeframe()
    news = Aggregator(
        topics_of_interest=[keyword],
        newsapi_key=os.environ['NEWS_API'],
        from_time=older,
        to_time=today
    )
    if not news.enable_media:
        bot.reply_to(message, "Media search is currently disabled. Enable it in configuration.ini")
        return
    articles = news.get_news()[keyword]
    if not articles:
        bot.reply_to(message, f"No news found for: {keyword}")
        return
    bot.send_message(message.chat.id, f"🖼️ MEDIA GALLERY FOR: {keyword.upper()}")
    for article_str in articles:
        img_match = re.search(r'🖼️ Image: (https?://\S+)', article_str)
        vid_match = re.search(r'🎬 Video: .+? - (https?://\S+)', article_str)
        if img_match:
            img_url = img_match.group(1)
            bot.send_message(message.chat.id, img_url)
        if vid_match:
            vid_url = vid_match.group(1)
            title_match = re.search(r'🎬 Video: (.+?) -', article_str)
            title = title_match.group(1) if title_match else "Related video"
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton(text=title, url=vid_url))
            article_title = re.search(r'📯 Title: (.+?)\n', article_str)
            context = article_title.group(1) if article_title else keyword
            bot.send_message(
                message.chat.id, 
                f"📺 Related video for: {context}", 
                reply_markup=markup
            )

@bot.message_handler(commands=['news_with_media'])
def bot_get_news_with_media(message):
    text = message.text.split()
    if len(text) < 2:
        bot.reply_to(message, "Please provide a keyword after /news_with_media command")
        return
    _, key_words = text[0], text[1:]
    today, older = utilities.get_timeframe()
    news = Aggregator(
        topics_of_interest=key_words,
        newsapi_key=os.environ['NEWS_API'],
        from_time=older,
        to_time=today
    )
    news.enable_media = True
    msg = news.get_news()
    for topics, news_items in msg.items():
        bot.send_message(message.chat.id, f"📱 {topics.replace(',', '').upper()} (WITH MEDIA)")
        bot_create_msg(message=message, news=news_items)

@bot.message_handler(commands=['save_to_sheets'])
def save_news_to_sheets(message):
    text = message.text.split(' ', 1)
    if len(text) < 2:
        bot.reply_to(message, "Please provide a keyword after /save_to_sheets command.\nExample: /save_to_sheets Ukraine")
        return
    keyword = text[1]
    today, older = utilities.get_timeframe()
    news = Aggregator(
        topics_of_interest=[keyword],
        newsapi_key=os.environ['NEWS_API'],
        from_time=older,
        to_time=today
    )
    articles_dict = news.get_news()
    articles = articles_dict.get(keyword, [])
    if not articles:
        bot.reply_to(message, f"No news found for: {keyword}")
        return
    structured_data = {}
    for i, article_str in enumerate(articles, 1):
        article_data = {}        
        title_match = re.search(r'\N{postal horn} Title: (.*?)\n', article_str)
        source_match = re.search(r'\N{personal computer}Source: (.*?)\n', article_str)
        summary_match = re.search(r'\N{newspaper} Summary: (.*?)\n', article_str)
        url_match = re.search(r'\N{link symbol}Original article: (.*?)\n', article_str)
        time_match = re.search(r'\N{hourglass}: (.*?)\n', article_str)
        article_data["title"] = title_match.group(1) if title_match else "Unknown"
        article_data["source"] = source_match.group(1) if source_match else "Unknown"
        article_data["description"] = summary_match.group(1) if summary_match else "No summary available"
        article_data["url"] = url_match.group(1) if url_match else "No URL available"
        article_data["publishedAt"] = time_match.group(1) if time_match else "Unknown date"
        article_data["author"] = "Unknown"  
        structured_data[i] = article_data
    try:
        service = fetch_service()        
        spreadsheet_title = f"News - {keyword} - {today}"
        sheet_names = ["Articles"]
        spreadsheet_id = create_spreadsheet(service, spreadsheet_title, sheet_names)        
        write_single(service, spreadsheet_id, "Articles!A1", structured_data)        
        bot.send_message(message.chat.id, f"News articles saved to Google Sheets!\nSpreadsheet ID: {spreadsheet_id}")
    except Exception as e:
        logger.error(f"Error saving to Google Sheets: {e}")
        bot.reply_to(message, f"Error saving to Google Sheets: {str(e)}")

@bot.message_handler(commands=['export_daily'])
def export_daily_news(message):
    try:
        today, _ = utilities.get_timeframe()
        config = configparser.ConfigParser()
        config.read("configuration.ini")
        default_topics = ["world", "technology"]
        topics_str = config.get("TOPICS", "daily_topics", fallback=",".join(default_topics))
        topics = [topic.strip() for topic in topics_str.split(",")]        
        if not topics:
            bot.reply_to(message, "No topics configured for daily export. Using defaults.")
            topics = default_topics
        bot.send_message(message.chat.id, f"Starting daily export for topics: {', '.join(topics)}")
        service = fetch_service()
        spreadsheet_title = f"Daily News Report - {today}"
        spreadsheet_id = create_spreadsheet(service, spreadsheet_title, topics)
        for topic in topics:
            news = Aggregator(
                topics_of_interest=[topic],
                newsapi_key=os.environ['NEWS_API'],
                from_time=today,  
                to_time=today
            )
            articles_dict = news.get_news()
            articles = articles_dict.get(topic, [])
            structured_data = {}
            for i, article_str in enumerate(articles, 1):
                article_data = {}
                title_match = re.search(r'\N{postal horn} Title: (.*?)\n', article_str)
                source_match = re.search(r'\N{personal computer}Source: (.*?)\n', article_str)
                summary_match = re.search(r'\N{newspaper} Summary: (.*?)\n', article_str)
                url_match = re.search(r'\N{link symbol}Original article: (.*?)\n', article_str)
                time_match = re.search(r'\N{hourglass}: (.*?)\n', article_str)
                article_data["title"] = title_match.group(1) if title_match else "Unknown"
                article_data["source"] = source_match.group(1) if source_match else "Unknown"
                article_data["description"] = summary_match.group(1) if summary_match else "No summary available"
                article_data["url"] = url_match.group(1) if url_match else "No URL available"
                article_data["publishedAt"] = time_match.group(1) if time_match else "Unknown date"
                article_data["author"] = "Unknown"
                structured_data[i] = article_data            
            write_single(service, spreadsheet_id, f"{topic}!A1", structured_data)
        bot.send_message(message.chat.id, f"Daily news export complete!\nSpreadsheet ID: {spreadsheet_id}")
    except Exception as e:
        logger.error(f"Error in daily export: {e}")
        bot.reply_to(message, f"Error in daily export: {str(e)}")

def main():
    load_dotenv()
    configure_logger()
    try:
        logger.info("Testing Google Sheets connection...")
        logger.info("Google Sheets connection successful")
    except Exception as e:
        logger.error(f"Google Sheets connection failed: {e}")
        logger.error("Make sure credentials.json is in place and token.json will be generated on first run")
    bot.infinity_polling()

if __name__ == '__main__':
	main()