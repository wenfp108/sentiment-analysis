import pandas as pd
from datetime import datetime
from .get_reddit_data import get_post_data
from .sentiment_analysis import get_sentiment
from .text_processor import clean_text
from .logger_config import setup_logger

logger = setup_logger()

# 移除 PRAW 初始化，这在镜像站模式下不需要
def convert_utc(utc_time):
    return datetime.utcfromtimestamp(utc_time)

def top_posts_subreddit_pipeline(
    subreddit_name, post_limit, comment_limmit, posts_to_get="Hot"
):
    # 调用新的 get_post_data (它现在不需要 reddit 实例)
    post_data = get_post_data(
        subreddit_name=subreddit_name,
        post_limit=post_limit,
        comment_limmit=comment_limmit,
        posts_to_get=posts_to_get,
    )
    
    df = pd.DataFrame(post_data)
    if df.empty: 
        logger.warning(f"r/{subreddit_name} returned empty data.")
        return df

    # 这里的 selftext 已经是我们拼好的 "Title + Comments"
    # 直接对它进行清洗和分析
    df["clean_text"] = df["selftext"].apply(lambda x: clean_text(str(x)))
    
    # 执行 BERT 情绪分析
    # 注意：我们分析的是 clean_text (包含评论)，效果比只分析标题好
    df = get_sentiment(df, "clean_text")
    
    # 补充时间字段
    df["timestamp"] = df["created_utc"].apply(convert_utc)
    
    # 计算 rank_score (热度 * 情绪动能)
    # sentiment_clean_text_score 是 BERT 的置信度
    # sentiment_clean_text_label 是 POSITIVE/NEGATIVE
    
    # 将 Label 转为数值：POSITIVE=1, NEGATIVE=-1
    df['vibe_val'] = df.apply(
        lambda x: x['sentiment_clean_text_score'] if x['sentiment_clean_text_label'] == 'POSITIVE' else -x['sentiment_clean_text_score'], 
        axis=1
    )
    
    return df
