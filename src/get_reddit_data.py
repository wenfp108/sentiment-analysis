import time
import requests
import random
import urllib3
from .logger_config import setup_logger

# 禁用安全警告（因为我们要关闭 SSL 验证）
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = setup_logger()

# === 🛡️ 终极备用镜像池 ===
# 混合了官方旧版接口 (old.reddit) 和 镜像站
MIRRORS = [
    'https://old.reddit.com',            # 官方旧版，最稳但有时限流
    'https://www.reddit.com',            # 官方新版
    'https://redlib.privacyredirect.com',
    'https://redlib.freedit.eu',
    'https://libreddit.bus-hit.me',
]

def fetch_json(path):
    headers = {
        # 伪装成 Google 爬虫或者非常普通的浏览器
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    # 稍微打乱顺序
    random.shuffle(MIRRORS)

    # 优先尝试 old.reddit，因为它最不像爬虫目标
    current_mirrors = sorted(MIRRORS, key=lambda x: 'old.reddit' not in x)

    for mirror in current_mirrors:
        try:
            url = f"{mirror}{path}"
            separator = '&' if '?' in url else '?'
            url += f"{separator}t={int(time.time())}"
            
            # 官方源给长一点时间
            timeout = 10 if 'reddit.com' in mirror else 5
            
            # 🔥 核心修改：verify=False (忽略 SSL 证书错误)
            resp = requests.get(url, headers=headers, timeout=timeout, verify=False)
            
            if resp.status_code == 200:
                try:
                    data = resp.json()
                    if (isinstance(data, dict) and 'data' in data) or (isinstance(data, list) and len(data) > 0):
                        return data
                except:
                    pass
            elif resp.status_code == 429:
                time.sleep(2) # 被限流了，歇会儿
            else:
                # 打印具体错误码，方便调试
                logger.warning(f"⚠️ {mirror} returned {resp.status_code}")
                
        except Exception as e:
            # 打印具体报错原因！
            logger.warning(f"⚠️ Connect {mirror} failed: {str(e)[:50]}")
            continue
            
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
    
    # URL 修正
    list_path = f"/r/{subreddit_name}/{posts_to_get.lower()}.json?limit={post_limit}"
    list_data = fetch_json(list_path)
    
    cleaned_posts = []
    
    if list_data and isinstance(list_data, dict) and 'data' in list_data:
        children = list_data['data'].get('children', [])
        for child in children:
            try:
                p = child['data']
                time.sleep(0.5) # 稍微快一点
                
                # 如果要完整评论，取消下面这行的注释（会变慢）
                # comments = get_top_comments_text(p['id'])
                comments = ""
                
                cleaned_posts.append({
                    "title": p.get('title'),
                    "id": p.get('id'),
                    "url": f"https://www.reddit.com{p.get('permalink')}",
                    "score": p.get('score', 0),
                    "upvote_ratio": p.get('upvote_ratio', 1.0),
                    "num_comments": p.get('num_comments', 0),
                    "created_utc": p.get('created_utc'),
                    "subreddit": subreddit_name,
                    "selftext": f"{p.get('title')} . {p.get('selftext', '')[:200]}",
                    "comments": []
                })
            except: continue
                
    return cleaned_posts
