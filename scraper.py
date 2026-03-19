"""
GREEN FUNDING スクレイパー
greenfunding.jp から終了プロジェクトのデータを収集し、SQLiteに保存する
"""

import requests
from bs4 import BeautifulSoup
import sqlite3
import re
import time
import sys

BASE_URL = "https://greenfunding.jp"
SEARCH_URL = f"{BASE_URL}/portals/ranking"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
}

# カテゴリマッピング
CATEGORY_MAP = {
    "27": "ガジェット",
    "38": "テクノロジー/IoT",
    "41": "雑貨",
    "45": "オーディオ",
    "49": "アウトドア",
    "44": "車/バイク",
    "16": "ファッション",
    "30": "スポーツ",
    "6": "社会貢献",
    "23": "アート",
    "25": "出版",
    "39": "地域活性化",
    "40": "エンタメ",
    "26": "音楽",
    "29": "フード",
    "24": "映像/映画",
    "32": "イベント",
    "35": "アイドル",
    "42": "写真",
    "46": "アニメ",
    "43": "鉄道",
    "50": "ペット",
    "51": "台湾",
    "33": "その他",
    "52": "ゴルフ",
    "47": "蔦屋家電＋",
}


def init_db():
    """データベースを初期化"""
    conn = sqlite3.connect("greenfunding.db")
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id TEXT UNIQUE,
            title TEXT,
            description TEXT,
            amount INTEGER DEFAULT 0,
            achievement_rate INTEGER DEFAULT 0,
            supporters INTEGER DEFAULT 0,
            category TEXT DEFAULT '',
            status TEXT DEFAULT '',
            url TEXT,
            image_url TEXT,
            portal TEXT DEFAULT '',
            end_date TEXT DEFAULT ''
        )
    """)
    conn.commit()
    return conn


def parse_amount(text):
    """金額テキストをパース (例: ¥1,234,567 -> 1234567)"""
    if not text:
        return 0
    nums = re.sub(r"[^\d]", "", text)
    return int(nums) if nums else 0


def parse_rate(text):
    """達成率テキストをパース (例: 1234 % -> 1234)"""
    if not text:
        return 0
    nums = re.sub(r"[^\d]", "", text.split("%")[0].split("％")[0])
    return int(nums) if nums else 0


def parse_supporters(text):
    """サポーター数をパース"""
    if not text:
        return 0
    nums = re.sub(r"[^\d]", "", text)
    return int(nums) if nums else 0


def scrape_page(url, session):
    """1ページ分のプロジェクトをスクレイピング"""
    projects = []
    try:
        resp = session.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        print(f"  リクエストエラー: {e}")
        return projects

    soup = BeautifulSoup(resp.text, "html.parser")

    # プロジェクトカードを探す
    cards = soup.select("a[href*='/projects/']")
    
    seen_urls = set()
    for card in cards:
        href = card.get("href", "")
        if "/projects/" not in href or href in seen_urls:
            continue
        
        # プロジェクトURLを正規化
        if href.startswith("/"):
            full_url = BASE_URL + href
        elif href.startswith("http"):
            full_url = href
        else:
            continue
        
        # プロジェクトIDを抽出
        match = re.search(r"/projects/(\d+)", href)
        if not match:
            continue
        
        project_id = match.group(1)
        if project_id in seen_urls:
            continue
        seen_urls.add(project_id)
        
        # カード内の情報を取得
        # タイトル
        title_el = card.select_one("h3") or card.select_one(".project-title") or card.select_one("p")
        title = title_el.get_text(strip=True) if title_el else ""
        if not title:
            # カード全体のテキストからタイトルを推定
            texts = [t.strip() for t in card.stripped_strings]
            title = texts[0] if texts else ""
        
        # 金額
        amount = 0
        amount_texts = card.find_all(string=re.compile(r"¥[\d,]+"))
        if amount_texts:
            amount = parse_amount(amount_texts[0])
        
        # 達成率
        rate = 0
        rate_texts = card.find_all(string=re.compile(r"\d+\s*%"))
        if rate_texts:
            rate = parse_rate(rate_texts[0])
        
        # サポーター数
        supporters = 0
        supporter_texts = card.find_all(string=re.compile(r"\d+\s*人"))
        if supporter_texts:
            supporters = parse_supporters(supporter_texts[0])
        
        # ステータス
        status = ""
        if card.find(string=re.compile(r"終了")):
            status = "終了"
        elif card.find(string=re.compile(r"SUCCESS")):
            status = "成功"
        
        # 画像
        img = card.select_one("img")
        image_url = img.get("src", "") if img else ""
        
        # ポータル名を抽出（URLから）
        portal = ""
        portal_match = re.search(r"greenfunding\.jp/([^/]+)/projects", full_url)
        if portal_match:
            portal = portal_match.group(1)
        
        if title and len(title) > 2:
            projects.append({
                "project_id": project_id,
                "title": title[:500],
                "description": "",
                "amount": amount,
                "achievement_rate": rate,
                "supporters": supporters,
                "category": "",
                "status": status,
                "url": full_url,
                "image_url": image_url,
                "portal": portal,
                "end_date": "",
            })
    
    return projects


def scrape_project_detail(url, session):
    """個別プロジェクトページから詳細情報を取得"""
    try:
        resp = session.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        
        detail = {}
        
        # カテゴリ
        cat_link = soup.select_one("a[href*='category_id=']")
        if cat_link:
            cat_href = cat_link.get("href", "")
            cat_match = re.search(r"category_id=(\d+)", cat_href)
            if cat_match:
                cat_id = cat_match.group(1)
                detail["category"] = CATEGORY_MAP.get(cat_id, cat_link.get_text(strip=True))
            else:
                detail["category"] = cat_link.get_text(strip=True)
        
        # 説明文
        desc_el = soup.select_one("meta[name='description']")
        if desc_el:
            detail["description"] = desc_el.get("content", "")[:500]
        
        return detail
    except Exception as e:
        print(f"    詳細取得エラー: {e}")
        return {}


def save_projects(conn, projects):
    """プロジェクトをDBに保存"""
    c = conn.cursor()
    saved = 0
    for p in projects:
        try:
            c.execute("""
                INSERT OR REPLACE INTO projects 
                (project_id, title, description, amount, achievement_rate, 
                 supporters, category, status, url, image_url, portal, end_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                p["project_id"], p["title"], p["description"],
                p["amount"], p["achievement_rate"], p["supporters"],
                p["category"], p["status"], p["url"], p["image_url"],
                p["portal"], p["end_date"]
            ))
            saved += 1
        except Exception as e:
            print(f"  DB保存エラー: {e}")
    conn.commit()
    return saved


