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
    """把结果作为增量文件存回 Central-Bank"""
    headers = get_github_headers()
    if not headers: return

    # === 🔥 核心修改：生成唯一的时间戳文件名 ===
    # 格式：reddit/sentiment/2026/02/04/120000.json
    now = datetime.now(timezone(timedelta(hours=8)))
    date_path = now.strftime('%Y/%m/%d')
    time_str = now.strftime('%H%M%S')
    
    path = f"{OUTPUT_ROOT}/{date_path}/{time_str}.json"
    api_url = f"https://api.github.com/repos/{COMMAND_REPO}/contents/{path}"
    
    # 直接 Push (上传)，不需要 Pull (拉取旧数据)
    try:
        # 将本次数据包转为 JSON 列表格式，方便 Refinery 统一处理
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
            # rank_score = 基础热度(score) * 情绪强度(abs(vibe) + 0.1)
            # 增加 0.1 是为了防止 vibe 为 0 时 score 被抹平
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
    else:
        logger.info("⚠️ No data fetched this run.")

if __name__ == "__main__":
    run()
