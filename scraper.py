import sqlite3
import re
import time
import requests
from datetime import datetime
from typing import Optional, Tuple, List

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
    negative = [r'أبحث\s*عن', r'ابحث\s*عن', r'محتاج\s*وظيفة', r'ابغى\s*شغل', r'أدور\s*كفيل', r'عايز\s*شغل', r'محتاج\s*كفيل', r'أريد\s*وظيفة', r'أبغى\s*وظيفة']
    for pat in negative:
        if re.search(pat, text_lower):
            return None
    if re.search(r'تنازل|نقل\s*كفالة|صك\s*تنازل|للتنازل', text_lower):
        return "تنازل"
    if re.search(r'استقدام|تأشيرات|تأشيرة', text_lower):
        return "استقدام"
    if re.search(r'متوفر|متوفرة|مطلوب\s*عمالة|عاملة\s*منزلية|خادمة|شغالة', text_lower):
        return "تنازل"
    return None

def process_and_add_ad(source: str, text: str) -> bool:
    category = classify_ad(text)
    if not category:
        return False
    phone, wa_link = extract_phone_and_whatsapp(text)
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR IGNORE INTO ads (source, content, category, phone, whatsapp_link)
            VALUES (?, ?, ?, ?, ?)
        ''', (source, text.strip(), category, phone, wa_link))
        conn.commit()
        added = cursor.rowcount > 0
        conn.close()
        return added
    except:
        return False

def scrape_haraj():
    url = "https://graphql.haraj.com.sa"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Content-Type": "application/json",
        "Origin": "https://haraj.com.sa",
        "Referer": "https://haraj.com.sa/"
    }
    query = """query($search:String, $page:Int) { posts(search:$search, page:$page) { items { title bodyTEXT city } } }"""
    keywords = ["عاملة منزلية للتنازل", "خادمة للتنازل", "شغالة للتنازل", "نقل كفالة عاملة"]
    
    total_added = 0
    for keyword in keywords:
        for page in range(1, 2):
            try:
                res = requests.post(url, json={"query": query, "variables": {"search": keyword, "page": page}}, headers=headers, timeout=10)
                if res.status_code == 200:
                    posts = res.json().get("data", {}).get("posts", {}).get("items", [])
                    for post in posts:
                        full_text = f"{post.get('title', '')}\n{post.get('bodyTEXT', '')}\nالمدينة: {post.get('city', '')}"
                        if process_and_add_ad("حراج", full_text):
                            total_added += 1
                time.sleep(1)
            except:
                pass
    print(f"تمت إضافة {total_added} إعلان جديد.")

def update_html_file():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT source, content, category, phone, whatsapp_link, date FROM ads ORDER BY date DESC LIMIT 100")
    ads = cursor.fetchall()
    conn.close()

    rows_html = ""
    for source, content, category, phone, wa_link, date in ads:
        cat_class = f"cat-{category}" if category in ["تنازل", "استقدام"] else "cat-أخرى"
        wa_button = f'<a href="{wa_link}" target="_blank" class="wa-btn">💬 تواصل ({phone})</a>' if (wa_link and phone) else '<span style="color:#a0aec0;font-size:0.8rem;">بدون رقم</span>'
        short_content = content[:250] + "..." if len(content) > 250 else content

        rows_html += f"""
                <tr>
                    <td><span class="source-tag">{source}</span></td>
                    <td><span class="category {cat_class}">{category}</span></td>
                    <td class="content-cell">{short_content}</td>
                    <td>{str(date)[:16]}</td>
                    <td>{wa_button}</td>
                </tr>
        """

    html_content = f"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>إعلانات الاستقدام والتنازل</title>
    <style>
        :root {{ --primary: #1a365d; --accent: #2b6cb0; }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{ font-family: 'Segoe UI', Tahoma, Arial, sans-serif; background: #f7fafc; padding: 20px; color: #2d3748; }}
        .container {{ max-width: 1200px; margin: 0 auto; background: white; border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.06); overflow: hidden; }}
        header {{ background: linear-gradient(135deg, var(--primary), var(--accent)); color: white; padding: 24px; text-align: center; }}
        header h1 {{ font-size: 1.5rem; margin-bottom: 6px; }}
        .filters {{ padding: 15px 20px; background: #fff; border-bottom: 1px solid #e2e8f0; }}
        .search-box {{ width: 100%; padding: 11px 16px; border: 2px solid #e2e8f0; border-radius: 8px; font-size: 0.95rem; outline: none; }}
        table {{ width: 100%; border-collapse: collapse; }}
        th, td {{ padding: 13px 15px; border-bottom: 1px solid #f1f5f9; text-align: right; vertical-align: middle; }}
        th {{ background: #f8fafc; font-weight: 600; color: #475569; font-size: 0.88rem; }}
        td {{ font-size: 0.92rem; }}
        tr:hover {{ background: #fafbfc; }}
        .source-tag {{ background: #ebf8ff; color: #2b6cb0; padding: 3px 9px; border-radius: 6px; font-size: 0.78rem; font-weight: 600; }}
        .category {{ padding: 3px 11px; border-radius: 20px; font-size: 0.75rem; font-weight: 700; display: inline-block; }}
        .cat-تنازل {{ background: #c6f6d5; color: #276749; }}
        .cat-استقدام {{ background: #bee3f8; color: #2a4365; }}
        .wa-btn {{ background-color: #25d366; color: white; padding: 6px 12px; border-radius: 6px; text-decoration: none; font-size: 0.82rem; font-weight: 600; display: inline-flex; align-items: center; gap: 4px; white-space: nowrap; }}
        .wa-btn:hover {{ background-color: #20ba5a; }}
        .content-cell {{ line-height: 1.55; max-width: 420px; }}
        footer {{ text-align: center; padding: 14px; color: #a0aec0; font-size: 0.8rem; background: #f8fafc; }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>إعلانات الاستقدام والتنازل المباشرة</h1>
            <p>مفلترة تلقائياً • أزرار واتساب مباشرة</p>
        </header>
        <div class="filters">
            <input type="text" class="search-box" id="searchInput" placeholder="ابحث برقم، مدينة، أو جنسية...">
        </div>
        <table>
            <thead>
                <tr>
                    <th>المصدر</th>
                    <th>الفئة</th>
                    <th>نص الإعلان</th>
                    <th>التاريخ</th>
                    <th>التواصل</th>
                </tr>
            </thead>
            <tbody id="adsTable">
                {rows_html}
            </tbody>
        </table>
        <footer>نظام آلي • آخر تحديث: {datetime.now().strftime("%Y-%m-%d %H:%M")}</footer>
    </div>
    <script>
        const searchInput = document.getElementById('searchInput');
        const rows = document.querySelectorAll('#adsTable tr');
        searchInput.addEventListener('input', (e) => {{
            const query = e.target.value.toLowerCase().trim();
            rows.forEach(row => {{
                row.style.display = row.textContent.toLowerCase().includes(query) ? '' : 'none';
            }});
        }));
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

