from fastapi import FastAPI, Request, Form
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse, Response
import sqlite3
import requests
import re
import csv
from io import StringIO

app = FastAPI(title="Личная библиотека")
templates = Jinja2Templates(directory="templates")

DB_PATH = "library.db"


def get_db_connection():
    """Создаёт соединение с SQLite базой данных"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Создаёт таблицы при первом запуске"""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Таблица книг
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS book (
            book_id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            isbn TEXT UNIQUE,
            publication_year INTEGER
        )
    """)

    # Таблица авторов
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS author (
            author_id INTEGER PRIMARY KEY AUTOINCREMENT,
            first_name TEXT,
            last_name TEXT NOT NULL
        )
    """)

    # Таблица связи книга-автор
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS book_author (
            book_id INTEGER,
            author_id INTEGER,
            PRIMARY KEY (book_id, author_id),
            FOREIGN KEY (book_id) REFERENCES book(book_id) ON DELETE CASCADE,
            FOREIGN KEY (author_id) REFERENCES author(author_id) ON DELETE CASCADE
        )
    """)

    # Таблица кэша API
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS api_cache (
            cache_id INTEGER PRIMARY KEY AUTOINCREMENT,
            isbn TEXT,
            source_api TEXT,
            raw_response TEXT,
            fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()
    print("✅ База данных готова")


# Вызываем создание таблиц при запуске
init_db()


def get_books_from_db(search_query: str = None):
    """Возвращает список книг. Если указан search_query, фильтрует по названию или автору"""
    conn = get_db_connection()
    cursor = conn.cursor()

    if search_query:
        # Поиск по названию книги или имени автора
        cursor.execute("""
            SELECT 
                b.book_id, 
                b.title, 
                b.isbn, 
                b.publication_year,
                COALESCE(GROUP_CONCAT(a.last_name || ' ' || a.first_name, ', '), '') AS authors
            FROM book b
            LEFT JOIN book_author ba ON b.book_id = ba.book_id
            LEFT JOIN author a ON ba.author_id = a.author_id
            WHERE b.title LIKE ? OR a.last_name LIKE ? OR a.first_name LIKE ?
            GROUP BY b.book_id
            ORDER BY b.title
        """, (f'%{search_query}%', f'%{search_query}%', f'%{search_query}%'))
    else:
        cursor.execute("""
            SELECT 
                b.book_id, 
                b.title, 
                b.isbn, 
                b.publication_year,
                COALESCE(GROUP_CONCAT(a.last_name || ' ' || a.first_name, ', '), '') AS authors
            FROM book b
            LEFT JOIN book_author ba ON b.book_id = ba.book_id
            LEFT JOIN author a ON ba.author_id = a.author_id
            GROUP BY b.book_id
            ORDER BY b.title
        """)

    books = cursor.fetchall()
    conn.close()
    return books


def get_stats():
    """Возвращает статистику по библиотеке"""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Общее количество книг
    cursor.execute("SELECT COUNT(*) FROM book")
    total_books = cursor.fetchone()[0]

    # Общее количество авторов
    cursor.execute("SELECT COUNT(*) FROM author")
    total_authors = cursor.fetchone()[0]

    # Самая старая книга
    cursor.execute("SELECT MIN(publication_year) FROM book WHERE publication_year IS NOT NULL")
    oldest_year = cursor.fetchone()[0]

    # Самая новая книга
    cursor.execute("SELECT MAX(publication_year) FROM book WHERE publication_year IS NOT NULL")
    newest_year = cursor.fetchone()[0]

    conn.close()

    return {
        "total_books": total_books,
        "total_authors": total_authors,
        "oldest_book_year": oldest_year,
        "newest_book_year": newest_year
    }


def fetch_from_openlibrary(isbn):
    """Запрашивает данные о книге из OpenLibrary API"""
    url = f"https://openlibrary.org/api/books?bibkeys=ISBN:{isbn}&format=json&jscmd=data"
    try:
        response = requests.get(url, timeout=5)
        data = response.json()
        key = f"ISBN:{isbn}"
        if key in data:
            book_data = data[key]
            year = None
            if book_data.get("publish_date"):
                match = re.search(r'\d{4}', book_data["publish_date"])
                if match:
                    year = int(match.group())
            return {
                "title": book_data.get("title", ""),
                "authors": [a.get("name", "") for a in book_data.get("authors", [])],
                "publication_year": year
            }
    except Exception as e:
        print(f"API error: {e}")
    return None


def save_book_to_db(isbn, book_data):
    """Сохраняет книгу и авторов в базу данных"""
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Вставляем книгу
        cursor.execute("""
            INSERT INTO book (isbn, title, publication_year)
            VALUES (?, ?, ?)
        """, (isbn, book_data["title"], book_data["publication_year"]))
        book_id = cursor.lastrowid

        # Добавляем авторов
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

            # Вставляем автора или игнорируем если уже есть
            cursor.execute("INSERT OR IGNORE INTO author (first_name, last_name) VALUES (?, ?)",
                           (first_name, last_name))

            # Получаем ID автора
            cursor.execute("SELECT author_id FROM author WHERE first_name = ? AND last_name = ?",
                           (first_name, last_name))
            author = cursor.fetchone()
            if author:
                cursor.execute("INSERT OR IGNORE INTO book_author (book_id, author_id) VALUES (?, ?)",
                               (book_id, author[0]))

        # Сохраняем в кэш
        cursor.execute("""
            INSERT OR REPLACE INTO api_cache (isbn, source_api, raw_response)
            VALUES (?, ?, ?)
        """, (isbn, "OpenLibrary", str(book_data)))

        conn.commit()
        return book_id
    except Exception as e:
        print(f"Ошибка при сохранении: {e}")
        return None
    finally:
        conn.close()


# =====================================================
# ВЕБ-МАРШРУТЫ
# =====================================================

@app.get("/")
async def home(request: Request, search: str = None, message: str = None, message_type: str = "success"):
    """Главная страница со списком книг и поиском"""
    books = get_books_from_db(search)
    stats = get_stats()
    return templates.TemplateResponse("index.html", {
        "request": request,
        "books": books,
        "stats": stats,
        "search_query": search or "",
        "message": message,
        "message_type": message_type
    })


@app.post("/add_book")
async def add_book(isbn: str = Form(...)):
    """Добавляет книгу по ISBN через OpenLibrary API"""
    isbn_clean = isbn.replace("-", "").replace(" ", "").strip()

    # Проверяем, нет ли уже такой книги
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT book_id FROM book WHERE isbn = ?", (isbn_clean,))
    if cursor.fetchone():
        conn.close()
        return RedirectResponse(url="/?message=Книга уже есть в библиотеке&message_type=warning", status_code=303)
    conn.close()

    # Запрашиваем данные из API
    book_data = fetch_from_openlibrary(isbn_clean)
    if not book_data or not book_data.get("title"):
        return RedirectResponse(url="/?message=Книга не найдена. Проверьте ISBN&message_type=danger", status_code=303)

    # Сохраняем в базу
    save_book_to_db(isbn_clean, book_data)

    return RedirectResponse(url="/?message=Книга успешно добавлена&message_type=success", status_code=303)


@app.post("/delete_book/{book_id}")
async def delete_book(book_id: int):
    """Удаляет книгу из библиотеки"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM book WHERE book_id = ?", (book_id,))
    conn.commit()
    conn.close()
    return RedirectResponse(url="/?message=Книга удалена&message_type=success", status_code=303)


@app.get("/export")
async def export_csv():
    """Экспортирует все книги в CSV файл"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 
            b.title, 
            b.isbn, 
            b.publication_year,
            COALESCE(GROUP_CONCAT(a.last_name || ' ' || a.first_name, ', '), '') AS authors
        FROM book b
        LEFT JOIN book_author ba ON b.book_id = ba.book_id
        LEFT JOIN author a ON ba.author_id = a.author_id
        GROUP BY b.book_id
        ORDER BY b.title
    """)
    books = cursor.fetchall()
    conn.close()

    # Создаём CSV файл в памяти
    output = StringIO()
    writer = csv.writer(output)

    # Заголовки
    writer.writerow(['Название', 'Авторы', 'ISBN', 'Год издания'])

    # Данные
    for book in books:
        writer.writerow([
            book['title'],
            book['authors'],
            book['isbn'],
            book['publication_year']
        ])

    # Возвращаем файл
    return Response(
        content=output.getvalue().encode('utf-8-sig'),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=library_export.csv"}
    )


# =====================================================
# ЗАПУСК СЕРВЕРА
# =====================================================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=5501)