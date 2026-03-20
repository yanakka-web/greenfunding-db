"""
既存プロジェクトのサポーター数を更新
"""
import requests
from bs4 import BeautifulSoup
import sqlite3
import re
import time

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
}

def parse_supporters(text):
    """サポーター数をパース"""
    if not text:
        return 0
    nums = re.sub(r"[^\d]", "", text)
    return int(nums) if nums else 0

def get_supporters_from_page(url, session):
    """プロジェクトページからサポーター数を取得"""
    try:
        resp = session.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        
        # 方法1: 「支援人数」というテキストの近くを探す
        text = soup.get_text()
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        
        for i, line in enumerate(lines):
            if "支援人数" in line or "支援者数" in line:
                # 次の行に数字がある可能性
                if i + 1 < len(lines):
                    next_line = lines[i + 1]
                    nums = re.sub(r"[^\d]", "", next_line)
                    if nums:
                        return int(nums)
        
        # 方法2: 「○○人」というパターンを探す
        supporter_texts = soup.find_all(string=re.compile(r"\d+\s*人"))
        for text in supporter_texts:
            # 「支援」という文字の近くにあるか確認
            parent_text = text.parent.get_text() if text.parent else ""
            if "支援" in parent_text or len(supporter_texts) <= 3:
                nums = re.sub(r"[^\d]", "", text)
                if nums:
                    return int(nums)
        
        return 0
    except Exception as e:
        print(f"    エラー: {e}")
        return 0

def main():
    print("=" * 60)
    print("サポーター数更新スクリプト")
    print("=" * 60)
    
    conn = sqlite3.connect("greenfunding.db")
    c = conn.cursor()
    
    # サポーター0人のプロジェクトを取得
    projects = c.execute("""
        SELECT id, project_id, url, title 
        FROM projects 
        WHERE supporters = 0
        ORDER BY id
    """).fetchall()
    
    total = len(projects)
    print(f"\n更新対象: {total}件\n")
    
    session = requests.Session()
    updated = 0
    
    for idx, (db_id, project_id, url, title) in enumerate(projects, 1):
        print(f"[{idx}/{total}] ID:{project_id} - {title[:40]}...", end=" ")
        
        supporters = get_supporters_from_page(url, session)
        
        if supporters > 0:
            c.execute("UPDATE projects SET supporters = ? WHERE id = ?", (supporters, db_id))
            conn.commit()
            updated += 1
            print(f"✅ {supporters}人")
        else:
            print("⚠️ 取得失敗")
        
        # 進捗表示
        if idx % 100 == 0:
            print(f"\n  --- 進捗: {idx}/{total} ({idx/total*100:.1f}%) | 更新済み: {updated}件 ---\n")
        
        # レート制限対策
        time.sleep(1.5)
    
    print("\n" + "=" * 60)
    print(f"✅ 完了！ {updated}件のサポーター数を更新しました")
    print("=" * 60)
    
    conn.close()

if __name__ == "__main__":
    main()