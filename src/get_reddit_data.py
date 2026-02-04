import time
import requests
import random
import xml.etree.ElementTree as ET
from .logger_config import setup_logger

logger = setup_logger()

# === 🧅 洋葱网络配置 ===
# 指向 GitHub Action 本地运行的 Tor 端口
TOR_PROXY = "socks5h://127.0.0.1:9050" 

PROXIES = {
    'http': TOR_PROXY,
    'https': TOR_PROXY
}

# === 🛡️ 镜像池 (Onion 优先) ===
def get_onion_mirrors():
    """
    优先使用 .onion 域名。
    这些是 RedLib/LibReddit 的暗网地址，只能通过 Tor 访问。
    特点：极慢，但极稳，绝不封号。
    """
    return [
        # 🌰 顶级 Onion 节点 (RedLib 官方或高可用)
        'http://lpt37amjv26sx3gnmjrvldk5c3y74y5h9b5e323h3q3q2w2g2m2n2.onion', # RedLib 官方 Onion
        'http://libred72727272727272727272727272727272727272727272727.onion', # 另一个著名的 Onion
        'http://u66743h546373322.onion', # 假定存在的备用节点
        
        # 🌐 Clearweb 节点 (走 Tor 访问也能隐藏身份)
        'https://redlib.privacyredirect.com',
        'https://libreddit.bus-hit.me',
        'https://redlib.perennialteks.com',
        'https://redlib.freedit.eu',
        'https://libreddit.kavin.rocks',
        'https://www.reddit.com' # 最后的最后，走 Tor 访问官方
    ]

# 动态获取更多 Onion 节点
def fetch_dynamic_onions():
    try:
        # 通过 Tor 访问列表，防止列表本身被墙
        url = "https://raw.githubusercontent.com/redlib-org/redlib-instances/main/instances.json"
        resp = requests.get(url, proxies=PROXIES, timeout=20)
        
        mirrors = []
        if resp.status_code == 200:
            data = resp.json()
            iterator = data.values() if isinstance(data, dict) else data
            
            for inst in iterator:
                if not isinstance(inst, dict): continue
                # 专门找 .onion 地址
                if 'onion' in inst.get('url', ''):
                    mirrors.append(inst['url'])
                # 或者状态很好的 clearweb 地址
                elif inst.get('monitor', {}).get('status') == 'up':
                    mirrors.append(inst['url'])
            
            if mirrors:
                # 把 Onion 排在前面
                mirrors.sort(key=lambda x: 0 if 'onion' in x else 1)
                return mirrors[:8] # 取前8个
    except Exception as e:
        logger.warning(f"⚠️ 动态获取 Onion 列表失败: {e}")
    
    return get_onion_mirrors()

# 初始化镜像池
MIRRORS = fetch_dynamic_onions()

# === 📡 慢速请求器 ===
def make_request(url, mode="json"):
    user_agents = [
        'Mozilla/5.0 (Windows NT 10.0; rv:109.0) Gecko/20100101 Firefox/115.0', # Tor Browser 常用 UA
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    ]
    
    headers = {
        'User-Agent': random.choice(user_agents),
        'Cache-Control': 'no-cache'
    }

    try:
        # 洋葱网络非常慢，给足耐心 (30秒)
        # 官方源通过 Tor 访问时容易被 Cloudflare 拦，所以 Onion 优先
        resp = requests.get(
            url, 
            headers=headers, 
            proxies=PROXIES,  # 🔥 强制走 Tor
            timeout=30        # 🔥 宽限超时时间
        )
        
        if resp.status_code == 200:
            return resp
        elif resp.status_code == 429:
            time.sleep(5) # 限流了多睡会儿
            
    except Exception as e:
        # logger.debug(f"   Request failed: {e}")
        pass
        
    return None

# === ♻️ 分布式 RSS ===
def fetch_via_rss(subreddit):
    posts = []
    # 乱序尝试，防止盯着一个薅
    random.shuffle(MIRRORS)
    
    for mirror in MIRRORS:
        try:
            rss_url = f"{mirror}/r/{subreddit}/hot.rss?t={int(time.time())}"
            # logger.info(f"   Trying RSS via Tor: {mirror} ...")
            
            resp = make_request(rss_url, mode="rss")
            if not resp: continue

            # 解析 XML (尝试兼容 Atom 和 RSS)
            try:
                root = ET.fromstring(resp.content)
                ns = {'atom': 'http://www.w3.org/2005/Atom'}
                
                # 提取条目
                entries = root.findall('atom:entry', ns)
                if not entries: entries = root.findall('./channel/item')
                if not entries: continue 

                for entry in entries:
                    # 标题
                    title_node = entry.find('atom:title', ns)
                    if title_node is None: title_node = entry.find('title')
                    title = title_node.text if title_node else "No Title"

                    # 链接
                    link_node = entry.find('atom:link', ns)
                    link = link_node.attrib.get('href') if link_node is not None else ""
                    if not link:
                        link_node = entry.find('link')
                        link = link_node.text if link_node else ""

                    # ID 生成
                    try:
                        if '/comments/' in link:
                            post_id = link.split('/comments/')[1].split('/')[0]
                        else: post_id = str(abs(hash(title)))[:8]
                    except: post_id = "rss_" + str(int(time.time()))[-4:]
                    
                    posts.append({
                        "title": title,
                        "id": post_id,
                        "url": link,
                        "score": 0, "upvote_ratio": 1.0, "num_comments": 0,
                        "created_utc": time.time(),
                        "subreddit": subreddit,
                        "selftext": title, # RSS 只有标题
                        "comments": []
                    })
                    if len(posts) >= 10: break
                
                if posts:
                    logger.info(f"   ✅ RSS Success via Tor ({mirror}): Got {len(posts)} posts.")
                    return posts 
            except: continue
        except: continue

    logger.error(f"   ❌ All Tor RSS mirrors failed for r/{subreddit}")
    return []

# === 📥 JSON 抓取 ===
def fetch_json(path):
    random.shuffle(MIRRORS)
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
    # 评论区如果不重要，为了速度可以不抓，这里尝试抓一下
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

# === 🚀 主入口 ===
def get_post_data(subreddit_name, post_limit=10, comment_limmit=5, reddit=None, posts_to_get="Hot"):
    logger.info(f"🚀 [Tor] Fetching r/{subreddit_name} (Pool: {len(MIRRORS)} onions/mirrors)...")
    
    # 1. 尝试 JSON
    list_data = fetch_json(f"/r/{subreddit_name}/hot.json?limit={post_limit}")
    
    cleaned_posts = []
    if list_data and isinstance(list_data, dict) and 'data' in list_data:
        children = list_data['data'].get('children', [])
        for child in children:
            try:
                p = child['data']
                # Tor 比较慢，不需要额外 sleep 太久，本身延迟就高
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
                    "selftext": f"{p.get('title')} . Top Comments: {comments}" if comments else p.get('title'),
                    "comments": []
                })
            except: continue
    
    # 2. Tor JSON 失败 -> Tor RSS 兜底
    if not cleaned_posts:
        logger.info(f"   ⚠️ Tor JSON failed. Switching to Tor RSS...")
        cleaned_posts = fetch_via_rss(subreddit_name)
        
    return cleaned_posts
