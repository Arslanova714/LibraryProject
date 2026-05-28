import sqlite3

conn = sqlite3.connect('library.db')
cursor = conn.cursor()

print('🔄 Начинаем добавление недостающих таблиц...')

# =====================================================
# 1. ТАБЛИЦА ЯЗЫКОВ (language)
# =====================================================

cursor.execute('''
    CREATE TABLE IF NOT EXISTS language (
        language_id INTEGER PRIMARY KEY AUTOINCREMENT,
        language_code TEXT NOT NULL UNIQUE,
        language_name TEXT NOT NULL
    )
''')
print('✅ Таблица "language" создана')

# Заполняем языки
languages = [
    ('rus', 'Русский'),
    ('eng', 'Английский'),
    ('deu', 'Немецкий'),
    ('fra', 'Французский'),
    ('spa', 'Испанский'),
    ('ita', 'Итальянский'),
    ('jpn', 'Японский'),
    ('chi', 'Китайский'),
]

for code, name in languages:
    cursor.execute('''
        INSERT OR IGNORE INTO language (language_code, language_name)
        VALUES (?, ?)
    ''', (code, name))
print(f'✅ Добавлено языков: {len(languages)}')

# =====================================================
# 2. ТАБЛИЦА ИЗДАТЕЛЬСТВ (publisher)
# =====================================================

cursor.execute('''
    CREATE TABLE IF NOT EXISTS publisher (
        publisher_id INTEGER PRIMARY KEY AUTOINCREMENT,
        publisher_name TEXT NOT NULL UNIQUE,
        city TEXT,
        country TEXT,
        website TEXT
    )
''')
print('✅ Таблица "publisher" создана')

# Заполняем издательства
publishers = [
    ('Эксмо', 'Москва', 'Россия', 'https://eksmo.ru'),
    ('АСТ', 'Москва', 'Россия', 'https://ast.ru'),
    ('Питер', 'Санкт-Петербург', 'Россия', 'https://piter.com'),
    ('Манн, Иванов и Фербер', 'Москва', 'Россия', 'https://mif.ru'),
    ('Альпина Паблишер', 'Москва', 'Россия', 'https://alpinabook.ru'),
    ('Penguin Random House', 'New York', 'USA', 'https://penguinrandomhouse.com'),
    ('HarperCollins', 'New York', 'USA', 'https://harpercollins.com'),
    ('Springer', 'Berlin', 'Germany', 'https://springer.com'),
    ('Наука', 'Москва', 'Россия', 'https://nauka.ru'),
]

for name, city, country, website in publishers:
    cursor.execute('''
        INSERT OR IGNORE INTO publisher (publisher_name, city, country, website)
        VALUES (?, ?, ?, ?)
    ''', (name, city, country, website))
print(f'✅ Добавлено издательств: {len(publishers)}')

# =====================================================
# 3. ТАБЛИЦА ФОРМАТОВ КНИГ (book_format)
# =====================================================

cursor.execute('''
    CREATE TABLE IF NOT EXISTS book_format (
        format_id INTEGER PRIMARY KEY AUTOINCREMENT,
        format_name TEXT NOT NULL UNIQUE,
        format_description TEXT
    )
''')
print('✅ Таблица "book_format" создана')

# Заполняем форматы
formats = [
    ('Твёрдый переплёт', 'Твёрдая обложка, стандартное издание'),
    ('Мягкий переплёт', 'Мягкая обложка, облегчённый вариант'),
    ('Электронная', 'Электронная книга (EPUB, PDF, FB2)'),
    ('Аудиокнига', 'Аудиоформат (MP3, M4B, FLAC)'),
    ('Кожаный переплёт', 'Коллекционное издание в коже'),
    ('Подарочное издание', 'Увеличенный формат, иллюстрации'),
]

for name, desc in formats:
    cursor.execute('''
        INSERT OR IGNORE INTO book_format (format_name, format_description)
        VALUES (?, ?)
    ''', (name, desc))
print(f'✅ Добавлено форматов: {len(formats)}')

# =====================================================
# 4. ТАБЛИЦА СОСТОЯНИЙ КНИГ (book_condition)
# =====================================================

cursor.execute('''
    CREATE TABLE IF NOT EXISTS book_condition (
        condition_id INTEGER PRIMARY KEY AUTOINCREMENT,
        condition_name TEXT NOT NULL UNIQUE,
        condition_rank INTEGER CHECK (condition_rank BETWEEN 1 AND 5)
    )
''')
print('✅ Таблица "book_condition" создана')

# Заполняем состояния
conditions = [
    ('Новое', 5),
    ('Отличное', 4),
    ('Хорошее', 3),
    ('Удовлетворительное', 2),
    ('Плохое', 1),
]

