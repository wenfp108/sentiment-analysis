import os
import json
import base64
import requests
import schedule
import time
from datetime import datetime, timezone, timedelta

from src.pipelines import top_posts_subreddit_pipeline
from src.logger_config import setup_logger

logger = setup_logger()

# === 配置区 ===
COMMAND_REPO = "wenfp108/Central-Bank"
OUTPUT_ROOT = "reddit/sentiment"
POOL_SIZE = 10     
COMMENT_LIMIT = 5 

# ⚠️ 这里留空，让脚本优先读环境变量。如果在服务器跑，我们用 export 命令注入 Token
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")

def get_github_headers():
    if not GITHUB_TOKEN:
        logger.error("❌ GITHUB_TOKEN not found! Please export GITHUB_TOKEN=... before running.")
        return None
    return {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }

def fetch_missions():
    headers = get_github_headers()
    if not headers: return {}
    try:
        url = f"https://api.github.com/repos/{COMMAND_REPO}/issues?state=open"
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code != 200: return {}
        
        missions = {}
        for issue in resp.json():
            title = issue.get('title', '').lower()
            if '[reddit]' in title:
                sub_name = title.replace('[reddit]', '').strip()
                missions[sub_name] = []
        return missions
    except Exception as e:
        logger.error(f"Fetch missions failed: {e}")
        return {}

def sync_to_central_bank(data_batch):
    headers = get_github_headers()
    if not headers: return

    now = datetime.now(timezone(timedelta(hours=8)))
    
    # === 修改部分：既要文件夹，又要长文件名 ===
    # 1. 制造文件夹路径 (YYYY/MM/DD)
    folder_path = now.strftime('%Y/%m/%d')
    
    # 2. 制造文件名 (YYYY-MM-DD-HHMMSS.json)
    file_name = now.strftime('%Y-%m-%d-%H%M%S')
    
    # 3. 拼在一起！(reddit/sentiment/2026/02/05/2026-02-05-012338.json)
    path = f"{OUTPUT_ROOT}/{folder_path}/{file_name}.json"
    # ==========================================
    
    api_url = f"https://api.github.com/repos/{COMMAND_REPO}/contents/{path}"
    
    try:
        final_content = json.dumps([data_batch], indent=2, ensure_ascii=False)
        b64_content = base64.b64encode(final_content.encode('utf-8')).decode('utf-8')
        
        payload = {
            "message": f"🤖 Reddit Incremental: {now.strftime('%H:%M:%S')}",
            "content": b64_content,
            "branch": "main"
        }
        
        resp = requests.put(api_url, headers=headers, json=payload)
        if resp.status_code in [200, 201]:
            logger.info(f"✅ Data synced to {path}")
        else:
            logger.error(f"❌ Upload failed: {resp.status_code} {resp.text}")
    except Exception as e:
        logger.error(f"Sync failed: {e}")

def job():
    logger.info("⏰ Job started...")
    missions = fetch_missions()
    if not missions:
        logger.info("💤 No missions found.")
        return
        
    logger.info(f"🛡️ Missions: {list(missions.keys())}")
    
    batch_results = []
    
    for sub in missions.keys():
        try:
            posts = top_posts_subreddit_pipeline(sub, POOL_SIZE, COMMENT_LIMIT, "Hot")
            if not posts: continue
            
            for p in posts:
                vibe = float(p.get('vibe_val', 0))
                score = int(p.get('score', 0))
                p['rank_score'] = score * (abs(vibe) + 0.1)

            champions = sorted(posts, key=lambda x: x['rank_score'], reverse=True)[:5]
            
            total_vibe = sum(float(p.get('vibe_val', 0)) for p in posts)
            avg_vibe = total_vibe / len(posts) if posts else 0

            champion_list = []
            for p in champions:
                champion_list.append({
                    "title": p.get('title'),
                    "url": p.get('url'),
                    "score": p.get('score'),
                    "vibe": p.get('vibe_val'),
                    "summary": p.get('clean_text', '')[:100]
                })
            
            batch_results.append({
                "subreddit": sub,
                "avg_sentiment": avg_vibe,
                "champions": champion_list
            })
            
        except Exception as e:
            logger.error(f"Error processing r/{sub}: {e}")
            
    if batch_results:
        payload = {
            "timestamp": datetime.now(timezone(timedelta(hours=8))).isoformat(),
            "data": batch_results
        }
        sync_to_central_bank(payload)

if __name__ == "__main__":
    job()
