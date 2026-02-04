import time
import requests
import random
from .logger_config import setup_logger

logger = setup_logger()

# === 🛡️ 镜像站池 (已更新为 2026 活跃节点) ===
# 策略：混合使用 RedLib 实例和官方源
MIRRORS = [
    # 优先尝试比较稳定的私有/小众实例
    'https://redlib.privacyredirect.com',
    'https://libreddit.bus-hit.me',
    'https://redlib.perennialteks.com',
    'https://redlib.freedit.eu',
    'https://libreddit.kavin.rocks',
    # 最后的兜底：官方源 (虽然容易限流，但比死掉好)
    'https://www.reddit.com'
]

def fetch_json(path):
    """通用请求函数：轮询镜像站直到成功"""
    headers = {
        # 伪装成真实的桌面浏览器，防止被秒杀
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5'
    }

    for mirror in MIRRORS:
        try:
            url = f"{mirror}{path}"
            
            # 官方源需要特别处理：不能加太频繁的随机参，且必须 .json 结尾
            if 'reddit.com' in mirror:
                # 官方源请求稍微慢一点，防封
                time.sleep(1)
            else:
                # 镜像站加随机参防缓存
                separator = '&' if '?' in url else '?'
                url += f"{separator}t={int(time.time())}"

            # logger.info(f"   Trying: {mirror} ...")
            resp = requests.get(url, headers=headers, timeout=8)
            
            if resp.status_code == 200:
                try:
                    return resp.json()
                except:
                    # 有时候返回的是 HTML 错误页而不是 JSON
                    continue
            elif resp.status_code == 429:
                logger.warning(f"   ⚠️ Rate Limit (429) at {mirror}")
                time.sleep(2) # 遇到限流稍微歇一下
            
        except Exception as e:
            # logger.warning(f"   ❌ Error {mirror}: {e}")
            continue
            
    logger.error(f"❌ All mirrors failed for path: {path}")
    return None

def get_top_comments_text(post_id):
    """获取 Top 3 评论文本"""
    # 评论区只尝试一次，不需要太重
    data = fetch_json(f"/comments/{post_id}.json")
    comments_list = []
    
    if data and isinstance(data, list) and len(data) > 1:
        try:
            children = data[1].get('data', {}).get('children', [])
            for child in children[:3]: # 只取前3条
                body = child.get('data', {}).get('body')
                score = child.get('data', {}).get('score', 0)
                if body and body not in ['[deleted]', '[removed]']:
                    comments_list.append(f"[Score:{score}] {body}")
        except: pass
    
    return " | ".join(comments_list)

def get_post_data(subreddit_name, post_limit=10, comment_limmit=5, reddit=None, posts_to_get="Hot"):
    logger.info(f"🚀 [Fetch] r/{subreddit_name} ({posts_to_get})...")
    
    # 强制使用 .json 后缀，这对官方源和镜像站都适用
    # 注意：Limit 参数在 URL 里
    list_path = f"/r/{subreddit_name}/hot.json?limit={post_limit}"
    list_data = fetch_json(list_path)
    
    cleaned_posts = []
    
    # 检查数据有效性 (RedLib 和 Reddit 原生 JSON 结构略有不同，但 data.children 是一样的)
    if list_data and isinstance(list_data, dict) and 'data' in list_data:
        children = list_data['data'].get('children', [])
        
        for i, child in enumerate(children):
            try:
                p = child['data']
                pid = p['id']
                
                # 抓取评论 (休眠防封)
                time.sleep(1.5) 
                comments_text = get_top_comments_text(pid)
                
                post_obj = {
                    "title": p.get('title'),
                    "id": pid,
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
            except Exception as e:
                logger.error(f"Error parsing post: {e}")
                continue
            
    return cleaned_posts
