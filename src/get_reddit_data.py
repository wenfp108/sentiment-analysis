import io
import json
import time
import boto3
import praw
from .logger_config import setup_logger

logger = setup_logger()

# === 保持原有的 AWS Secrets / 本地文件读取逻辑不变 (请保留你原来的头部代码) ===
# 假设你已经初始化了 reddit = praw.Reddit(...) 
# 下面只贴出需要修改的核心函数：

def get_post_data(
    subreddit_name,
    post_limit=100,
    comment_limmit=100,
    reddit=None, # 确保这里的 reddit client 传进来了
    posts_to_get="Hot",  # 默认改为 Hot
):
    logger.info(
        f"Getting Reddit Data: Subreddit: {subreddit_name} --- Mode: {posts_to_get}"
    )
    if not reddit:
        # 这里应该有你原本的初始化逻辑，或者确保调用时传入了 reddit 实例
        # 为了防呆，这里可以抛错或者再次初始化
        logger.error("Reddit instance is missing!")
        return []

    subreddit = reddit.subreddit(subreddit_name)
    
    # === 🔥 核心修改区域 ===
    if posts_to_get == "Top":
        logger.info("Getting top posts (Today)")
        posts = subreddit.top(limit=post_limit, time_filter="day")
        
    elif posts_to_get == "Hot":
        logger.info("Getting hot posts (Algorithm)")
        posts = subreddit.hot(limit=post_limit)
        
    elif posts_to_get == "Recent":
        logger.info("Getting new posts")
        posts = subreddit.new(limit=post_limit)
    else:
        # 默认回落到 Hot
        posts = subreddit.hot(limit=post_limit)
    # ========================

    posts_with_comments = []
    for post in posts:
        try:
            post.comments.replace_more(limit=0)
            comments = []
            for comment in post.comments.list()[:comment_limmit]:
                if isinstance(comment, praw.models.MoreComments): continue
                comments.append({
                    "body": comment.body,
                    "author": str(comment.author),
                    "score": comment.score,
                    "created_utc": comment.created_utc,
                    "is_top_level": comment.is_root,
                    "parent_id": comment.parent_id,
                    "depth": comment.depth,
                    "gilded": comment.gilded,
                })

            posts_with_comments.append({
                "title": post.title,
                "selftext": post.selftext,
                "score": post.score,
                "url": post.url,
                "author": str(post.author),
                "created_utc": post.created_utc,
                "num_comments": post.num_comments,
                "upvote_ratio": post.upvote_ratio,
                "subreddit": str(post.subreddit),
                "comments": comments,
            })
        except Exception as e:
            logger.error(f"Error processing post {post.id}: {e}")
            continue
            
    return posts_with_comments
