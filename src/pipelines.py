from textblob import TextBlob
from .get_reddit_data import get_post_data
from .logger_config import setup_logger
from datetime import datetime

logger = setup_logger()

def analyze_sentiment(text):
    try:
        return TextBlob(str(text)).sentiment.polarity
    except:
        return 0.0

def top_posts_subreddit_pipeline(subreddit_name, post_limit, comment_limmit, posts_to_get="Hot"):
    # 1. 获取数据
    posts = get_post_data(subreddit_name, post_limit, comment_limmit, None, posts_to_get)
    
    if not posts:
        logger.warning(f"No posts found for r/{subreddit_name}")
        return [] 
        
    # 2. 轻量级情感分析
    processed_posts = []
    for post in posts:
        # 构造完整文本
        full_text = f"{post.get('title', '')} {post.get('selftext', '')}"
        
        # 情感打分
        score = analyze_sentiment(full_text)
        
        # 写入新字段
        post['vibe_val'] = score
        post['clean_text'] = full_text
        try:
            post['timestamp'] = datetime.utcfromtimestamp(post.get('created_utc', 0))
        except:
            post['timestamp'] = datetime.utcnow()
        
        processed_posts.append(post)

    return processed_posts