for name, rank in conditions:
    cursor.execute('''
        INSERT OR IGNORE INTO book_condition (condition_name, condition_rank)
        VALUES (?, ?)
    ''', (name, rank))
print(f'✅ Добавлено состояний: {len(conditions)}')

# =====================================================
# 5. ТАБЛИЦА ЛОГА ОШИБОК API (api_error_log)
# =====================================================

cursor.execute('''
    CREATE TABLE IF NOT EXISTS api_error_log (
        error_id INTEGER PRIMARY KEY AUTOINCREMENT,
        isbn TEXT,
        source_api TEXT,
        error_message TEXT,
        http_status INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
''')
print('✅ Таблица "api_error_log" создана')

# Добавляем тестовые записи в лог ошибок
error_logs = [
    ('9780000000000', 'OpenLibrary', 'Книга с данным ISBN не найдена в каталоге', 404),
    ('9781234567890', 'GoogleBooks', 'Превышен лимит запросов к API', 429),
    ('9789999999999', 'OpenLibrary', 'Таймаут соединения при запросе к API', 408),
]

for isbn, source, message, status in error_logs:
    cursor.execute('''
        INSERT OR IGNORE INTO api_error_log (isbn, source_api, error_message, http_status)
        VALUES (?, ?, ?, ?)
    ''', (isbn, source, message, status))
print(f'✅ Добавлено записей в лог ошибок: {len(error_logs)}')

# =====================================================
# 6. ОБНОВЛЯЕМ СТРУКТУРУ СУЩЕСТВУЮЩИХ ТАБЛИЦ (добавляем внешние ключи)
# =====================================================

# Добавляем колонку publisher_id в таблицу book (если её нет)
try:
    cursor.execute('ALTER TABLE book ADD COLUMN publisher_id INTEGER REFERENCES publisher(publisher_id)')
    print('✅ Добавлена колонка publisher_id в таблицу book')
except sqlite3.OperationalError:
    print('⚠️ Колонка publisher_id уже существует в таблице book')

# Добавляем колонку language_id в таблицу book (если её нет)
try:
    cursor.execute('ALTER TABLE book ADD COLUMN language_id INTEGER REFERENCES language(language_id)')
    print('✅ Добавлена колонка language_id в таблицу book')
except sqlite3.OperationalError:
    print('⚠️ Колонка language_id уже существует в таблице book')

# Добавляем колонку page_count в таблицу book (если её нет)
try:
    cursor.execute('ALTER TABLE book ADD COLUMN page_count INTEGER')
    print('✅ Добавлена колонка page_count в таблицу book')
except sqlite3.OperationalError:
    print('⚠️ Колонка page_count уже существует в таблице book')

# Добавляем колонку description в таблицу book (если её нет)
try:
    cursor.execute('ALTER TABLE book ADD COLUMN description TEXT')
    print('✅ Добавлена колонка description в таблицу book')
except sqlite3.OperationalError:
    print('⚠️ Колонка description уже существует в таблице book')

# Добавляем колонку cover_url в таблицу book (если её нет)
try:
    cursor.execute('ALTER TABLE book ADD COLUMN cover_url TEXT')
    print('✅ Добавлена колонка cover_url в таблицу book')
except sqlite3.OperationalError:
    print('⚠️ Колонка cover_url уже существует в таблице book')

# Добавляем колонку average_rating в таблицу book (если её нет)
try:
    cursor.execute('ALTER TABLE book ADD COLUMN average_rating REAL')
    print('✅ Добавлена колонка average_rating в таблицу book')
except sqlite3.OperationalError:
    print('⚠️ Колонка average_rating уже существует в таблице book')

# =====================================================
# 7. ИТОГОВАЯ ПРОВЕРКА
# =====================================================

conn.commit()

print('\n' + '='*50)
print('📊 ИТОГОВАЯ СТАТИСТИКА')
print('='*50)

cursor.execute('SELECT COUNT(*) FROM language')
print(f'🌐 Языков: {cursor.fetchone()[0]}')

cursor.execute('SELECT COUNT(*) FROM publisher')
print(f'🏢 Издательств: {cursor.fetchone()[0]}')

cursor.execute('SELECT COUNT(*) FROM book_format')
print(f'📖 Форматов: {cursor.fetchone()[0]}')

cursor.execute('SELECT COUNT(*) FROM book_condition')
print(f'📊 Состояний: {cursor.fetchone()[0]}')

cursor.execute('SELECT COUNT(*) FROM api_error_log')
print(f'⚠️ Записей в логе ошибок: {cursor.fetchone()[0]}')

cursor.execute('SELECT COUNT(*) FROM book')
print(f'📚 Книг: {cursor.fetchone()[0]}')

cursor.execute('SELECT COUNT(*) FROM author')
print(f'✍️ Авторов: {cursor.fetchone()[0]}')

conn.close()

print('\n✅ Все недостающие таблицы успешно добавлены!')