def main():
    print("=" * 60)
    print("GREEN FUNDING スクレイパー")
    print("=" * 60)
    
    conn = init_db()
    session = requests.Session()
    total_saved = 0
    
    # ランキングページからスクレイピング（全ページ）
    max_pages = 300  # 安全のため上限設定
    
    print(f"\n📊 ランキングページからデータ収集開始...")
    
    for page in range(1, max_pages + 1):
        url = f"{SEARCH_URL}?page={page}"
        print(f"  ページ {page} を取得中... ({url})")
        
        projects = scrape_page(url, session)
        
        if not projects:
            print(f"  ページ {page}: データなし → 終了")
            break
        
        saved = save_projects(conn, projects)
        total_saved += saved
        print(f"  → {len(projects)} 件取得, {saved} 件保存 (累計: {total_saved})")
        
        # レート制限対策
        time.sleep(1)
    
    # 新着ページからもスクレイピング
    print(f"\n📋 新着ページからデータ収集開始...")
    NEW_URL = f"{BASE_URL}/portals/search"
    
    for page in range(1, max_pages + 1):
        url = f"{NEW_URL}?condition=new&page={page}"
        print(f"  ページ {page} を取得中...")
        
        projects = scrape_page(url, session)
        
        if not projects:
            print(f"  ページ {page}: データなし → 終了")
            break
        
        saved = save_projects(conn, projects)
        total_saved += saved
        print(f"  → {len(projects)} 件取得, {saved} 件保存 (累計: {total_saved})")
        
        time.sleep(1)
    
    # カテゴリ別にもスクレイピング
    print(f"\n📂 カテゴリ別データ収集開始...")
    for cat_id, cat_name in CATEGORY_MAP.items():
        print(f"\n  カテゴリ: {cat_name}")
        for page in range(1, 100):
            url = f"{NEW_URL}?category_id={cat_id}&page={page}"
            projects = scrape_page(url, session)
            
            if not projects:
                break
            
            saved = save_projects(conn, projects)
            total_saved += saved
            
            if page % 10 == 0:
                print(f"    ページ {page}: {saved} 件保存 (累計: {total_saved})")
            
            time.sleep(0.5)
    
    # 統計表示
    c = conn.cursor()
    total = c.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
    total_amount = c.execute("SELECT SUM(amount) FROM projects").fetchone()[0] or 0
    max_amount = c.execute("SELECT MAX(amount) FROM projects").fetchone()[0] or 0
    max_rate = c.execute("SELECT MAX(achievement_rate) FROM projects").fetchone()[0] or 0
    
    print("\n" + "=" * 60)
    print("📊 収集完了!")
    print(f"  総プロジェクト数: {total:,}")
    print(f"  総支援金額: ¥{total_amount:,}")
    print(f"  最高支援金額: ¥{max_amount:,}")
    print(f"  最高達成率: {max_rate:,}%")
    print("=" * 60)
    
    conn.close()


if __name__ == "__main__":
    main()
