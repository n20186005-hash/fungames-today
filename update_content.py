import json
import requests
import datetime
import os

# --- 配置部分 ---
# 这里使用 GameMonetize 的 RSS (你需要去注册申请自己的 feed url)
GAME_FEED_URL = "https://gamemonetize.com/rss.php?format=json" 
# 你的网站文件实际所在的文件夹名字
BASE_DIR = "fungames.today/MyGameSite"

# --- 核心功能 ---
def update_games():
    print("正在抓取新游戏...")
    # 确保 data 文件夹存在
    data_dir = os.path.join(BASE_DIR, 'data')
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)

    try:
        response = requests.get(GAME_FEED_URL, timeout=10)
        if response.status_code == 200:
            games_data = response.json()
            new_games = games_data[:20]  # 取前20个
            
            # 保存到 data/games.json
            file_path = os.path.join(data_dir, 'games.json')
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(new_games, f, ensure_ascii=False, indent=2)
            print(f"成功更新 {len(new_games)} 个游戏到 {file_path}")
            return len(new_games)
    except Exception as e:
        print(f"更新失败: {e}")
        return 0

# --- 主程序 ---
if __name__ == "__main__":
    count = update_games()
    
    # 生成通知数据
    meta_data = {
        "last_update": datetime.datetime.now().strftime("%Y-%m-%d"),
        "new_count": count,
        "notification": f"今日已更新 {count} 款新游戏！"
    }
    
    # 保存通知数据
    meta_path = os.path.join(BASE_DIR, 'data', 'meta.json')
    with open(meta_path, 'w', encoding='utf-8') as f:
        json.dump(meta_data, f, ensure_ascii=False)
    
    print("更新完成！")
