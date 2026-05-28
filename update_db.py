import sqlite3

conn = sqlite3.connect('library.db')
cursor = conn.cursor()

print('🔄 Начинаем обновление базы данных...')

# =====================================================
# 1. ДОБАВЛЯЕМ ТАБЛИЦУ ЖАНРОВ (если её нет)
# =====================================================

cursor.execute('''
    CREATE TABLE IF NOT EXISTS genre (
        genre_id INTEGER PRIMARY KEY AUTOINCREMENT,
        genre_name TEXT NOT NULL UNIQUE,
        description TEXT
    )
''')
print('✅ Таблица "genre" готова')

# =====================================================
# 2. ДОБАВЛЯЕМ ТАБЛИЦУ СВЯЗИ КНИГА-ЖАНР (если её нет)
# =====================================================

cursor.execute('''
    CREATE TABLE IF NOT EXISTS book_genre (
        book_id INTEGER,
        genre_id INTEGER,
        PRIMARY KEY (book_id, genre_id),
        FOREIGN KEY (book_id) REFERENCES book(book_id) ON DELETE CASCADE,
        FOREIGN KEY (genre_id) REFERENCES genre(genre_id) ON DELETE CASCADE
    )
''')
print('✅ Таблица "book_genre" готова')

# =====================================================
# 3. ЗАПОЛНЯЕМ ТАБЛИЦУ ЖАНРОВ
# =====================================================

genres = [
    ('Роман', 'Литературный жанр, раскрывающий историю жизни и развития личности'),
    ('Фантастика', 'Жанр, основанный на фантастическом допущении'),
    ('Программирование', 'Книги по разработке программного обеспечения'),
    ('Детектив', 'Литературный жанр, описывающий расследование преступления'),
    ('Сатира', 'Юмористический или сатирический жанр'),
    ('Антиутопия', 'Жанр, описывающий тоталитарное общество'),
    ('Фэнтези', 'Жанр, основанный на использовании мифологических элементов'),
]

for genre_name, description in genres:
    cursor.execute('''
        INSERT OR IGNORE INTO genre (genre_name, description) VALUES (?, ?)
    ''', (genre_name, description))

print(f'✅ Добавлено жанров: {len(genres)}')

# =====================================================
# 4. ПОЛУЧАЕМ ID КНИГ И ЖАНРОВ
# =====================================================

cursor.execute('SELECT book_id, title FROM book')
books = {title: book_id for book_id, title in cursor.fetchall()}

cursor.execute('SELECT genre_id, genre_name FROM genre')
genres_dict = {genre_name: genre_id for genre_id, genre_name in cursor.fetchall()}

# =====================================================
# 5. СВЯЗЫВАЕМ КНИГИ С ЖАНРАМИ
# =====================================================

book_genre_links = [
    (books.get('Война и мир'), genres_dict.get('Роман')),
    (books.get('Преступление и наказание'), genres_dict.get('Роман')),
    (books.get('1984'), genres_dict.get('Антиутопия')),
    (books.get('1984'), genres_dict.get('Фантастика')),
    (books.get('Совершенный код'), genres_dict.get('Программирование')),
    (books.get('Чистый код'), genres_dict.get('Программирование')),
    (books.get('Мастер и Маргарита'), genres_dict.get('Сатира')),
    (books.get('Мастер и Маргарита'), genres_dict.get('Роман')),
    (books.get('451 градус по Фаренгейту'), genres_dict.get('Антиутопия')),
    (books.get('451 градус по Фаренгейту'), genres_dict.get('Фантастика')),
    (books.get('Гарри Поттер и Философский камень'), genres_dict.get('Фэнтези')),
    (books.get('Гарри Поттер и Философский камень'), genres_dict.get('Роман')),
    (books.get('Двенадцать стульев'), genres_dict.get('Сатира')),
    (books.get('Двенадцать стульев'), genres_dict.get('Роман')),
    (books.get('Анна Каренина'), genres_dict.get('Роман')),
]

for book_id, genre_id in book_genre_links:
    if book_id and genre_id:
        cursor.execute('''
            INSERT OR IGNORE INTO book_genre (book_id, genre_id) VALUES (?, ?)
        ''', (book_id, genre_id))

print(f'✅ Добавлено связей книга-жанр: {len(book_genre_links)}')

# =====================================================
# 6. ОБНОВЛЯЕМ ГОДЫ ИЗДАНИЯ КНИГ
# =====================================================

updates = [
    ('Война и мир', 1869),
    ('Преступление и наказание', 1866),
    ('1984', 1949),
    ('Совершенный код', 2004),
    ('Чистый код', 2013),
    ('Мастер и Маргарита', 1967),
    ('451 градус по Фаренгейту', 1953),
    ('Гарри Поттер и Философский камень', 1997),
    ('Двенадцать стульев', 1928),
    ('Анна Каренина', 1877),
]

for title, year in updates:
    cursor.execute('''
        UPDATE book SET publication_year = ? WHERE title = ? AND publication_year IS NULL
    ''', (year, title))

print('✅ Годы издания книг обновлены')

# =====================================================
# 7. ДОБАВЛЯЕМ ДАННЫЕ В КЭШ API
# =====================================================

api_cache_data = [
    ('9785389047938', 'OpenLibrary', '{"title":"Война и мир","authors":["Лев Толстой"],"publish_date":"1869","pages":1300}'),
    ('9785171184630', 'OpenLibrary', '{"title":"Преступление и наказание","authors":["Фёдор Достоевский"],"publish_date":"1866","pages":672}'),
    ('9780451524935', 'GoogleBooks', '{"title":"1984","authors":["George Orwell"],"publishedDate":"1949","pageCount":328}'),
    ('9785961434628', 'GoogleBooks', '{"title":"Code Complete","authors":["Steve McConnell"],"publishedDate":"2004","pageCount":896}'),
    ('9785496020084', 'GoogleBooks', '{"title":"Clean Code","authors":["Robert C. Martin"],"publishedDate":"2008","pageCount":464}'),
]

for isbn, source_api, raw_response in api_cache_data:
    cursor.execute('''
        INSERT OR REPLACE INTO api_cache (isbn, source_api, raw_response, fetched_at)
        VALUES (?, ?, ?, CURRENT_TIMESTAMP)
    ''', (isbn, source_api, raw_response))

print(f'✅ Добавлено записей в кэш API: {len(api_cache_data)}')

# =====================================================
# 8. ИТОГОВАЯ ПРОВЕРКА
# =====================================================

conn.commit()

print('\n' + '='*50)
print('📊 ИТОГОВАЯ СТАТИСТИКА')
print('='*50)

cursor.execute('SELECT COUNT(*) FROM book')
print(f'📚 Книг: {cursor.fetchone()[0]}')

cursor.execute('SELECT COUNT(*) FROM author')
print(f'✍️ Авторов: {cursor.fetchone()[0]}')

cursor.execute('SELECT COUNT(*) FROM genre')
print(f'🏷️ Жанров: {cursor.fetchone()[0]}')

cursor.execute('SELECT COUNT(*) FROM book_author')
print(f'🔗 Связей книга-автор: {cursor.fetchone()[0]}')

cursor.execute('SELECT COUNT(*) FROM book_genre')
print(f'🔗 Связей книга-жанр: {cursor.fetchone()[0]}')

cursor.execute('SELECT COUNT(*) FROM api_cache')
print(f'💾 Записей в кэше API: {cursor.fetchone()[0]}')

cursor.execute('SELECT COUNT(*) FROM user')
print(f'👤 Пользователей: {cursor.fetchone()[0]}')

conn.close()
print('\n✅ База данных успешно обновлена!')