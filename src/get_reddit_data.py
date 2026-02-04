import time
import requests
import random
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from .logger_config import setup_logger

logger = setup_logger()

# === 1. 镜像站池 (精选高活节点) ===
def get_fresh_mirrors():
    """定义优先尝试的镜像列表"""
    return [
        'https://redlib.privacyredirect.com',
        'https://libreddit.bus-hit.me',
        'https://redlib.perennialteks.com',
        'https://redlib.freedit.eu',
        'https://libreddit.kavin.rocks',
        'https://snoo.habedieeh.re',
        'https://www.reddit.com',     # 官方 JSON
        'https://old.reddit.com'      # 老版 JSON
    ]

MIRRORS = get_fresh_mirrors()

# === 2. 通用请求函数 ===
def make_request(url, mode="json"):
    """发送 HTTP 请求，自动伪装"""
    # 轮换 User-Agent，有时候伪装成 FeedBurner (RSS抓取器) 会有奇效
    user_agents = [
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)',
        'FeedBurner/1.0 (http://www.FeedBurner.com)', 
        'RefineryBot/1.0'
    ]
    
    headers = {
        'User-Agent': random.choice(user_agents),
        'Accept': 'application/rss+xml, application/json' if mode == "rss" else 'application/json, text/html',
        'Cache-Control': 'no-cache'
    }

    try:
        # 官方源必须限速
        if 'reddit.com' in url: time.sleep(2)
        
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            return resp
        elif resp.status_code == 429:
            time.sleep(2)
    except:
        pass
    return None

# === 3. RSS 兜底机制 (核心新增) ===
def fetch_via_rss(subreddit):
    """当 JSON 全挂时，使用 RSS 获取基础数据"""
    rss_url = f"https://www.reddit.com/r/{subreddit}/hot.rss"
    logger.info(f"   ⚠️ JSON failed. Switching to RSS Fallback: {rss_url}")
    
    resp = make_request(rss_url, mode="rss")
    if not resp: 
        logger.error(f"   ❌ RSS also failed for r/{subreddit}")
        return []

    posts = []
    try:
        # 解析 XML
        root = ET.fromstring(resp.content)
        # RSS 命名空间通常是 default, 但我们需要手动提取 entry
        # Atom 格式通常用 {http://www.w3.org/2005/Atom}entry
        
        # 简单暴力解析：遍历所有 entry 或 item
        # Reddit RSS 格式是 Atom
        ns = {'atom': 'http://www.w3.org/2005/Atom'}
        for entry in root.findall('atom:entry', ns):
            title = entry.find('atom:title', ns).text
            link = entry.find('atom:link', ns).attrib['href']
            # RSS 没有 ID 字段，从 Link 截取
            # Link ex: https://www.reddit.com/r/s/comments/1aje8x/title/
            try:
                post_id = link.split('/comments/')[1].split('/')[0]
            except:
                post_id = "rss_" + str(int(time.time())) + str(random.randint(1,1000))
                
            posts.append({
                "title": title,
                "id": post_id,
                "url": link,
                "score": 0,          # RSS 无分数
                "upvote_ratio": 1.0, # RSS 无情绪值
                "num_comments": 0,   # RSS 无评论数
                "created_utc": time.time(),
                "subreddit": subreddit,
                "selftext": title,   # 无评论，仅保留标题
                "comments": []
            })
            if len(posts) >= 10: break
            
        logger.info(f"   ✅ RSS Salvation: Retrieved {len(posts)} posts (Titles only).")
    except Exception as e:
        logger.error(f"   ❌ RSS Parsing Error: {e}")
    
    return posts

# === 4. JSON 抓取逻辑 ===
def fetch_json(path):
    for mirror in MIRRORS:
        url = f"{mirror}{path}"
        if '?' in url: url += f"&t={int(time.time())}"
        else: url += f"?t={int(time.time())}"
        
        resp = make_request(url, mode="json")
        if resp:
            try:
                data = resp.json()
                if isinstance(data, dict) and 'data' in data: return data
                if isinstance(data, list) and len(data) > 0: return data
            except: continue
    return None

def get_top_comments_text(post_id):
    """尝试获取评论，拿不到就返回空，不强求"""
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

# === 5. 主入口 ===
def get_post_data(subreddit_name, post_limit=10, comment_limmit=5, reddit=None, posts_to_get="Hot"):
    logger.info(f"🚀 [Fetch] r/{subreddit_name}...")
    
    # 1. 尝试 JSON 方式 (数据最全)
    list_data = fetch_json(f"/r/{subreddit_name}/hot.json?limit={post_limit}")
    
    cleaned_posts = []
    
    # 2. 如果 JSON 成功
    if list_data and isinstance(list_data, dict) and 'data' in list_data:
        children = list_data['data'].get('children', [])
        for child in children:
            try:
                p = child['data']
                time.sleep(1) # 礼貌休眠
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
                    # 优先拼接评论
                    "selftext": f"{p.get('title')} . Top Comments: {comments}" if comments else p.get('title'),
                    "comments": []
                })
            except: continue
    
    # 3. 如果 JSON 失败 (cleaned_posts 为空)，触发 RSS 兜底
    if not cleaned_posts:
        cleaned_posts = fetch_via_rss(subreddit_name)
        
    return cleaned_posts
