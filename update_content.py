import json
import requests
import feedparser # 专门用来解析新闻RSS的库
import datetime
import os
import time

# --- 配置部分 ---
GAME_FEED_URL = "https://gamemonetize.com/rss.php?format=json"
# 这里使用 IGN 的游戏新闻源 (你也可以换成 GameSpot 或 Kotaku)
NEWS_RSS_URL = "https://feeds.ign.com/ign/news" 
BASE_DIR = "fungames.today/MyGameSite"

# --- 1. 游戏更新模块 ---
def update_games():
    print("🎮 正在抓取新游戏...")
    data_dir = os.path.join(BASE_DIR, 'data')
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)

    headers = { 'User-Agent': 'Mozilla/5.0' }
    try:
        response = requests.get(GAME_FEED_URL, headers=headers, timeout=15)
        if response.status_code == 200:
            new_games = response.json()[:20] # 取前20个
            with open(os.path.join(data_dir, 'games.json'), 'w', encoding='utf-8') as f:
                json.dump(new_games, f, ensure_ascii=False, indent=2)
            print(f"✅ 游戏更新成功: {len(new_games)} 个")
            return len(new_games)
    except Exception as e:
        print(f"❌ 游戏更新失败: {e}")
        return 0

# --- 2. 新闻更新模块 (只增不减) ---
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

# --- 主程序 ---
if __name__ == "__main__":
    game_count = update_games()
    news_count = update_news()
    
    # 生成通知数据
    meta_data = {
        "last_update": datetime.datetime.now().strftime("%Y-%m-%d"),
        "new_count": game_count,
        "news_count": news_count, # 记录新闻数量
        "notification": f"Update: {game_count} Games & {news_count} News Added!"
    }
    
    with open(os.path.join(BASE_DIR, 'data', 'meta.json'), 'w', encoding='utf-8') as f:
        json.dump(meta_data, f, ensure_ascii=False)
