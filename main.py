from fastapi import FastAPI, Request, Form, HTTPException, Depends
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse, Response
from fastapi.security import HTTPBasic, HTTPBasicCredentials
import sqlite3
import requests
import re
import csv
import secrets
from io import StringIO
from passlib.context import CryptContext
from datetime import datetime, timedelta

app = FastAPI(title="Личная библиотека")
templates = Jinja2Templates(directory="templates")

DB_PATH = "library.db"

# Настройка хэширования паролей
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# =====================================================
# РАБОТА С БАЗОЙ ДАННЫХ
# =====================================================

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Создаёт все таблицы при первом запуске"""
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

    # Таблица пользователей (ДОБАВЛЕНА)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Таблица сессий (ДОБАВЛЕНА)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS session (
            session_id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            expires_at TIMESTAMP NOT NULL,
            FOREIGN KEY (user_id) REFERENCES user(user_id) ON DELETE CASCADE
        )
    """)

    conn.commit()

    # Создаём администратора, если его нет
    cursor.execute("SELECT COUNT(*) FROM user WHERE role = 'admin'")
    if cursor.fetchone()[0] == 0:
        admin_hash = pwd_context.hash("admin123")
        cursor.execute(
            "INSERT INTO user (username, password_hash, role) VALUES (?, ?, ?)",
            ("admin", admin_hash, "admin")
        )
        print("✅ Администратор создан: login=admin, password=admin123")

    # Создаём тестового пользователя, если его нет
    cursor.execute("SELECT COUNT(*) FROM user WHERE username = 'user'")
    if cursor.fetchone()[0] == 0:
        user_hash = pwd_context.hash("user123")
        cursor.execute(
            "INSERT INTO user (username, password_hash, role) VALUES (?, ?, ?)",
            ("user", user_hash, "user")
        )
        print("✅ Тестовый пользователь создан: login=user, password=user123")

    conn.commit()
    conn.close()
    print("✅ База данных готова")


# Вызываем создание таблиц при запуске
init_db()


# =====================================================
# ФУНКЦИИ АВТОРИЗАЦИИ
# =====================================================

def create_session(user_id: int) -> str:
    """Создаёт новую сессию и возвращает её ID"""
    session_id = secrets.token_urlsafe(32)
    expires_at = datetime.now() + timedelta(days=7)

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO session (session_id, user_id, expires_at) VALUES (?, ?, ?)",
        (session_id, user_id, expires_at)
    )
    conn.commit()
    conn.close()
    return session_id


def get_user_by_session(session_id: str):
    """Возвращает пользователя по ID сессии"""
    if not session_id:
        return None

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT u.user_id, u.username, u.role
        FROM session s
        JOIN user u ON s.user_id = u.user_id
        WHERE s.session_id = ? AND s.expires_at > CURRENT_TIMESTAMP
    """, (session_id,))
    user = cursor.fetchone()
    conn.close()
    return user


def get_current_user(request: Request):
    """Получает текущего пользователя из cookie"""
    session_id = request.cookies.get("session_id")
    return get_user_by_session(session_id)


def require_auth(request: Request):
    """Декоратор для проверки авторизации"""
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    return user


def require_admin(request: Request):
    """Декоратор для проверки прав администратора"""
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    if user["role"] != "admin":
        return RedirectResponse(url="/?error=Доступ запрещён", status_code=303)
    return user


# =====================================================
# ФУНКЦИИ ДЛЯ РАБОТЫ С БАЗОЙ (ОСТАЛИСЬ БЕЗ ИЗМЕНЕНИЙ)
# =====================================================

def get_books_from_db(search_query: str = None):
    conn = get_db_connection()
    cursor = conn.cursor()

    if search_query:
        cursor.execute("""
            SELECT 
                b.book_id, b.title, b.isbn, b.publication_year,
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
                b.book_id, b.title, b.isbn, b.publication_year,
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
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM book")
    total_books = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM author")
    total_authors = cursor.fetchone()[0]
    cursor.execute("SELECT MIN(publication_year) FROM book WHERE publication_year IS NOT NULL")
    oldest_year = cursor.fetchone()[0]
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
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
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

            cursor.execute("INSERT OR IGNORE INTO author (first_name, last_name) VALUES (?, ?)",
                           (first_name, last_name))
            cursor.execute("SELECT author_id FROM author WHERE first_name = ? AND last_name = ?",
                           (first_name, last_name))
            author = cursor.fetchone()
            if author:
                cursor.execute("INSERT OR IGNORE INTO book_author (book_id, author_id) VALUES (?, ?)",
                               (book_id, author[0]))

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

# --- Страница входа ---
@app.get("/login")
async def login_page(request: Request, error: str = None):
    """Страница входа"""
    # Если пользователь уже авторизован, перенаправляем на главную
    user = get_current_user(request)
    if user:
        return RedirectResponse(url="/", status_code=303)
    return templates.TemplateResponse("login.html", {"request": request, "error": error})


