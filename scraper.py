import sqlite3
import re
import time
import requests
from datetime import datetime
from typing import Optional, Tuple

DB_NAME = "recruitment.db"
HTML_FILE = "index.html"

def setup_database():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT NOT NULL,
            content TEXT NOT NULL,
            category TEXT,
            phone TEXT,
            whatsapp_link TEXT,
            date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(content)
        )
    ''')
    conn.commit()
    conn.close()

def extract_phone_and_whatsapp(text: str) -> Tuple[str, str]:
    if not text:
        return "", ""
    clean_text = re.sub(r'[\s\-_\.]', '', text)
    patterns = [r'(?:\+?966|0)?5\d{8}', r'05\d{8}', r'\+9665\d{8}', r'9665\d{8}']
    for pattern in patterns:
        match = re.search(pattern, clean_text)
        if match:
            raw = match.group(0)
            if raw.startswith('05'):
                clean = '966' + raw[1:]
            elif raw.startswith('+966'):
                clean = raw[1:]
            elif raw.startswith('966'):
                clean = raw
            else:
                clean = '966' + raw[-9:]
            display = '0' + clean[3:] if clean.startswith('966') else raw
            return display, f"https://wa.me/{clean}"
    return "", ""

def classify_ad(text: str) -> Optional[str]:
    if not text or not text.strip():
        return None
    text_lower = text.lower().strip()
    negative = [r'أبحث\s*عن', r'ابحث\s*عن', r'محتاج\s*وظيفة', r'ابغى\s*شغل', r'أدور\s*كفيل', r'عايز\s*شغل', r'محتاج\s*كفيل', r'أريد\s*وظيفة', r'أبغى\s*وظيفة', r'مطلوب\s*كفيل', r'ابي\s*شغل']
    for pat in negative:
        if re.search(pat, text_lower):
            return None
    if re.search(r'تنازل|نقل\s*كفالة|صك\s*تنازل|للتنازل|تخارج', text_lower):
        return "تنازل"
    if re.search(r'استقدام|تأشيرات|تأشيرة|مكتب\s*استقدام', text_lower):
        return "استقدام"
    if re.search(r'متوفر|متوفرة|مطلوب\s*عمالة|عاملة\s*منزلية|خادمة|شغالة|سائق\s*خاص', text_lower):
        return "تنازل"
    return None

def process_and_add_ad(source: str, text: str):
    category = classify_ad(text)
    if not category:
        return
    phone, wa_link = extract_phone_and_whatsapp(text)
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR IGNORE INTO ads (source, content, category, phone, whatsapp_link)
            VALUES (?, ?, ?, ?, ?)
        ''', (source, text.strip(), category, phone, wa_link))
        conn.commit()
        conn.close()
    except Exception:
        pass

def scrape_haraj():
    keywords = ["عاملة منزلية للتنازل", "خادمة للتنازل", "شغالة للتنازل", "نقل كفالة عاملة", "سائق خاص للتنازل"]
    url = "https://graphql.haraj.com.sa"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0",
        "Content-Type": "application/json",
        "Origin": "https://haraj.com.sa",
        "Referer": "https://haraj.com.sa/"
    }
    query = """
    query($search:String, $page:Int) {
      posts(search:$search, page:$page) {
        items { title, bodyTEXT, city }
        pageInfo { hasNextPage }
      }
    }
    """
    for keyword in keywords:
        for page in range(1, 2):
            payload = {"query": query, "variables": {"search": keyword, "page": page}}
            try:
                response = requests.post(url, json=payload, headers=headers, timeout=10)
                if response.status_code != 200:
                    break
                data = response.json()
                posts = data.get("data", {}).get("posts", {}).get("items", [])
                if not posts:
                    break
                for post in posts:
                    title = post.get("title", "")
                    body = post.get("bodyTEXT", "") or ""
                    city = post.get("city", "")
                    full_text = f"{title}\n{body}\nالمدينة: {city}"
                    process_and_add_ad(source="حراج", text=full_text)
                time.sleep(1)
            except Exception:
                break

