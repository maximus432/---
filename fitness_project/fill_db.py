import sqlite3

def fill_data():
    conn = sqlite3.connect('fitness_club.db')
    cursor = conn.cursor()

    # Список тестовых данных
    clients = [
        ('Александр', 'Петров', '+7 (918) 123-45-67'),
        ('Мария', 'Сидорова', '+7 (928) 765-43-21'),
        ('Дмитрий', 'Волков', '+7 (905) 555-11-22'),
        ('Елена', 'Кузнецова', '+7 (961) 444-88-99'),
        ('Артем', 'Морозов', '+7 (999) 000-11-22'),
        ('Виктория', 'Белова', '+7 (918) 222-33-44')
    ]

    try:
        cursor.executemany('INSERT INTO clients (first_name, last_name, phone) VALUES (?, ?, ?)', clients)
        conn.commit()
        print(f"Добавлено {len(clients)} новых записей.")
    except sqlite3.IntegrityError:
        print("Данные уже были добавлены ранее.")
    finally:
        conn.close()

if __name__ == '__main__':
    fill_data()