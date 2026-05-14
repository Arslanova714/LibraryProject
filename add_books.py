import sqlite3
import requests
import re
import time

DB_PATH = "library.db"

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def fetch_from_openlibrary(isbn):
    url = f"https://openlibrary.org/api/books?bibkeys=ISBN:{isbn}&format=json&jscmd=data"
    try:
        response = requests.get(url, timeout=5)
        data = response.json()
        key = f"ISBN:{isbn}"
        if key in data:
            book_data = data[key]
            year = None
            if book_data.get("publish_date"):
                year_match = re.search(r'\d{4}', book_data["publish_date"])
                if year_match:
                    year = int(year_match.group())
            return {
                "title": book_data.get("title", ""),
                "authors": [a.get("name", "") for a in book_data.get("authors", [])],
                "publication_year": year,
                "raw_json": book_data
            }
    except Exception as e:
        print(f"Ошибка API для ISBN {isbn}: {e}")
    return None

def save_book_to_db(isbn, book_data):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT book_id FROM book WHERE isbn = ?", (isbn,))
        if cursor.fetchone():
            print(f"Книга с ISBN {isbn} уже есть в базе")
            return False
        
        cursor.execute("""
            INSERT INTO book (isbn, title, publication_year)
            VALUES (?, ?, ?)
        """, (isbn, book_data["title"], book_data["publication_year"]))
        book_id = cursor.lastrowid
        
        for author_name in book_data["authors"]:
            if not author_name:
                continue
            parts = author_name.split()
            if len(parts) == 1:
                last_name = parts[0]
                first_name = ""
            else:
                last_name = parts[-1]
                first_name = " ".join(parts[:-1])
            
            cursor.execute("INSERT OR IGNORE INTO author (first_name, last_name) VALUES (?, ?)", (first_name, last_name))
            cursor.execute("SELECT author_id FROM author WHERE first_name = ? AND last_name = ?", (first_name, last_name))
            author = cursor.fetchone()
            if author:
                cursor.execute("INSERT OR IGNORE INTO book_author (book_id, author_id) VALUES (?, ?)", (book_id, author[0]))
        
        conn.commit()
        print(f"✅ Добавлена: {book_data['title']}")
        return True
    except Exception as e:
        print(f"Ошибка при сохранении {isbn}: {e}")
        return False
    finally:
        conn.close()

BOOKS_TO_ADD = [
    "9785389047938",
    "9785171184630",
    "9780451524935",
    "9785496020084",
    "9785961434628",
    "9785170643972",
    "9785389202658",
    "9785446102800",
    "9785496021852",
    "9785171033259",
    "9785171033266",
    "9785171033273",
    "9785699406346",
    "9785171023908",
    "9785171023915",
]

print("=" * 50)
print("Начинаю добавление книг...")
print("=" * 50)

for i, isbn in enumerate(BOOKS_TO_ADD, 1):
    print(f"\n[{i}/{len(BOOKS_TO_ADD)}] Обработка ISBN: {isbn}")
    book_data = fetch_from_openlibrary(isbn)
    if book_data and book_data.get("title"):
        save_book_to_db(isbn, book_data)
    else:
        print(f"❌ Книга с ISBN {isbn} не найдена")
    time.sleep(1)

print("\n" + "=" * 50)
print("Готово!")