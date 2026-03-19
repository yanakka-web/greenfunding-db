from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
import sqlite3
from typing import Optional

app = FastAPI()


def get_db():
    conn = sqlite3.connect("greenfunding.db")
    conn.row_factory = sqlite3.Row
    return conn


@app.get("/api/projects")
def get_projects(
    page: int = 1,
    limit: int = 20,
    title: Optional[str] = None,
    keyword: Optional[str] = None,
    min_amount: Optional[int] = None,
    max_amount: Optional[int] = None,
    min_rate: Optional[int] = None,
    max_rate: Optional[int] = None,
    min_supporters: Optional[int] = None,
    max_supporters: Optional[int] = None,
    category: Optional[str] = None,
    portal: Optional[str] = None,
    sort: Optional[str] = "amount_desc",
    favorites_only: Optional[str] = None,
):
    conn = get_db()
    c = conn.cursor()

    query = "SELECT * FROM projects WHERE 1=1"
    params = []

    if title:
        query += " AND title LIKE ?"
        params.append(f"%{title}%")

    if keyword:
        query += " AND (title LIKE ? OR description LIKE ?)"
        params.append(f"%{keyword}%")
        params.append(f"%{keyword}%")

    if min_amount:
        query += " AND amount >= ?"
        params.append(min_amount)

    if max_amount:
        query += " AND amount <= ?"
        params.append(max_amount)

    if min_rate:
        query += " AND achievement_rate >= ?"
        params.append(min_rate)

    if max_rate:
        query += " AND achievement_rate <= ?"
        params.append(max_rate)

    if min_supporters:
        query += " AND supporters >= ?"
        params.append(min_supporters)

    if max_supporters:
        query += " AND supporters <= ?"
        params.append(max_supporters)

    if category:
        query += " AND category = ?"
        params.append(category)

    if portal:
        query += " AND portal = ?"
        params.append(portal)

    sort_map = {
        "amount_desc": "amount DESC",
        "amount_asc": "amount ASC",
        "rate_desc": "achievement_rate DESC",
        "rate_asc": "achievement_rate ASC",
        "supporters_desc": "supporters DESC",
        "supporters_asc": "supporters ASC",
        "newest": "id DESC",
        "oldest": "id ASC",
    }

    query += f" ORDER BY {sort_map.get(sort, 'amount DESC')}"

    count_query = query.replace("SELECT *", "SELECT COUNT(*)")
    total = c.execute(count_query, params).fetchone()[0]

    query += " LIMIT ? OFFSET ?"
    params.extend([limit, (page - 1) * limit])

    projects = c.execute(query, params).fetchall()
    conn.close()

    return {"total": total, "page": page, "projects": [dict(p) for p in projects]}


@app.get("/api/stats")
def get_stats():
    conn = get_db()
    c = conn.cursor()
    total = c.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
    max_amount = c.execute("SELECT MAX(amount) FROM projects").fetchone()[0] or 0
    max_rate = c.execute("SELECT MAX(achievement_rate) FROM projects").fetchone()[0] or 0
    total_amount = c.execute("SELECT SUM(amount) FROM projects").fetchone()[0] or 0
    conn.close()
    return {
        "total_projects": total,
        "max_amount": max_amount,
        "max_rate": max_rate,
        "total_amount": total_amount,
    }


@app.get("/api/categories")
def get_categories():
    conn = get_db()
    c = conn.cursor()
    rows = c.execute(
        "SELECT category, COUNT(*) as cnt FROM projects WHERE category != '' GROUP BY category ORDER BY cnt DESC"
    ).fetchall()
    conn.close()
    return [{"name": r[0], "count": r[1]} for r in rows]


@app.get("/api/portals")
def get_portals():
    conn = get_db()
    c = conn.cursor()
    rows = c.execute(
        "SELECT portal, COUNT(*) as cnt FROM projects WHERE portal != '' GROUP BY portal ORDER BY cnt DESC"
    ).fetchall()
    conn.close()
    return [{"name": r[0], "count": r[1]} for r in rows]


app.mount("/", StaticFiles(directory="static", html=True), name="static")
