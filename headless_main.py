import pandas as pd
import json
import logging
import os
import requests
import base64
import numpy as np
from datetime import datetime
from textblob import TextBlob

# 引入项目现有模块
from src.pipelines import top_posts_subreddit_pipeline
from src.logger_config import setup_logger

logger = setup_logger()

# === 🏦 中央银行配置 ===
COMMAND_REPO = "wenfp108/Central-Bank"
# 🔥 [核心修改] 路径调整为 reddit/sentiment
OUTPUT_ROOT = "reddit/sentiment"          
POOL_SIZE = 15
CHAMPION_COUNT = 5
COMMENT_LIMIT = 20

def get_github_headers():
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        logger.error("❌ 缺少 GITHUB_TOKEN，无法连接银行！")
        return None
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.v3+json",
        "Content-Type": "application/json"
    }

def fetch_missions():
    """1. 领任务"""
    headers = get_github_headers()
    if not headers: return {}
    try:
        url = f"https://api.github.com/repos/{COMMAND_REPO}/issues?state=open&per_page=100"
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        
        missions = {i['title'].lower().replace('[reddit]', '').strip(): 
                    ([k.strip() for k in i.get('body', '').replace('，', ',').replace('\n', ',').split(',') if k.strip()] if i.get('body') else [])
                    for i in resp.json() if '[reddit]' in i.get('title', '').lower()}
        return missions
    except Exception as e:
        logger.error(f"❌ 领任务失败: {e}")
        return {}

def analyze_vibe(comments):
    if not comments: return 0.0
    scores = [TextBlob(c.get('body', '')).sentiment.polarity for c in comments[:COMMENT_LIMIT] if c.get('body')]
    return np.mean(scores) if scores else 0.0

def detect_anomalies(current_posts, daily_history):
    """2. 异动检测"""
    history_map = {}
    for entry in daily_history:
        for sector in entry.get('data', []):
            for p in sector.get('champions', []):
                history_map[p['title']] = p['vibe']

    for p in current_posts:
        if p['title'] in history_map:
            prev_vibe = history_map[p['title']]
            delta = p['vibe'] - prev_vibe
            if (prev_vibe > 0 and p['vibe'] < 0) or (prev_vibe < 0 and p['vibe'] > 0):
                p['anomaly'] = {"type": "REVERSAL", "prev": round(prev_vibe, 3), "delta": round(delta, 3)}
            elif abs(delta) > 0.4:
                p['anomaly'] = {"type": "SHARP_DRIFT", "prev": round(prev_vibe, 3), "delta": round(delta, 3)}
    return current_posts

def sync_to_central_bank(new_time_data):
    """
    3. 银行同步协议 (Pull -> Merge -> Push)
    目标路径: reddit/sentiment/2026-01-31.json
    """
    headers = get_github_headers()
    if not headers: return

    today_str = datetime.utcnow().strftime('%Y-%m-%d')
    
    # 🔥 远程路径: reddit/sentiment/2026-01-31.json
    remote_path = f"{OUTPUT_ROOT}/{today_str}.json"
    api_url = f"https://api.github.com/repos/{COMMAND_REPO}/contents/{remote_path}"

    logger.info(f"🏦 正在连接中央银行，同步路径: {remote_path} ...")

    # A. 侦查 (Pull)
    daily_history = []
    sha = None
    try:
        resp = requests.get(api_url, headers=headers, timeout=10)
        if resp.status_code == 200:
            file_data = resp.json()
            sha = file_data['sha']
            content_b64 = file_data['content']
            daily_history = json.loads(base64.b64decode(content_b64).decode('utf-8'))
            logger.info(f"✅ 成功拉取今日底稿: {len(daily_history)} 条记录")
        else:
            logger.info("🆕 今日首条数据，创建新账本")
    except Exception as e:
        logger.warning(f"⚠️ 拉取数据异常 (视为新文件): {e}")

    # B. 融合 (Merge)
    for sector in new_time_data['data']:
        sector['champions'] = detect_anomalies(sector['champions'], daily_history)
    
    daily_history.append(new_time_data)

    # C. 存证 (Push)
    try:
        final_content = json.dumps(daily_history, indent=4, ensure_ascii=False)
        final_b64 = base64.b64encode(final_content.encode('utf-8')).decode('utf-8')
        
        payload = {
            "message": f"📊 Reddit Sentinel Update: {new_time_data['time']}",
            "content": final_b64,
            "branch": "main"
        }
        if sha:
            payload["sha"] = sha

        put_resp = requests.put(api_url, headers=headers, json=payload, timeout=15)
        put_resp.raise_for_status()
        logger.info(f"🚀 上传成功！数据已存入: {remote_path}")
        
    except Exception as e:
        logger.error(f"❌ 上传失败: {e}")

    # D. 本地留底
    try:
        # 本地也保持结构一致: data/reddit/sentiment/2026-01-31.json
        # 注意: 本地我们通常存 data/ 下方便 debug，这里我加个前缀 data/
        local_dir = os.path.join("data", OUTPUT_ROOT)
        os.makedirs(local_dir, exist_ok=True)
        local_file = os.path.join(local_dir, f"{today_str}.json")
        
        with open(local_file, 'w', encoding='utf-8') as f:
            json.dump(daily_history, f, indent=4, ensure_ascii=False)
        logger.info(f"💾 本地备份已生成: {local_file}")
    except: pass

def run_mission():
    missions = fetch_missions()
    if not missions:
        logger.warning("💤 无任务")
        return

    logger.info(f"🛡️ Woonbot 启动... 目标: {len(missions)} 板块")
    
    current_batch_data = []

    for sub, kws in missions.items():
        try:
            logger.info(f"📡 扫描 r/{sub} ...")
            df = top_posts_subreddit_pipeline(sub, POOL_SIZE, COMMENT_LIMIT, "Hot")
            if df.empty: continue

            df['title_signed'] = df.apply(lambda x: -x['sentiment_clean_title_score'] if x.get('sentiment_clean_title_label') == 'NEGATIVE' else x['sentiment_clean_title_score'], axis=1)
            df['vibe'] = (df['title_signed'] * 0.4) + (df['comments'].apply(analyze_vibe) * 0.6)
            df['rank_score'] = (df['score'] / (df['score'].max() + 1)) * 0.6 + abs(df['vibe']) * 0.4
            champions = df.sort_values(by='rank_score', ascending=False).head(CHAMPION_COUNT)

            post_list = [{"title": r['title'], "vibe": round(r['vibe'], 3), "pop": int(r['score'])} for _, r in champions.iterrows()]

            current_batch_data.append({
                "sub": sub,
                "sentiment": round(df['vibe'].mean(), 3),
                "champions": post_list
            })
        except Exception as e: logger.error(f"Error {sub}: {e}")

    if current_batch_data:
        sync_to_central_bank({
            "time": datetime.utcnow().strftime('%H:%M'),
            "data": current_batch_data
        })

if __name__ == "__main__":
    run_mission()
