import sqlite3
import re

def clean_and_filter(text):
    if not text: return False, None
    text_lower = text.lower()
    # رفض الباحثين عن عمل
    if any(w in text_lower for w in ['أبحث عن', 'محتاج وظيفة', 'ابغى شغل']):
        return False, None
    # قبول العروض
    if 'تنازل' in text_lower: return True, 'تنازل'
    if 'استقدام' in text_lower: return True, 'استقدام'
    return False, None

print("تم تجهيز منطق الفلترة والسحب بنجاح.")