def update_html_file():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM ads")
    total_ads = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM ads WHERE category='تنازل'")
    total_tanazul = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM ads WHERE category='استقدام'")
    total_istiqdam = cursor.fetchone()[0]

    cursor.execute("SELECT source, content, category, phone, whatsapp_link, date FROM ads ORDER BY date DESC LIMIT 100")
    ads = cursor.fetchall()
    conn.close()

    rows_html = ""
    for source, content, category, phone, wa_link, date in ads:
        cat_class = "cat-tanazul" if category == "تنازل" else "cat-istiqdam"
        wa_button = f'<a href="{wa_link}" target="_blank" class="wa-btn">💬 واتساب ({phone})</a>' if wa_link and phone else '<span style="color:#64748b;font-size:12px;">بدون رقم</span>'
        rows_html += f"""
                <tr data-category="{category}">
                    <td><span class="source-badge">{source}</span></td>
                    <td><span class="category-badge {cat_class}">{category}</span></td>
                    <td class="content-cell">{content}</td>
                    <td class="date-cell">{str(date)[:16]}</td>
                    <td>{wa_button}</td>
                </tr>
        """

    html_content = f"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>لوحة إعلانات الاستقدام والتنازل المباشرة</title>
    <link href="https://fonts.googleapis.com/css2?family=Tajawal:wght@400;500;700;800&display=swap" rel="stylesheet">
    <style>
        :root {{ --bg: #f8fafc; --card: #ffffff; --text: #1e293b; --muted: #64748b; --primary: #2563eb; --primary-hover: #1d4ed8; --border: #e2e8f0; --tanazul-bg: #dcfce7; --tanazul-text: #15803d; --istiqdam-bg: #e0f2fe; --istiqdam-text: #0369a1; }}
        [data-theme="dark"] {{ --bg: #0f172a; --card: #1e293b; --text: #f1f5f9; --muted: #94a3b8; --primary: #3b82f6; --primary-hover: #2563eb; --border: #334155; --tanazul-bg: #064e3b; --tanazul-text: #6ee7b7; --istiqdam-bg: #0369a1; --istiqdam-text: #bae6fd; }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{ font-family: 'Tajawal', sans-serif; background: var(--bg); color: var(--text); padding: 20px; min-height: 100vh; }}
        .container {{ max-width: 1300px; margin: 0 auto; background: var(--card); border-radius: 16px; box-shadow: 0 10px 30px rgba(0,0,0,0.08); overflow: hidden; border: 1px solid var(--border); }}
        header {{ background: linear-gradient(135deg, var(--primary), var(--primary-hover)); color: white; padding: 24px 30px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 15px; }}
        header h1 {{ font-size: 22px; font-weight: 800; }}
        header p {{ font-size: 13px; opacity: 0.9; margin-top: 4px; }}
        .theme-toggle {{ background: rgba(255,255,255,0.2); border: none; color: white; padding: 8px 14px; border-radius: 10px; cursor: pointer; font-family: 'Tajawal'; font-weight: 700; }}
        .stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; padding: 20px 30px 0; }}
        .stat-card {{ background: var(--bg); border: 1px solid var(--border); padding: 15px; border-radius: 12px; text-align: center; }}
        .stat-card h3 {{ font-size: 12px; color: var(--muted); margin-bottom: 5px; }}
        .stat-card .val {{ font-size: 20px; font-weight: 800; color: var(--primary); }}
        .controls {{ padding: 20px 30px; display: flex; gap: 15px; flex-wrap: wrap; align-items: center; border-bottom: 1px solid var(--border); }}
        .search-box {{ flex: 1; min-width: 250px; padding: 12px 16px; border: 1px solid var(--border); border-radius: 10px; background: var(--bg); color: var(--text); font-family: 'Tajawal'; font-size: 14px; outline: none; }}
        .filter-tabs {{ display: flex; gap: 8px; }}
        .tab-btn {{ padding: 10px 16px; border-radius: 10px; border: 1px solid var(--border); background: var(--bg); color: var(--text); cursor: pointer; font-family: 'Tajawal'; font-weight: 700; font-size: 13px; }}
        .tab-btn.active {{ background: var(--primary); color: white; border-color: var(--primary); }}
        .table-responsive {{ width: 100%; overflow-x: auto; }}
        table {{ width: 100%; border-collapse: collapse; text-align: right; }}
        th, td {{ padding: 14px 20px; border-bottom: 1px solid var(--border); font-size: 14px; vertical-align: middle; }}
        th {{ background: var(--bg); font-weight: 700; color: var(--muted); font-size: 13px; }}
        tr:hover {{ background: rgba(0,0,0,0.02); }}
        .source-badge {{ background: var(--bg); border: 1px solid var(--border); padding: 4px 10px; border-radius: 8px; font-size: 12px; font-weight: 700; }}
        .category-badge {{ padding: 4px 12px; border-radius: 20px; font-size: 12px; font-weight: 700; display: inline-block; }}
        .cat-tanazul {{ background: var(--tanazul-bg); color: var(--tanazul-text); }}
        .cat-istiqdam {{ background: var(--istiqdam-bg); color: var(--istiqdam-text); }}
        .wa-btn {{ background-color: #22c55e; color: white; padding: 7px 14px; border-radius: 8px; text-decoration: none; font-size: 13px; font-weight: 700; display: inline-flex; align-items: center; gap: 5px; white-space: nowrap; }}
        .wa-btn:hover {{ background-color: #16a34a; }}
        .content-cell {{ line-height: 1.6; max-width: 450px; white-space: pre-line; }}
        .date-cell {{ font-size: 12px; color: var(--muted); white-space: nowrap; }}
        footer {{ text-align: center; padding: 20px; color: var(--muted); font-size: 12px; border-top: 1px solid var(--border); }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div>
                <h1>منظومة إعلانات الاستقدام والتنازل</h1>
                <p>تحديث آلي مباشر • تواصل فوري عبر واتساب</p>
            </div>
            <button class="theme-toggle" onclick="toggleTheme()">🌓 وضع العرض</button>
        </header>
        <div class="stats-grid">
            <div class="stat-card"><h3>إجمالي الإعلانات</h3><div class="val">{total_ads}</div></div>
            <div class="stat-card"><h3>عروض التنازل ونقل الكفالة</h3><div class="val">{total_tanazul}</div></div>
            <div class="stat-card"><h3>طلبات الاستقدام</h3><div class="val">{total_istiqdam}</div></div>
        </div>
        <div class="controls">
            <input type="text" class="search-box" id="searchInput" placeholder="ابحث برقم، مدينة، جنسية، أو كلمة مفتاحية...">
            <div class="filter-tabs">
                <button class="tab-btn active" onclick="filterCat('all', this)">الكل</button>
                <button class="tab-btn" onclick="filterCat('تنازل', this)">تنازل</button>
                <button class="tab-btn" onclick="filterCat('استقدام', this)">استقدام</button>
            </div>
        </div>
        <div class="table-responsive">
            <table>
                <thead>
                    <tr>
                        <th>المصدر</th>
                        <th>الفئة</th>
                        <th>نص الإعلان التفصيلي</th>
                        <th>التاريخ</th>
                        <th>تواصل واتساب</th>
                    </tr>
                </thead>
                <tbody id="adsTable">
                    {rows_html}
                </tbody>
            </table>
        </div>
        <footer>آخر تحديث آلي للنظام: {datetime.now().strftime("%Y-%m-%d %H:%M")}</footer>
    </div>
    <script>
        function toggleTheme() {{
            const html = document.documentElement;
            const current = html.getAttribute('data-theme');
            const next = current === 'dark' ? 'light' : 'dark';
            html.setAttribute('data-theme', next);
            localStorage.setItem('theme', next);
        }}
        if(localStorage.getItem('theme') === 'dark') {{
            document.documentElement.setAttribute('data-theme', 'dark');
        }}
        const searchInput = document.getElementById('searchInput');
        const rows = document.querySelectorAll('#adsTable tr');
        let currentCat = 'all';
        function filterAds() {{
            const query = searchInput.value.toLowerCase().trim();
            rows.forEach(row => {{
                const cat = row.getAttribute('data-category');
                const text = row.textContent.toLowerCase();
                const matchCat = (currentCat === 'all' || cat === currentCat);
                const matchText = text.includes(query);
                row.style.display = (matchCat && matchText) ? '' : 'none';
            }});
        }}
        searchInput.addEventListener('input', filterAds);
        function filterCat(cat, btn) {{
            currentCat = cat;
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            filterAds();
        }}
    </script>
</body>
</html>
"""
    with open(HTML_FILE, "w", encoding="utf-8") as f:
        f.write(html_content)

if __name__ == "__main__":
    setup_database()
    scrape_haraj()
    update_html_file()
    print("تم التحديث بنجاح")

