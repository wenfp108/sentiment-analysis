import pandas as pd
import json
import logging
import os
import requests
from datetime import datetime

# 引入项目现有模块
from src.pipelines import top_posts_subreddit_pipeline
from src.logger_config import setup_logger
from src.eda import get_top_n_words

logger = setup_logger()

# === 影子指挥中心配置 ===
COMMAND_REPO = "wenfp108/Central-Bank"  # 你的私人指令库
OUTPUT_FILE = "sentiment_report.json"
POST_LIMIT = 15      # 每个板块抓取贴数
COMMENT_LIMIT = 30   # 每个帖子评论分析数

def fetch_missions_from_shadow_hq():
    """
    去 GitHub Issue 拿任务
    """
    # 优先使用 GH_PAT (在 Secrets 里配置)，其次 GITHUB_TOKEN
    token = os.environ.get("GITHUB_TOKEN")
    
    if not token:
        logger.error("❌ 缺少 GITHUB_TOKEN，无法连接指挥中心！")
        return {}

    url = f"https://api.github.com/repos/{COMMAND_REPO}/issues?state=open&per_page=100"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.v3+json"
    }

    logger.info(f"📡 正在连接: {COMMAND_REPO} ...")
    
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        issues = resp.json()
        
        missions = {}
        
        for issue in issues:
            title = issue.get('title', '').strip()
            
            # 🎯 识别 [reddit]
            if '[reddit]' in title.lower():
                # 1. 提取板块名 (去掉标签)
                subreddit = title.lower().replace('[reddit]', '').strip()
                
                # 2. 提取关键词 (直接读正文，用逗号分隔)
                body = issue.get('body', '')
                if body:
                    keywords = [k.strip() for k in body.replace('，', ',').replace('\n', ',').split(',') if k.strip()]
                else:
                    keywords = [] # 正文没写就不筛关键词
                
                missions[subreddit] = keywords
                logger.info(f"📥 领取任务: r/{subreddit} | 关键词: {keywords if keywords else '无 (全量模式)'}")

        logger.info(f"✅ 获取到 {len(missions)} 个板块任务。")
        return missions

    except Exception as e:
        logger.error(f"❌ 连接失败: {e}")
        return {}

def calculate_distribution(df):
    """计算情绪分布"""
    if df.empty:
        return {"POSITIVE": "0%", "NEGATIVE": "0%", "NEUTRAL": "0%"}
    col_name = 'sentiment_clean_title_label'
    if col_name not in df.columns:
        return {"Error": "Column not found"}
    counts = df[col_name].value_counts(normalize=True)
    return {
        "POSITIVE": f"{counts.get('pos', 0):.0%}",
        "NEGATIVE": f"{counts.get('neg', 0):.0%}",
        "NEUTRAL":  f"{counts.get('neu', 0):.0%}"
    }

def run_mission():
    final_report = []
    
    # 1. 领任务
    monitor_matrix = fetch_missions_from_shadow_hq()
    
    if not monitor_matrix:
        logger.warning("🚫 指挥中心没有 [reddit] 任务。")
        return

    logger.info("🚀 Woonbot 启动...")

    # 2. 跑任务
    for subreddit, keywords in monitor_matrix.items():
        logger.info(f"📡 正在抓取 r/{subreddit} (Hot模式) ...")
        
        try:
            # === 🔥 调用管道 ===
            # 这里调用 src/pipelines.py，它会透传 posts_to_get 给你的底层代码
            df = top_posts_subreddit_pipeline(
                subreddit_name=subreddit,
                post_limit=POST_LIMIT,
                comment_limmit=COMMENT_LIMIT,
                posts_to_get="Hot"  # <--- 关键：使用你新加的 Hot 模式
            )
            
            if df.empty:
                logger.warning(f"⚠️ r/{subreddit} 没抓到数据")
                continue

            dist = calculate_distribution(df)
            top_words_raw = get_top_n_words(df, 'clean_title', n=5)
            top_keywords = [word for word, count in top_words_raw]

            raw_samples = []
            for _, row in df.head(5).iterrows():
                # 只有当 keywords 存在时才去匹配高亮
                if keywords:
                    matched_entities = [k for k in keywords if k.lower() in row['title'].lower()]
                else:
                    matched_entities = []
                
                raw_samples.append({
                    "title": row['title'],
                    "sentiment_label": row.get('sentiment_clean_title_label', 'unknown').upper(),
                    "sentiment_score": round(row.get('sentiment_clean_title_score', 0), 3),
                    "key_entities": matched_entities if matched_entities else ["General"]
                })

            subreddit_report = {
                "timestamp": datetime.utcnow().isoformat(),
                "subreddit": subreddit,
                "summary": {
                    "sentiment_distribution": dist,
                    "top_keywords": top_keywords
                },
                "raw_data_sample": raw_samples
            }
            
            final_report.append(subreddit_report)
            logger.info(f"✅ r/{subreddit} 完成")

        except Exception as e:
            logger.error(f"❌ r/{subreddit} 出错: {e}")

    # 3. 存数据
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(final_report, f, indent=4, ensure_ascii=False)
    
    logger.info(f"🎉 任务结束，结果已保存至 {OUTPUT_FILE}")

if __name__ == "__main__":
    run_mission()
