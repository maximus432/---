from flask import Flask, render_template, request, redirect, url_for, flash
import sqlite3
import re

app = Flask(__name__)
app.secret_key = 'fitness_club_secret_key'  # Необходимо для работы сообщений
DB_NAME = 'fitness_club.db'

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    # Включаем внешние ключи
    cursor.execute("PRAGMA foreign_keys = ON")
    
    # Таблица клиентов
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS clients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            phone TEXT UNIQUE NOT NULL,
            registration_date DATE DEFAULT CURRENT_DATE
        )
    ''')
    # Таблица абонементов с каскадным удалением
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS subscriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER,
            plan_name TEXT,
            price REAL,
            status TEXT DEFAULT 'Активен',
            FOREIGN KEY (client_id) REFERENCES clients (id) ON DELETE CASCADE
        )
    ''')
    conn.commit()
    conn.close()

def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.execute("PRAGMA foreign_keys = ON") # Важно для каскадного удаления
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/', methods=['GET', 'POST'])
def index():
    conn = get_db_connection()
    if request.method == 'POST':
        first_name = request.form.get('first_name', '').strip()
        last_name = request.form.get('last_name', '').strip()
        phone = request.form.get('phone', '').strip()

        # Регулярное выражение для валидации телефона: цифры, пробелы, дефисы, +
        phone_pattern = re.compile(r'^\+?[\d\s\-]{7,15}$')

        if not first_name or not last_name or not phone:
            flash("Все поля обязательны для заполнения!", "warning")
        elif not phone_pattern.match(phone):
            flash("Некорректный формат телефона!", "danger")
        else:
            try:
                conn.execute('INSERT INTO clients (first_name, last_name, phone) VALUES (?, ?, ?)',
                             (first_name, last_name, phone))
                conn.commit()
                flash("Клиент успешно добавлен!", "success")
            except sqlite3.IntegrityError:
                flash("Ошибка: Клиент с таким номером уже существует.", "danger")
        
        conn.close()
        return redirect(url_for('index'))

    clients = conn.execute('SELECT * FROM clients ORDER BY id DESC').fetchall()
    subs = conn.execute('''
        SELECT s.*, c.first_name, c.last_name 
        FROM subscriptions s 
        JOIN clients c ON s.client_id = c.id
    ''').fetchall()
    
    conn.close()
    return render_template('index.html', clients=clients, subs=subs)

@app.route('/delete/<int:id>')
def delete_client(id):
    conn = get_db_connection()
    conn.execute('DELETE FROM clients WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    flash("Клиент успешно удален.", "info")
    return redirect(url_for('index'))

@app.route('/buy_sub', methods=['POST'])
def buy_sub():
    client_id = request.form.get('client_id')
    plan = request.form.get('plan')
    prices = {"Базовый": 2500, "Стандарт": 4500, "Безлимит": 7000}
    
    if client_id and plan in prices:
        conn = get_db_connection()
        # 1. Сначала помечаем все текущие абонементы клиента как 'Истек'
        conn.execute('''
            UPDATE subscriptions 
            SET status = 'Истек' 
            WHERE client_id = ? AND status = 'Активен'
        ''', (client_id,))
        
        # 2. Добавляем новый абонемент
        conn.execute('''
            INSERT INTO subscriptions (client_id, plan_name, price, status) 
            VALUES (?, ?, ?, 'Активен')
        ''', (client_id, plan, prices.get(plan, 0)))
        
        conn.commit()
        conn.close()
        flash("Абонемент успешно оформлен! Предыдущий деактивирован.", "success")
    else:
        flash("Ошибка оформления абонемента.", "danger")
    return redirect(url_for('index'))

if __name__ == '__main__':
    init_db()
    app.run(debug=True)