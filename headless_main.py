import os
import json
import base64
import requests
import numpy as np
from datetime import datetime, timezone, timedelta

# 引入项目模块
from src.pipelines import top_posts_subreddit_pipeline
from src.logger_config import setup_logger

logger = setup_logger()

# === 配置区 ===
COMMAND_REPO = "wenfp108/Central-Bank"
OUTPUT_ROOT = "reddit/sentiment" # 存到 Central Bank 的哪个文件夹
POOL_SIZE = 10     # 抓每个论坛的前 10 贴
COMMENT_LIMIT = 5  # (此参数在 get_reddit_data 内部已被固定为 3，但需保留传参)

def get_github_headers():
    token = os.environ.get("GITHUB_TOKEN") # 必须在 Action Secrets 里配好
    if not token:
        logger.error("❌ GITHUB_TOKEN not found!")
        return None
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.v3+json"
    }

def fetch_missions():
    """去 Central-Bank 的 Issue 区找任务"""
    headers = get_github_headers()
    if not headers: return {}
    
    try:
        url = f"https://api.github.com/repos/{COMMAND_REPO}/issues?state=open"
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code != 200: return {}
        
        missions = {}
        for issue in resp.json():
            title = issue.get('title', '').lower()
            # 识别标题带 [reddit] 的 Issue
            if '[reddit]' in title:
                # 提取 Body 里的关键词，用逗号分隔
                sub_name = title.replace('[reddit]', '').strip()
                keywords = issue.get('body', '').strip().split(',') if issue.get('body') else []
                missions[sub_name] = keywords
        return missions
    except Exception as e:
        logger.error(f"Fetch missions failed: {e}")
        return {}

def sync_to_central_bank(data_batch):
    """把结果存回 Central-Bank"""
    headers = get_github_headers()
    if not headers: return

    # 生成按天归档的文件名: reddit/sentiment/2026-02-04.json
    now = datetime.now(timezone(timedelta(hours=8)))
    date_str = now.strftime('%Y-%m-%d')
    path = f"{OUTPUT_ROOT}/{date_str}.json"
    
    api_url = f"https://api.github.com/repos/{COMMAND_REPO}/contents/{path}"
    
    # 1. 先拉取当天的旧数据 (Pull)
    existing_data = []
    sha = None
    try:
        resp = requests.get(api_url, headers=headers)
        if resp.status_code == 200:
            file_info = resp.json()
            sha = file_info['sha']
            content = base64.b64decode(file_info['content']).decode('utf-8')
            existing_data = json.loads(content)
    except: pass
    
    # 2. 合并新数据 (Merge)
    # 这里的 data_batch 是一个包含 timestamp 和 data 列表的字典
    existing_data.append(data_batch)
    
    # 3. 推送回去 (Push)
    try:
        new_content = json.dumps(existing_data, indent=2, ensure_ascii=False)
        b64_content = base64.b64encode(new_content.encode('utf-8')).decode('utf-8')
        
        payload = {
            "message": f"🤖 Reddit Update: {now.strftime('%H:%M')}",
            "content": b64_content,
            "branch": "main"
        }
        if sha: payload["sha"] = sha
        
        requests.put(api_url, headers=headers, json=payload)
        logger.info(f"✅ Data synced to {path}")
    except Exception as e:
        logger.error(f"Sync failed: {e}")

def run():
    # 1. 领任务
    missions = fetch_missions()
    if not missions:
        logger.info("💤 No missions found in Issues.")
        return
        
    logger.info(f"🛡️ Missions accepted: {list(missions.keys())}")
    
    batch_results = []
    
    # 2. 执行任务
    for sub, keywords in missions.items():
        try:
            # 调用 Pipeline
            df = top_posts_subreddit_pipeline(sub, POOL_SIZE, COMMENT_LIMIT, "Hot")
            if df.empty: continue
            
            # 选出 Champion (得分最高的 5 个)
            # rank_score = 基础热度(score) * 情绪强度(abs(vibe))
            # 注意：vibe_val 在 pipeline 里已经算好了
            df['rank_score'] = df['score'] * (df['vibe_val'].abs() + 0.1)
            champions = df.sort_values('rank_score', ascending=False).head(5)
            
            post_list = []
            for _, row in champions.iterrows():
                post_list.append({
                    "title": row['title'],
                    "url": row['url'],
                    "score": int(row['score']),
                    "vibe": float(row['vibe_val']), # 情绪分
                    "summary": row['clean_text'][:100] # 摘要
                })
            
            batch_results.append({
                "subreddit": sub,
                "avg_sentiment": float(df['vibe_val'].mean()),
                "champions": post_list
            })
            
        except Exception as e:
            logger.error(f"Failed to process r/{sub}: {e}")
            
    # 3. 上传结果
    if batch_results:
        payload = {
            "timestamp": datetime.now(timezone(timedelta(hours=8))).isoformat(),
            "data": batch_results
        }
        sync_to_central_bank(payload)

if __name__ == "__main__":
    run()
