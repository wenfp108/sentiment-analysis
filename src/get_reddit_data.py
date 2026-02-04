import time
import requests
import random
from .logger_config import setup_logger

logger = setup_logger()

# === 🛡️ Serv00 专用直连镜像池 ===
# Serv00 位于欧洲，连接这些欧洲节点速度飞快，不需要 Tor
MIRRORS = [
    'https://redlib.privacyredirect.com',
    'https://redlib.freedit.eu',
    'https://redlib.perennialteks.com',
    'https://libreddit.bus-hit.me',
    'https://libreddit.kavin.rocks',
    'https://www.reddit.com'
]

def fetch_json(path):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    random.shuffle(MIRRORS)

    for mirror in MIRRORS:
        try:
            url = f"{mirror}{path}"
            separator = '&' if '?' in url else '?'
            url += f"{separator}t={int(time.time())}"
            
            # 官方源请求慢一点，镜像源可以快点
            timeout = 5 if 'reddit.com' not in mirror else 10
            
            resp = requests.get(url, headers=headers, timeout=timeout)
            
            if resp.status_code == 200:
                try:
                    data = resp.json()
                    if (isinstance(data, dict) and 'data' in data) or (isinstance(data, list) and len(data) > 0):
                        return data
                except: continue
            elif resp.status_code == 429:
                time.sleep(2)
        except: continue
            
    logger.error(f"❌ Failed to fetch {path} from all mirrors.")
    return None

def get_top_comments_text(post_id):
    data = fetch_json(f"/comments/{post_id}.json")
    comments_list = []
    if data and isinstance(data, list) and len(data) > 1:
        try:
            children = data[1].get('data', {}).get('children', [])
            for child in children[:3]:
                body = child.get('data', {}).get('body')
                if body and body not in ['[deleted]', '[removed]']:
                    comments_list.append(body.replace('\n', ' ').strip())
        except: pass
    return " | ".join(comments_list)

def get_post_data(subreddit_name, post_limit=10, comment_limmit=5, reddit=None, posts_to_get="Hot"):
    logger.info(f"🚀 [Serv00] Fetching r/{subreddit_name}...")
    list_path = f"/r/{subreddit_name}/hot.json?limit={post_limit}"
    list_data = fetch_json(list_path)
    
    cleaned_posts = []
    if list_data and isinstance(list_data, dict) and 'data' in list_data:
        children = list_data['data'].get('children', [])
        for child in children:
            try:
                p = child['data']
                time.sleep(0.2)
                comments = get_top_comments_text(p['id'])
                cleaned_posts.append({
                    "title": p.get('title'),
                    "id": p.get('id'),
                    "url": f"https://www.reddit.com{p.get('permalink')}",
                    "score": p.get('score', 0),
                    "upvote_ratio": p.get('upvote_ratio', 1.0),
                    "num_comments": p.get('num_comments', 0),
                    "created_utc": p.get('created_utc'),
                    "subreddit": subreddit_name,
                    "selftext": f"{p.get('title')} . Top Comments: {comments}",
                    "comments": []
                })
            except: continue
    return cleaned_posts
