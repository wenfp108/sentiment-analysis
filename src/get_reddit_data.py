import time
import requests
import random
from .logger_config import setup_logger

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

def fetch_json(path, max_retries=3):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }

    for attempt in range(max_retries):
        # 每次重试打乱顺序
        mirrors = list(MIRRORS)
        random.shuffle(mirrors)
        mirrors.sort(key=lambda x: 'old.reddit' not in x)

        for mirror in mirrors:
            try:
                url = f"{mirror}{path}"
                separator = '&' if '?' in url else '?'
                url += f"{separator}t={int(time.time())}"

                timeout = 10 if 'reddit.com' in mirror else 5
                resp = requests.get(url, headers=headers, timeout=timeout)

                if resp.status_code == 200:
                    try:
                        data = resp.json()
                        if (isinstance(data, dict) and 'data' in data) or (isinstance(data, list) and len(data) > 0):
                            return data
                    except (ValueError, KeyError) as e:
                        logger.warning(f"⚠️ {mirror} JSON parse error: {e}")
                elif resp.status_code == 429:
                    logger.warning(f"⚠️ {mirror} rate limited (429)")
                    time.sleep(2)
                else:
                    logger.warning(f"⚠️ {mirror} returned {resp.status_code}")

            except requests.exceptions.Timeout:
                logger.warning(f"⚠️ {mirror} timeout")
            except requests.exceptions.ConnectionError as e:
                logger.warning(f"⚠️ {mirror} connection error: {str(e)[:50]}")
            except Exception as e:
                logger.warning(f"⚠️ {mirror} unexpected error: {e}")

        if attempt < max_retries - 1:
            wait = 2 ** (attempt + 1)
            logger.info(f"💤 All mirrors failed, retrying in {wait}s ({attempt+1}/{max_retries})...")
            time.sleep(wait)

    logger.error(f"❌ Failed to fetch {path} from all mirrors after {max_retries} attempts.")
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
        except Exception as e:
            logger.warning(f"⚠️ Comment parse error: {e}")
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
            except Exception as e:
                logger.warning(f"⚠️ Post parse error in r/{subreddit_name}: {e}")
                continue
                
    return cleaned_posts
