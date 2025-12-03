import json
import requests
import feedparser # 专门用来解析新闻RSS的库
import datetime
import os
import time
import subprocess
import traceback

# --- 配置部分 ---
GAME_FEED_URL = "https://gamemonetize.com/rss.php?format=json"
# 这里使用 IGN 的游戏新闻源 (你也可以换成 GameSpot 或 Kotaku)
NEWS_RSS_URL = "https://feeds.ign.com/ign/news"
BASE_DIR = "fungames.today/MyGameSite"

# --- 1. 游戏更新模块（已修改：改为合并+去重，并为新条目添加 added_at） ---
def update_games():
    print("🎮 正在抓取新游戏...")
    data_dir = os.path.join(BASE_DIR, 'data')
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)

    headers = { 'User-Agent': 'Mozilla/5.0' }
    try:
        response = requests.get(GAME_FEED_URL, headers=headers, timeout=15)
        if response.status_code == 200:
            # 尝试解析出一个列表（原来是直接 response.json()[:20] 覆盖）
            resp_json = response.json()
            # 如果返回的是 dict 且包含列表字段，尽量获取列表
            new_games_raw = []
            if isinstance(resp_json, list):
                new_games_raw = resp_json
            elif isinstance(resp_json, dict):
                # 常见字段名尝试
                for k in ('items', 'data', 'results', 'games', 'rows', 'feed'):
                    if k in resp_json and isinstance(resp_json[k], list):
                        new_games_raw = resp_json[k]
                        break
                # fallback: 把 dict 当作单个元素
                if not new_games_raw:
                    # 如果 dict 里有列表字段，取第一个列表
                    for v in resp_json.values():
                        if isinstance(v, list):
                            new_games_raw = v
                            break
                    if not new_games_raw:
                        # 最后退回把整个 dict 当作单项
                        new_games_raw = [resp_json]
            else:
                new_games_raw = []

            # 只取前 50 条以防过大（需要时可调整）
            new_games_raw = new_games_raw[:50]

            # 规范化条目：尽量取 url/title/thumbnail/description/category
            def normalize(raw):
                if not isinstance(raw, dict):
                    return None
                url = None
                for key in ('url','link','game_url','gameLink','page','href'):
                    if key in raw and raw[key]:
                        url = raw[key]
                        break
                # 尝试嵌套字段
                if not url:
                    for nk in ('data','item','attributes'):
                        if nk in raw and isinstance(raw[nk], dict):
                            for key in ('url','link'):
                                if key in raw[nk] and raw[nk][key]:
                                    url = raw[nk][key]
                                    break
                            if url:
                                break
                if not url:
                    return None
                title = raw.get('title') or raw.get('name') or url
                thumbnail = raw.get('thumbnail') or raw.get('thumb') or raw.get('image') or ''
                description = raw.get('description') or raw.get('desc') or ''
                category = raw.get('category') or raw.get('tag') or ''
                return {
                    'url': url,
                    'title': title,
                    'thumbnail': thumbnail,
                    'description': description,
                    'category': category
                }

            fetched = []
            for r in new_games_raw:
                n = normalize(r)
                if n:
                    fetched.append(n)

            games_file = os.path.join(data_dir, 'games.json')
            existing = []
            if os.path.exists(games_file):
                try:
                    with open(games_file, 'r', encoding='utf-8') as f:
                        existing = json.load(f)
                except Exception as e:
                    print("⚠️ 读取已有 games.json 失败，将从空列表开始:", e)

            existing_map = { item.get('url'): item for item in existing if item.get('url') }
            added = 0
            for g in fetched:
                url = g['url']
                if url in existing_map:
                    # 已存在，跳过（若你想更新字段可在此合并）
                    continue
                entry = {
                    'url': url,
                    'title': g.get('title') or url,
                    'description': g.get('description',''),
                    'thumbnail': g.get('thumbnail',''),
                    'category': g.get('category',''),
                    'added_at': datetime.datetime.utcnow().isoformat() + 'Z'
                }
                existing.append(entry)
                existing_map[url] = entry
                added += 1

            # 按时间降序保存
            existing.sort(key=lambda x: x.get('added_at',''), reverse=True)
            with open(games_file, 'w', encoding='utf-8') as f:
                json.dump(existing, f, ensure_ascii=False, indent=2)

            print(f"✅ 游戏更新完成（合并写入），新增 {added} 条")
            return added
        else:
            print(f"❌ 请求游戏源失败，状态码 {response.status_code}")
            return 0
    except Exception as e:
        print("❌ 游戏更新失败:", e)
        traceback.print_exc()
        return 0

