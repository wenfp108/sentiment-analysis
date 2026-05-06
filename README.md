# Sentiment Analysis

> Reddit 社区情绪采集 + 情感分析系统

## 架构

```
Central-Bank Issues [reddit] 标签
         │
    ┌────▼─────────────┐
    │ headless_main.py │  (生产：Serv00 / Actions)
    │  读取 Issues     │
    │  抓取 Reddit     │
    │  TextBlob 分析   │
    │  同步到央行      │
    └──────────────────┘
         │
    ┌────▼──────────────────────────────┐
    │       Docker 架构 (实验)           │
    │  producer → RabbitMQ → consumer   │
    │  → model-server (DistilBERT)      │
    │  → MongoDB                        │
    │  → Streamlit 可视化               │
    └───────────────────────────────────┘
```

## 生产流程 (headless_main.py)

```
1. 读取 Central-Bank Issues 的 [reddit] 标签 → 获取 subreddit 列表
2. 对每个 subreddit：抓取 Hot 帖子 → TextBlob 情感分析 → 排序取 Top 5
3. 打包结果 → GitHub API 写入 Central-Bank
```

### 数据采集 (get_reddit_data.py)

通过镜像站抓取 Reddit 数据，不依赖官方 API：
- 多镜像站轮询（old.reddit、redlib 等）
- 随机打乱顺序防封
- 超时自动切换

### 情感分析 (pipelines.py)

使用 TextBlob 进行轻量级情感分析：
- `vibe_val`：情感极性，范围 -1（负面）到 +1（正面）
- 基于规则而非深度学习，速度快，适合高频采集

### 排序逻辑

```python
rank_score = post_score × (|vibe_val| + 0.1)
```

取每个 subreddit 的 Top 5 champions 写入 Central-Bank。

## Docker 架构 (实验性)

独立的实时处理流水线，当前未在 Actions 中运行：

| 组件 | 用途 |
|------|------|
| `reddit-producer` | PRAW 实时抓取 → RabbitMQ |
| `reddit-consumer` | RabbitMQ → DistilBERT 推理 → MongoDB |
| `model-server` | DistilBERT 模型服务 (FastAPI) |
| `streamlit-app` | 可视化面板 |

## 关联仓库

| 仓库 | 用途 |
|------|------|
| [sentiment-analysis](https://github.com/wenfp108/sentiment-analysis) | 本仓库。Reddit 采集 + 分析 |
| [Central-Bank](https://github.com/wenfp108/Central-Bank) | 数据存储（Issues 指令 + 数据归档） |
| [Refinery-Engine](https://github.com/wenfp108/refinery-erngine) | 下游：从 Central-Bank 读取 Reddit 数据做 AI 审计 |

## 环境变量

| 变量 | 用途 |
|------|------|
| `GITHUB_TOKEN` / `GH_PAT` | GitHub API（读 Issues + 写数据） |

## 环境

- **Runner**: Serv00 服务器 (主) / GitHub Actions (备用)
- **Engine**: Python 3.9
- **依赖**: TextBlob, requests, transformers (DistilBERT, Docker 模式用)
