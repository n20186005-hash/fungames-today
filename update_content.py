import json
import requests
import datetime
import os

# --- 配置部分 ---
GAME_FEED_URL = "https://gamemonetize.com/rss.php?format=json"
# 注意：根据你的截图，你的文件夹名现在是 "MyGameSite"，所以我改成了这个
BASE_DIR = "fungames.today/MyGameSite"

# --- 核心功能 ---
def update_games():
    print("正在抓取新游戏...")
    
    # 1. 确保目录存在
    data_dir = os.path.join(BASE_DIR, 'data')
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)

    # 2. 准备伪装头部 (User-Agent) 防止被拦截
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }

    try:
        # 发送请求
        response = requests.get(GAME_FEED_URL, headers=headers, timeout=15)
        
        # 3. 检查是否成功
        if response.status_code == 200:
            games_data = response.json()
            new_games = games_data[:20]  # 取前20个
            
            # 保存 games.json
            file_path = os.path.join(data_dir, 'games.json')
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(new_games, f, ensure_ascii=False, indent=2)
                
            print(f"✅ 成功！已保存 {len(new_games)} 个游戏到 {file_path}")
            return len(new_games)
        else:
            print(f"❌ 下载失败，状态码: {response.status_code}")
            return 0
            
    except Exception as e:
        print(f"❌ 发生错误: {e}")
        return 0

# --- 主程序 ---
if __name__ == "__main__":
    # 执行更新
    count = update_games()
    
    # 生成通知数据
    meta_data = {
        "last_update": datetime.datetime.now().strftime("%Y-%m-%d"),
        "new_count": count,
        "notification": f"今日已更新 {count} 款新游戏！"
    }
    
    # 保存 meta.json
    meta_path = os.path.join(BASE_DIR, 'data', 'meta.json')
    with open(meta_path, 'w', encoding='utf-8') as f:
        json.dump(meta_data, f, ensure_ascii=False)
    
    print("任务结束。")