@app.post("/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...)):
    """Обработка формы входа"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, username, password_hash, role FROM user WHERE username = ?", (username,))
    user = cursor.fetchone()
    conn.close()

    if user and pwd_context.verify(password, user["password_hash"]):
        # Создаём сессию
        session_id = create_session(user["user_id"])
        response = RedirectResponse(url="/", status_code=303)
        response.set_cookie(key="session_id", value=session_id, httponly=True, max_age=604800)
        return response
    else:
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "Неверный логин или пароль"
        })


@app.get("/logout")
async def logout(request: Request):
    """Выход из системы"""
    session_id = request.cookies.get("session_id")
    if session_id:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM session WHERE session_id = ?", (session_id,))
        conn.commit()
        conn.close()

    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie("session_id")
    return response


@app.get("/register")
async def register_page(request: Request, error: str = None):
    """Страница регистрации"""
    user = get_current_user(request)
    if user:
        return RedirectResponse(url="/", status_code=303)
    return templates.TemplateResponse("register.html", {"request": request, "error": error})


@app.post("/register")
async def register(request: Request, username: str = Form(...), password: str = Form(...)):
    """Обработка регистрации нового пользователя"""
    if len(username) < 3:
        return templates.TemplateResponse("register.html", {
            "request": request,
            "error": "Имя пользователя должно содержать не менее 3 символов"
        })

    if len(password) < 4:
        return templates.TemplateResponse("register.html", {
            "request": request,
            "error": "Пароль должен содержать не менее 4 символов"
        })

    conn = get_db_connection()
    cursor = conn.cursor()

    # Проверяем, не занято ли имя
    cursor.execute("SELECT user_id FROM user WHERE username = ?", (username,))
    if cursor.fetchone():
        conn.close()
        return templates.TemplateResponse("register.html", {
            "request": request,
            "error": "Пользователь с таким именем уже существует"
        })

    # Создаём нового пользователя
    password_hash = pwd_context.hash(password)
    cursor.execute(
        "INSERT INTO user (username, password_hash, role) VALUES (?, ?, ?)",
        (username, password_hash, "user")
    )
    conn.commit()
    conn.close()

    return templates.TemplateResponse("login.html", {
        "request": request,
        "error": "Регистрация успешна! Теперь войдите в систему"
    })


# --- Главная страница ---
@app.get("/")
async def home(request: Request, search: str = None, error: str = None):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    books = get_books_from_db(search)
    stats = get_stats()
    return templates.TemplateResponse("index.html", {
        "request": request,
        "books": books,
        "stats": stats,
        "search_query": search or "",
        "error": error,
        "user": user
    })


# --- Добавление книги (только администратор) ---
@app.post("/add_book")
async def add_book(request: Request, isbn: str = Form(...)):
    user = get_current_user(request)
    if not user or user["role"] != "admin":
        return RedirectResponse(url="/?error=Доступ запрещён", status_code=303)

    isbn_clean = isbn.replace("-", "").replace(" ", "").strip()

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT book_id FROM book WHERE isbn = ?", (isbn_clean,))
    if cursor.fetchone():
        conn.close()
        return RedirectResponse(url="/?error=Книга уже есть в библиотеке", status_code=303)
    conn.close()

    book_data = fetch_from_openlibrary(isbn_clean)
    if not book_data or not book_data.get("title"):
        return RedirectResponse(url="/?error=Книга не найдена. Проверьте ISBN", status_code=303)

    save_book_to_db(isbn_clean, book_data)
    return RedirectResponse(url="/?error=", status_code=303)


# --- Удаление книги (только администратор) ---
@app.post("/delete_book/{book_id}")
async def delete_book(request: Request, book_id: int):
    user = get_current_user(request)
    if not user or user["role"] != "admin":
        return RedirectResponse(url="/?error=Доступ запрещён", status_code=303)

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM book WHERE book_id = ?", (book_id,))
    conn.commit()
    conn.close()
    return RedirectResponse(url="/", status_code=303)


# --- Экспорт в CSV (только администратор) ---
@app.get("/export")
async def export_csv(request: Request):
    user = get_current_user(request)
    if not user or user["role"] != "admin":
        return RedirectResponse(url="/?error=Доступ запрещён", status_code=303)

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 
            b.title, b.isbn, b.publication_year,
            COALESCE(GROUP_CONCAT(a.last_name || ' ' || a.first_name, ', '), '') AS authors
        FROM book b
        LEFT JOIN book_author ba ON b.book_id = ba.book_id
        LEFT JOIN author a ON ba.author_id = a.author_id
        GROUP BY b.book_id
        ORDER BY b.title
    """)
    books = cursor.fetchall()
    conn.close()

    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(['Название', 'Авторы', 'ISBN', 'Год издания'])

    for book in books:
        writer.writerow([book['title'], book['authors'], book['isbn'], book['publication_year']])

    return Response(
        content=output.getvalue().encode('utf-8-sig'),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=library_export.csv"}
    )


# --- Страница просмотра базы данных (только администратор) ---
@app.get("/admin/db")
async def view_database(request: Request):
    user = get_current_user(request)
    if not user or user["role"] != "admin":
        return RedirectResponse(url="/?error=Доступ запрещён", status_code=303)

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = cursor.fetchall()

    db_data = {}
    for table in tables:
        table_name = table['name']
        cursor.execute(f"SELECT * FROM {table_name} LIMIT 50")
        rows = cursor.fetchall()
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = [col['name'] for col in cursor.fetchall()]
        db_data[table_name] = {"columns": columns, "rows": rows}

    conn.close()
    return templates.TemplateResponse("database.html", {"request": request, "db_data": db_data})


# =====================================================
# ЗАПУСК СЕРВЕРА
# =====================================================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8005)