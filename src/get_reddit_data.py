import time
import requests
import random
from .logger_config import setup_logger

logger = setup_logger()

# === 镜像站池 ===
MIRRORS = [
    'https://l.opnxng.com',
    'https://redlib.catsarch.com', 
    'https://r.nf',
    'https://redlib.vling.net'
]

def fetch_json(path):
    """通用镜像站请求"""
    for mirror in MIRRORS:
        try:
            url = f"{mirror}{path}"
            separator = '&' if '?' in url else '?'
            url += f"{separator}t={int(time.time())}"
            # 伪装 Header
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) RefineryBot/1.0'}
            
            # logger.info(f"Fetching: {url}")
            resp = requests.get(url, headers=headers, timeout=10)
            
            if resp.status_code == 200:
                return resp.json()
        except:
            continue
    return None

def get_top_comments_text(post_id):
    """获取 Top 3 评论文本"""
    data = fetch_json(f"/comments/{post_id}.json")
    comments_list = []
    
    if data and isinstance(data, list) and len(data) > 1:
        children = data[1].get('data', {}).get('children', [])
        for child in children[:3]: # 只取前3条
            body = child.get('data', {}).get('body')
            score = child.get('data', {}).get('score', 0)
            if body and body not in ['[deleted]', '[removed]']:
                comments_list.append(f"[Score:{score}] {body}")
    
    return " | ".join(comments_list)

# 注意：保持函数签名与你原有代码兼容，但忽略 reddit/posts_to_get 参数
def get_post_data(subreddit_name, post_limit=10, comment_limmit=5, reddit=None, posts_to_get="Hot"):
    logger.info(f"🚀 [Mirror] Fetching r/{subreddit_name} ({posts_to_get})...")
    
    # 强制使用 hot.json，这是最稳的接口
    list_path = f"/r/{subreddit_name}/hot.json?limit={post_limit}"
    list_data = fetch_json(list_path)
    
    cleaned_posts = []
    if list_data and 'data' in list_data:
        children = list_data['data']['children']
        
        for i, child in enumerate(children):
            p = child['data']
            pid = p['id']
            
            # 为了安全，每抓一篇歇 1.5 秒
            time.sleep(1.5)
            # logger.info(f"   Getting comments for {pid}...")
            
            comments_text = get_top_comments_text(pid)
            
            # 核心：构造与原有 pipeline 兼容的字典
            post_obj = {
                "title": p.get('title'),
                "id": pid,
                "url": f"https://www.reddit.com{p.get('permalink')}",
                "score": p.get('score', 0),
                "upvote_ratio": p.get('upvote_ratio', 1.0),
                "num_comments": p.get('num_comments', 0),
                "created_utc": p.get('created_utc'),
                "subreddit": subreddit_name,
                
                # 关键策略：把 标题+评论 拼入 selftext，供 AI 分析
                "selftext": f"{p.get('title')} . Top Comments: {comments_text}",
                
                # 兼容旧代码：comments 设为空列表，因为我们已经提取了文本
                "comments": [] 
            }
            cleaned_posts.append(post_obj)
            
    return cleaned_posts
