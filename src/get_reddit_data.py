import time
import requests
import random
from .logger_config import setup_logger

logger = setup_logger()

# === 🛡️ 1. 自动猎杀活跃镜像 (修复版) ===
def get_fresh_mirrors():
    """动态获取活跃的 RedLib 实例，兼容多种 JSON 格式"""
    # 备选池：混合了 RedLib 和 Reddit 官方源
    fallback_mirrors = [
        'https://redlib.privacyredirect.com',
        'https://libreddit.bus-hit.me',
        'https://redlib.perennialteks.com',
        'https://redlib.freedit.eu',
        'https://libreddit.kavin.rocks',
        'https://snoo.habedieeh.re',
        'https://www.reddit.com', # 官方源
        'https://old.reddit.com'  # 老版官方源 (有时候限制宽松点)
    ]
    
    try:
        logger.info("🔄 正在从官方列表寻找活跃节点...")
        url = "https://raw.githubusercontent.com/redlib-org/redlib-instances/main/instances.json"
        resp = requests.get(url, timeout=10)
        
        if resp.status_code == 200:
            data = resp.json()
            fresh_list = []

            # 兼容处理：如果是字典，取 values；如果是列表，直接用
            iterator = data.values() if isinstance(data, dict) else data

            for inst in iterator:
                # 防御性编程：确保 inst 是字典且有 url
                if not isinstance(inst, dict): continue
                
                # 筛选标准：status=up 且 monitor=true，且不是暗网(.onion)
                monitor = inst.get('monitor', {})
                if monitor.get('status') == 'up' and 'onion' not in inst.get('url', ''):
                    fresh_list.append(inst['url'])
            
            if fresh_list:
                # 随机选 6 个新节点 + 官方源
                selected = random.sample(fresh_list, min(6, len(fresh_list)))
                selected.append('https://www.reddit.com')
                logger.info(f"✅ 成功锁定 {len(selected)} 个活跃节点！")
                return selected
            else:
                logger.warning("⚠️ 获取到的列表为空，切换回备选池。")
    except Exception as e:
        logger.warning(f"⚠️ 动态获取失败 ({type(e).__name__})，切换回备选池: {e}")
    
    return fallback_mirrors

# 初始化
MIRRORS = get_fresh_mirrors()

def fetch_json(path):
    """通用请求函数 (带详细诊断)"""
    # 🎭 伪装成最新的 Chrome
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Cache-Control': 'no-cache',
        'Pragma': 'no-cache'
    }

    for mirror in MIRRORS:
        try:
            url = f"{mirror}{path}"
            
            # 官方源必须慢一点，且不能带随机参数
            if 'reddit.com' in mirror:
                time.sleep(2) 
            else:
                separator = '&' if '?' in url else '?'
                url += f"{separator}t={int(time.time())}"

            # logger.info(f"   Trying: {mirror} ...")
            resp = requests.get(url, headers=headers, timeout=8)
            
            if resp.status_code == 200:
                try:
                    data = resp.json()
                    # 再次确认数据有效性
                    if isinstance(data, dict) and 'data' in data:
                        return data
                    if isinstance(data, list) and len(data) > 0:
                        return data
                    # 如果返回空字典或无关内容
                    # logger.warning(f"   ⚠️ {mirror} returned valid 200 but invalid JSON structure.")
                except: 
                    pass # JSON 解析失败，跳过
            elif resp.status_code == 429:
                # logger.warning(f"   ⚠️ Rate Limit (429) at {mirror}")
                time.sleep(2)
            else:
                # 打印错误码，方便调试
                # logger.warning(f"   ❌ {mirror} failed with {resp.status_code}")
                pass
            
        except requests.exceptions.Timeout:
            # logger.warning(f"   ⏳ Timeout at {mirror}")
            continue
        except Exception as e:
            # logger.warning(f"   ❌ Error at {mirror}: {e}")
            continue
            
    logger.error(f"❌ 所有节点 ({len(MIRRORS)}个) 全部尝试失败: {path}")
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
                    clean = body.replace('\n', ' ').strip()
                    comments_list.append(clean)
        except: pass
    
    return " | ".join(comments_list)

def get_post_data(subreddit_name, post_limit=10, comment_limmit=5, reddit=None, posts_to_get="Hot"):
    logger.info(f"🚀 [Fetch] r/{subreddit_name} (Pool: {len(MIRRORS)} nodes)...")
    
    # 强制加上 .json
    list_path = f"/r/{subreddit_name}/hot.json?limit={post_limit}"
    list_data = fetch_json(list_path)
    
    cleaned_posts = []
    
    if list_data and isinstance(list_data, dict) and 'data' in list_data:
        children = list_data['data'].get('children', [])
        
        for i, child in enumerate(children):
            try:
                p = child['data']
                pid = p['id']
                
                time.sleep(1) # 稍微慢点，稳一点
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
            except: continue
            
    return cleaned_posts
