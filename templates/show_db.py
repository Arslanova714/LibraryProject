import sqlite3

conn = sqlite3.connect('library.db')
cursor = conn.cursor()

print('=== Таблицы в базе данных ===')
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
for row in cursor.fetchall():
    print(f'  - {row[0]}')

print('\n=== Содержимое таблицы book ===')
cursor.execute('SELECT book_id, title, isbn, publication_year FROM book LIMIT 10')
for row in cursor.fetchall():
    print(f'  {row}')

print('\n=== Содержимое таблицы author ===')
cursor.execute('SELECT author_id, first_name, last_name FROM author LIMIT 10')
for row in cursor.fetchall():
    print(f'  {row}')

print('\n=== Содержимое таблицы book_author (связи) ===')
cursor.execute('SELECT * FROM book_author LIMIT 10')
for row in cursor.fetchall():
    print(f'  {row}')

print('\n=== Содержимое таблицы api_cache (кэш) ===')
cursor.execute('SELECT cache_id, isbn, source_api, fetched_at FROM api_cache LIMIT 5')
for row in cursor.fetchall():
    print(f'  {row}')

conn.close()