import json
import requests
import feedparser
import datetime
import os
import time
import subprocess
import traceback
import shutil

# --- 配置部分 ---
# 备用 URL，如果 rss.php 挂了可以尝试 feed.php
GAME_FEED_URL = "https://gamemonetize.com/rss.php?format=json" 
NEWS_RSS_URL = "https://feeds.ign.com/ign/news"
BASE_DIR = "fungames.today/MyGameSite"

# --- 1. 游戏更新模块 (修复版) ---
def update_games():
    print("🎮 正在抓取新游戏...")
    data_dir = os.path.join(BASE_DIR, 'data')
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)

    # 1. 安全读取旧数据
    games_file = os.path.join(data_dir, 'games.json')
    existing = []
    load_success = False # 标记读取是否成功

    if os.path.exists(games_file):
        try:
            with open(games_file, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if content:
                    existing = json.loads(content)
                    load_success = True
                else:
                    print("⚠️ games.json 为空，将初始化为空列表")
                    existing = []
                    load_success = True # 空文件也是一种“成功”状态
        except Exception as e:
            print(f"❌ 严重错误：读取 games.json 失败！为了防止数据丢失，脚本将终止游戏更新。\n错误信息: {e}")
            return 0 # 直接返回，不执行后续的写入操作
    else:
        print("ℹ️ games.json 不存在，将创建新文件")
        existing = []
        load_success = True

    # 2. 抓取新数据
    # 使用更真实的浏览器 UA，防止被拦截
    headers = { 
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Referer': 'https://gamemonetize.com/',
        'Accept': 'application/json, text/plain, */*'
    }
    
    fetched = []
    try:
        response = requests.get(GAME_FEED_URL, headers=headers, timeout=30)
        print(f"📡 请求状态码: {response.status_code}")
        
        if response.status_code == 200:
            try:
                resp_json = response.json()
            except json.JSONDecodeError:
                print("❌ 源站返回的不是有效的 JSON，可能是服务器维护或被拦截 (返回了 HTML)。")
                return 0

            new_games_raw = []
            # 智能解析各种可能的 JSON 结构
            if isinstance(resp_json, list):
                new_games_raw = resp_json
            elif isinstance(resp_json, dict):
                # 尝试常见的字段名
                for k in ['items', 'games', 'data', 'feed']:
                    if k in resp_json and isinstance(resp_json[k], list):
                        new_games_raw = resp_json[k]
                        break
                if not new_games_raw:
                    new_games_raw = [resp_json] # 可能是单条数据

            # 数据清洗函数
            def normalize(raw):
                if not isinstance(raw, dict): return None
                # 寻找 URL
                url = raw.get('url') or raw.get('link') or raw.get('game_url')
                if not url: return None
                
                return {
                    'url': url,
                    'title': raw.get('title') or raw.get('name') or "Unknown Game",
                    'thumbnail': raw.get('thumbnail') or raw.get('thumb') or '',
                    'description': raw.get('description') or raw.get('desc') or '',
                    'category': raw.get('category') or raw.get('tag') or 'Arcade',
                }

            # 处理抓取到的数据
            for r in new_games_raw[:60]: # 取前60条
                n = normalize(r)
                if n: fetched.append(n)
            
            print(f"✅ 从源站成功获取 {len(fetched)} 个游戏")

        else:
            print(f"❌ 请求失败，服务器返回: {response.status_code}")
            return 0

    except Exception as e:
        print("❌ 网络请求或解析阶段出错:", e)
        traceback.print_exc()
        return 0

    # 3. 合并与保存 (只有读取成功且抓取过程没崩溃才执行)
    if load_success:
        existing_map = {item.get('url'): item for item in existing}
        added_count = 0
        
        for g in fetched:
            url = g['url']
            if url not in existing_map:
                entry = {
                    'url': url,
                    'title': g['title'],
                    'description': g['description'],
                    'thumbnail': g['thumbnail'],
                    'category': g['category'],
                    'added_at': datetime.datetime.utcnow().isoformat() + 'Z'
                }
                existing.append(entry)
                existing_map[url] = entry
                added_count += 1
        
        if added_count > 0:
            # 备份旧文件（安全措施）
            if os.path.exists(games_file):
                shutil.copy(games_file, games_file + ".bak")
            
            # 按时间倒序
            existing.sort(key=lambda x: x.get('added_at', ''), reverse=True)
            
            # 写入
            with open(games_file, 'w', encoding='utf-8') as f:
                json.dump(existing, f, ensure_ascii=False, indent=2)
            
            print(f"💾 成功写入文件，新增 {added_count} 个游戏！")
            return added_count
        else:
            print("ℹ️ 没有新游戏需要添加。")
            return 0
    else:
        print("⚠️ 由于此时无法安全读取旧数据，本次跳过写入，以保护数据。")
        return 0

# --- 2. 新闻更新模块 (保持原样即可，略微优化 headers) ---
def update_news():
    print("📰 正在抓取新闻...")
    data_dir = os.path.join(BASE_DIR, 'data')
    news_file = os.path.join(data_dir, 'news.json')
    
    existing_news = []
    if os.path.exists(news_file):
        try:
            with open(news_file, 'r', encoding='utf-8') as f:
                existing_news = json.load(f)
        except:
            existing_news = []
            
    try:
        # 增加 headers 防止 RSS 403
        feed = feedparser.parse(NEWS_RSS_URL, request_headers={'User-Agent': 'Mozilla/5.0'})
        new_items = []
        existing_titles = {item['title'] for item in existing_news}
        
        for entry in feed.entries:
            if entry.title not in existing_titles:
                image_url = ""
                if 'media_content' in entry:
                    image_url = entry.media_content[0]['url']
                
                news_item = {
                    "title": entry.title,
                    "date": datetime.datetime.now().strftime("%Y-%m-%d"),
                    "desc": (entry.summary[:150] + "...") if 'summary' in entry else "",
                    "tag": "News",
                    "source": "IGN",
                    "link": entry.link
                }
                new_items.append(news_item)
        
        if new_items:
            final_news = new_items + existing_news
            final_news = final_news[:100]
            with open(news_file, 'w', encoding='utf-8') as f:
                json.dump(final_news, f, ensure_ascii=False, indent=2)
            print(f"✅ 新增 {len(new_items)} 条新闻")
            return len(new_items)
        return 0
    except Exception as e:
        print(f"❌ 新闻更新失败: {e}")
        return 0

# --- 主程序 ---
if __name__ == "__main__":
    try:
        games_added = update_games()
        news_added = update_news()
    except Exception as e:
        print("❌ 主程序异常:", e)
        games_added = 0
        news_added = 0

    # 写入 Meta (即使没有更新也要刷新 last_update 吗？通常建议只有更新了才写，或者保持每天一次)
    meta_dir = os.path.join(BASE_DIR, 'data')
    if not os.path.exists(meta_dir):
        os.makedirs(meta_dir)

    meta_path = os.path.join(meta_dir, 'meta.json')
    
    # 只有当数据真的变动，或者 meta 文件不存在时才更新，避免产生无意义的 commit
    should_update_meta = (games_added > 0 or news_added > 0 or not os.path.exists(meta_path))
    
    if should_update_meta:
        meta_data = {
            "last_update": datetime.datetime.now().strftime("%Y-%m-%d"),
            "new_count": games_added,
            "news_count": news_added,
            "notification": f"Update: {games_added} Games & {news_added} News Added!"
        }
        with open(meta_path, 'w', encoding='utf-8') as f:
            json.dump(meta_data, f, ensure_ascii=False, indent=2)

    # Git 提交逻辑
    if games_added > 0 or news_added > 0:
        try:
            print("🚀 准备提交到 GitHub...")
            subprocess.run(['git', 'config', 'user.email', 'actions@users.noreply.github.com'], check=True)
            subprocess.run(['git', 'config', 'user.name', 'github-actions'], check=True)
            
            files_to_add = [
                os.path.join(BASE_DIR, 'data', 'games.json'),
                os.path.join(BASE_DIR, 'data', 'news.json'),
                os.path.join(BASE_DIR, 'data', 'meta.json')
            ]
            # 过滤掉不存在的文件
            files_to_add = [f for f in files_to_add if os.path.exists(f)]
            
            subprocess.run(['git', 'add'] + files_to_add, check=True)
            subprocess.run(['git', 'commit', '-m', f'Auto update: +{games_added} games +{news_added} news'], check=False)
            subprocess.run(['git', 'push'], check=False)
            print("✅ Git Push 完成")
        except Exception as e:
            print("⚠️ Git 提交失败:", e)
    else:
        print("ℹ️ 无新内容，跳过 Git 提交")
