import time
import requests
import random
from .logger_config import setup_logger

logger = setup_logger()

# === 🛡️ 适合 Serv00 的镜像源 (Serv00 在欧洲，连这些极快) ===
MIRRORS = [
    'https://redlib.privacyredirect.com',
    'https://redlib.freedit.eu',
    'https://redlib.perennialteks.com',
    'https://libreddit.bus-hit.me',
    'https://libreddit.kavin.rocks',
    'https://www.reddit.com' # Serv00 IP 干净，通常可直连
]

def fetch_json(path):
    """
    Serv00 专用请求函数：
    不需要 Tor 代理，直接用 requests 轮询
    """
    # 伪装成浏览器
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }

    # 打乱顺序，随机选择一个节点开始
    random.shuffle(MIRRORS)

    for mirror in MIRRORS:
        try:
            url = f"{mirror}{path}"
            # 加个随机参数防缓存
            separator = '&' if '?' in url else '?'
            url += f"{separator}t={int(time.time())}"

            # 官方源请求慢一点，镜像源可以快点
            timeout = 6 if 'reddit.com' not in mirror else 10
            
            resp = requests.get(url, headers=headers, timeout=timeout)
            
            if resp.status_code == 200:
                try:
                    data = resp.json()
                    # 简单验证数据有效性
                    if isinstance(data, dict) and 'data' in data:
                        return data
                    if isinstance(data, list) and len(data) > 0:
                        return data
                except:
                    continue
            elif resp.status_code == 429:
                time.sleep(2) # 限流了就歇两秒
            
        except Exception:
            continue
            
    logger.error(f"❌ Failed to fetch {path} from all mirrors.")
    return None

def get_top_comments_text(post_id):
    """获取评论"""
    data = fetch_json(f"/comments/{post_id}.json")
    comments_list = []
    
    if data and isinstance(data, list) and len(data) > 1:
        try:
            children = data[1].get('data', {}).get('children', [])
            for child in children[:3]: # 取前3条
                body = child.get('data', {}).get('body')
                if body and body not in ['[deleted]', '[removed]']:
                    comments_list.append(body.replace('\n', ' ').strip())
        except: pass
    
    return " | ".join(comments_list)

def get_post_data(subreddit_name, post_limit=10, comment_limmit=5, reddit=None, posts_to_get="Hot"):
    logger.info(f"🚀 [Serv00] Fetching r/{subreddit_name}...")
    
    # 强制加上 .json
    list_path = f"/r/{subreddit_name}/hot.json?limit={post_limit}"
    list_data = fetch_json(list_path)
    
    cleaned_posts = []
    
    if list_data and isinstance(list_data, dict) and 'data' in list_data:
        children = list_data['data'].get('children', [])
        
        for i, child in enumerate(children):
            try:
                p = child['data']
                # Serv00 性能一般，稍微休息一下防止请求太快被封
                time.sleep(0.2) 
                
                comments_text = get_top_comments_text(p['id'])
                
                post_obj = {
                    "title": p.get('title'),
                    "id": p.get('id'),
                    "url": f"https://www.reddit.com{p.get('permalink')}",
                    "score": p.get('score', 0),
                    "upvote_ratio": p.get('upvote_ratio', 1.0),
                    "num_comments": p.get('num_comments', 0),
                    "created_utc": p.get('created_utc'),
                    "subreddit": subreddit_name,
                    "selftext": f"{p.get('title')} . Top Comments: {comments_text}",
                    "comments": [] 
                }
                cleaned_posts.append(post_obj)
            except: continue
            
    return cleaned_posts
