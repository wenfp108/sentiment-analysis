import io
import json
import time
import boto3
import praw
from .logger_config import setup_logger

logger = setup_logger()

# ... (保持原本的 Credentials 读取部分不变，可以直接复制你原来的头部) ...
# 为了节省篇幅，这里假设你保留了原本的 client_id, secret 等读取代码
# 重点修改下面的 get_post_data 函数

def get_post_data(
    subreddit_name,
    post_limit=100,
    comment_limmit=100,
    reddit=reddit,
    posts_to_get="Hot",  # 默认改为 Hot (最兼顾热度和时效)
):
    logger.info(
        f"Getting Reddit Data: Subreddit: {subreddit_name} --- Number of Posts: {post_limit} --- Comment Limit : {comment_limmit}"
    )
    subreddit = reddit.subreddit(subreddit_name)
    
    # === 🔥 核心修改区域 ===
    if posts_to_get == "Top":
        logger.info("Getting top posts (Today)")
        # 关键修改：time_filter="day"
        # 含义：只抓取【过去24小时内】点赞最高的贴。这才是最准确的"今日情绪"。
        posts = subreddit.top(limit=post_limit, time_filter="day")
        
    elif posts_to_get == "Hot":
        logger.info("Getting hot posts (Algorithm)")
        # 新增模式：Hot
        # 含义：Reddit 官方热度算法 (点赞数 + 发帖时间权重)。最适合捕捉"正在发生的大事"。
        posts = subreddit.hot(limit=post_limit)
        
    elif posts_to_get == "Recent":
        logger.info("Getting new posts")
        posts = subreddit.new(limit=post_limit)
    # ========================

    posts_with_comments = []
    for post in posts:
        # (以下代码保持不变，负责抓取评论)
        try:
            post.comments.replace_more(limit=0) # 建议改为0以加快速度，除非你需要深层评论
            comments = []
            # 只取前 comment_limmit 条评论
            for comment in post.comments.list()[:comment_limmit]:
                if isinstance(comment, praw.models.MoreComments):
                    continue
                comment_data = {
                    "body": comment.body,
                    "author": str(comment.author),
                    "score": comment.score,
                    "created_utc": comment.created_utc,
                    "is_top_level": comment.is_root,
                    "parent_id": comment.parent_id,
                    "depth": comment.depth,
                    "gilded": comment.gilded,
                }
                comments.append(comment_data)

            post_data = {
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
            }
            posts_with_comments.append(post_data)
        except Exception as e:
            logger.error(f"Error processing post {post.id}: {e}")
            continue
            
    logger.info("Got Reddit Data")
    return posts_with_comments
