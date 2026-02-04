import time
import requests
import random
from .logger_config import setup_logger

logger = setup_logger()

# === 🛡️ 自动获取镜像列表 ===
def get_fresh_mirrors():
    """从官方仓库动态获取活跃的 RedLib 实例"""
    fallback_mirrors = [
        'https://redlib.privacyredirect.com',
        'https://libreddit.bus-hit.me',
        'https://redlib.perennialteks.com',
        'https://redlib.freedit.eu',
        'https://www.reddit.com' # 最后的兜底
    ]
    
    try:
        # 这是一个维护得很好的实例列表 JSON
        url = "https://raw.githubusercontent.com/redlib-org/redlib-instances/main/instances.json"
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            # 筛选出 up (在线) 且 monitor (被监控) 的实例
            fresh_list = [inst['url'] for inst in data if inst.get('monitor', {}).get('status') == 'up']
            
            if fresh_list:
                # 随机选 5 个，防止只盯着一个薅
                selected = random.sample(fresh_list, min(5, len(fresh_list)))
                # 必须把官方源加在最后作为兜底
                selected.append('https://www.reddit.com')
                logger.info(f"🔄 Refreshed mirrors: {len(selected)} active instances found.")
                return selected
    except Exception as e:
        logger.warning(f"⚠️ Failed to fetch dynamic mirrors: {e}")
    
    return fallback_mirrors

# 初始化时获取一次即可
MIRRORS = get_fresh_mirrors()

def fetch_json(path):
    """通用请求函数"""
    # 伪装 Header
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    }

    for mirror in MIRRORS:
        try:
            url = f"{mirror}{path}"
            
            # 官方源特殊处理
            if 'reddit.com' in mirror:
                time.sleep(2) # 官方源必须慢一点
            else:
                separator = '&' if '?' in url else '?'
                url += f"{separator}t={int(time.time())}"

            resp = requests.get(url, headers=headers, timeout=10)
            
            if resp.status_code == 200:
                try:
                    return resp.json()
                except: continue
            elif resp.status_code == 429:
                time.sleep(2)
            
        except:
            continue
            
    logger.error(f"❌ All mirrors failed for path: {path}")
    return None

def get_top_comments_text(post_id):
    """获取 Top 3 评论"""
    data = fetch_json(f"/comments/{post_id}.json")
    comments_list = []
    
    if data and isinstance(data, list) and len(data) > 1:
        try:
            children = data[1].get('data', {}).get('children', [])
            for child in children[:3]:
                body = child.get('data', {}).get('body')
                if body and body not in ['[deleted]', '[removed]']:
                    # 简单清洗一下换行
                    clean_body = body.replace('\n', ' ').strip()
                    comments_list.append(clean_body)
        except: pass
    
    return " | ".join(comments_list)

def get_post_data(subreddit_name, post_limit=10, comment_limmit=5, reddit=None, posts_to_get="Hot"):
    # 强制使用 .json
    list_path = f"/r/{subreddit_name}/hot.json?limit={post_limit}"
    
    logger.info(f"🚀 [Fetch] r/{subreddit_name} via pool ({len(MIRRORS)} nodes)...")
    list_data = fetch_json(list_path)
    
    cleaned_posts = []
    
    if list_data and isinstance(list_data, dict) and 'data' in list_data:
        children = list_data['data'].get('children', [])
        
        for i, child in enumerate(children):
            try:
                p = child['data']
                pid = p['id']
                
                # 抓取评论
                time.sleep(1)
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
                    # 你的核心需求：标题+评论拼接
                    "selftext": f"{p.get('title')} . Top Comments: {comments_text}",
                    "comments": [] 
                }
                cleaned_posts.append(post_obj)
            except: continue
            
    return cleaned_posts