# --- 2. 新闻更新模块 (原样保留：未做改动) ---
def update_news():
    print("📰 正在抓取新闻...")
    data_dir = os.path.join(BASE_DIR, 'data')
    news_file = os.path.join(data_dir, 'news.json')
    
    # A. 先读取旧新闻（如果存在）
    existing_news = []
    if os.path.exists(news_file):
        try:
            with open(news_file, 'r', encoding='utf-8') as f:
                existing_news = json.load(f)
        except:
            existing_news = []
    
    # B. 抓取新新闻
    try:
        feed = feedparser.parse(NEWS_RSS_URL)
        new_items = []
        
        # 建立一个旧标题的集合，用来查重
        existing_titles = {item['title'] for item in existing_news}
        
        for entry in feed.entries:
            # 如果这篇新闻之前没存过，才添加
            if entry.title not in existing_titles:
                # 提取图片 (RSS里图片通常在 media_content 或 summary 里，这里做个简单处理)
                image_url = ""
                if 'media_content' in entry:
                    image_url = entry.media_content[0]['url']
                
                news_item = {
                    "title": entry.title,
                    "date": datetime.datetime.now().strftime("%Y-%m-%d"), # 记录今天日期
                    "desc": entry.summary[:150] + "...", # 只取前150个字
                    "tag": "News", # 默认标签
                    "source": "IGN", # 来源
                    "link": entry.link # 原文链接
                }
                new_items.append(news_item)
        
        if new_items:
            # C. 把新新闻加到最前面 (Prepend)
            final_news = new_items + existing_news
            
            # 为了防止文件无限大，我们可以只保留最近 100 条 (可选)
            final_news = final_news[:100]
            
            with open(news_file, 'w', encoding='utf-8') as f:
                json.dump(final_news, f, ensure_ascii=False, indent=2)
            print(f"✅ 新增了 {len(new_items)} 条新闻！")
            return len(new_items)
        else:
            print("💤 没有发现新新闻。")
            return 0
            
    except Exception as e:
        print(f"❌ 新闻更新失败: {e}")
        return 0

# --- 主程序：保持你原本逻辑写 meta，但是现在使用合并后的游戏数量和新闻数量 ---
if __name__ == "__main__":
    try:
        games_added = update_games()
        news_added = update_news()
    except Exception as e:
        print("❌ 更新过程中发生异常:", e)
        games_added = 0
        news_added = 0

    # 确保 data 目录存在，然后写 meta.json（和你原来写 meta 的信息相同）
    meta_dir = os.path.join(BASE_DIR, 'data')
    if not os.path.exists(meta_dir):
        os.makedirs(meta_dir)

    meta_data = {
        "last_update": datetime.datetime.now().strftime("%Y-%m-%d"),
        "new_count": games_added,
        "news_count": news_added, # 记录新闻数量
        "notification": f"Update: {games_added} Games & {news_added} News Added!"
    }

    meta_path = os.path.join(meta_dir, 'meta.json')
    with open(meta_path, 'w', encoding='utf-8') as f:
        json.dump(meta_data, f, ensure_ascii=False, indent=2)

    print(f"🔔 写入 meta: {meta_path}")

    # 如果有新增，则尝试提交并推送（在 Actions 中需要 permissions: contents: write）
    if games_added > 0 or news_added > 0:
        try:
            subprocess.run(['git', 'config', 'user.email', 'actions@users.noreply.github.com'], check=True)
            subprocess.run(['git', 'config', 'user.name', 'github-actions'], check=True)
            paths = [os.path.join(BASE_DIR, 'data', 'games.json'),
                     os.path.join(BASE_DIR, 'data', 'news.json'),
                     os.path.join(BASE_DIR, 'data', 'meta.json')]
            subprocess.run(['git', 'add'] + paths, check=True)
            subprocess.run(['git', 'commit', '-m', f'Auto update: +{games_added} games +{news_added} news'], check=False)
            subprocess.run(['git', 'push'], check=False)
            print("✅ 尝试执行 git push（如果 workflow 有权限则会成功）")
        except Exception as e:
            print("⚠️ 尝试 git push 失败：", e)
            traceback.print_exc()
    else:
        print("ℹ️ 本次无新增内容，跳过提交。")
