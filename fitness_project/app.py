import os
from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'fitness_core_super_secret_key_123'  # Ключ для работы сессий

DATABASE = 'fitness.db'

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row  # Обращение к полям базы по именам колонок
    return conn

def init_db():
    """Инициализация таблиц базы данных при первом запуске приложения"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Включаем поддержку внешних ключей в SQLite для корректной работы ON DELETE CASCADE
    cursor.execute("PRAGMA foreign_keys = ON")
    
    # Таблица пользователей (администраторы, клиенты, тренеры)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL, -- admin, client, trainer
            full_name TEXT NOT NULL,
            phone TEXT
        )
    ''')
    
    # Таблица абонементов (связана с пользователем-клиентом через client_id)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS subscriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER NOT NULL,
            tariff_name TEXT NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            status TEXT NOT NULL, -- active, expired
            FOREIGN KEY (client_id) REFERENCES users (id) ON DELETE CASCADE
        )
    ''')
    
    # Таблица тренировок/расписания (связана с пользователем-тренером через trainer_id)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS workouts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trainer_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            workout_date TEXT NOT NULL,
            workout_time TEXT NOT NULL,
            FOREIGN KEY (trainer_id) REFERENCES users (id) ON DELETE CASCADE
        )
    ''')
    
    # Создание профиля главного администратора по умолчанию
    cursor.execute("SELECT * FROM users WHERE username = 'admin'")
    if not cursor.fetchone():
        hashed_password = generate_password_hash('admin123')
        cursor.execute('''
            INSERT INTO users (username, password, role, full_name, phone)
            VALUES ('admin', ?, 'admin', 'Главный Администратор', '+79991112233')
        ''', (hashed_password,))
        
    conn.commit()
    conn.close()

# Проверяем наличие файла БД, если его нет — создаем структуру
if not os.path.exists(DATABASE):
    init_db()


# ==========================================
# БЛОК АВТОРИЗАЦИИ И СЕССИЙ (LOGIN / LOGOUT)
# ==========================================

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for(f"{session['role']}_dashboard"))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        conn.close()
        
        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            session['full_name'] = user['full_name']
            
            return redirect(url_for(f"{user['role']}_dashboard"))
        else:
            flash('Неверное имя пользователя или пароль', 'danger')
            
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


# ==========================================
# МОДУЛЬ АДМИНИСТРАТОРА (ADMIN)
# ==========================================

@app.route('/admin/dashboard')
def admin_dashboard():
    if 'user_id' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    clients = conn.execute("SELECT * FROM users WHERE role = 'client'").fetchall()
    trainers = conn.execute("SELECT * FROM users WHERE role = 'trainer'").fetchall()
    conn.close()
    
    return render_template('admin_dashboard.html', clients=clients, trainers=trainers)

@app.route('/admin/add_user', methods=['POST'])
def add_user():
    if 'user_id' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
        
    username = request.form['username']
    password = request.form['password']
    role = request.form['role']
    full_name = request.form['full_name']
    phone = request.form['phone']
    
    hashed_password = generate_password_hash(password)
    
    conn = get_db_connection()
    try:
        conn.execute('''
            INSERT INTO users (username, password, role, full_name, phone)
            VALUES (?, ?, ?, ?, ?)
        ''', (username, hashed_password, role, full_name, phone))
        conn.commit()
        flash(f'Пользователь {full_name} успешно зарегистрирован!', 'success')
    except sqlite3.IntegrityError:
        flash('Ошибка: Этот логин уже занят другим пользователем!', 'danger')
    finally:
        conn.close()
        
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/edit_user/<int:user_id>', methods=['POST'])
def edit_user(user_id):
    """Новая функция: Редактирование данных пользователя администратором"""
    if 'user_id' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
        
    full_name = request.form['full_name']
    phone = request.form['phone']
    username = request.form['username']
    
    conn = get_db_connection()
    try:
        conn.execute('''
            UPDATE users 
            SET username = ?, full_name = ?, phone = ? 
            WHERE id = ?
        ''', (username, full_name, phone, user_id))
        conn.commit()
        flash('Данные пользователя успешно обновлены!', 'success')
    except sqlite3.IntegrityError:
        flash('Ошибка: Такой логин уже используется другим пользователем!', 'danger')
    finally:
        conn.close()
        
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/delete_user/<int:user_id>', methods=['POST', 'GET'])
def delete_user(user_id):
    """Новая функция: Полное удаление пользователя (и каскадно его абонементов)"""
    if 'user_id' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute('DELETE FROM users WHERE id = ?', (user_id,))
    conn.commit()
    conn.close()
    
    flash('Пользователь и связанные с ним данные успешно удалены.', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/sell_subscription', methods=['POST'])
def sell_subscription():
    if 'user_id' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
        
    client_id = request.form['client_id']
    tariff_name = request.form['tariff_name']
    start_date = request.form['start_date']
    end_date = request.form['end_date']
    
    conn = get_db_connection()
    conn.execute('''
        INSERT INTO subscriptions (client_id, tariff_name, start_date, end_date, status)
        VALUES (?, ?, ?, ?, 'active')
    ''', (client_id, tariff_name, start_date, end_date))
    conn.commit()
    conn.close()
    
    flash('Абонемент успешно оформлен и активирован для клиента!', 'success')
    return redirect(url_for('admin_dashboard'))


# ==========================================
# МОДУЛЬ КЛИЕНТА (CLIENT)
# ==========================================

@app.route('/client/dashboard')
def client_dashboard():
    if 'user_id' not in session or session['role'] != 'client':
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    subscription = conn.execute('''
        SELECT * FROM subscriptions 
        WHERE client_id = ? AND status = 'active'
        ORDER BY id DESC LIMIT 1
    ''', (session['user_id'],)).fetchone()
    
    workouts = conn.execute('''
        SELECT w.*, u.full_name as trainer_name 
        FROM workouts w
        JOIN users u ON w.trainer_id = u.id
    ''').fetchall()
    conn.close()
    
    return render_template('client_dashboard.html', subscription=subscription, workouts=workouts)


# ==========================================
# МОДУЛЬ ТРЕНЕРА (TRAINER)
# ==========================================

@app.route('/trainer/dashboard')
def trainer_dashboard():
    if 'user_id' not in session or session['role'] != 'trainer':
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    my_workouts = conn.execute('''
        SELECT * FROM workouts WHERE trainer_id = ?
    ''', (session['user_id'],)).fetchall()
    conn.close()
    
    return render_template('trainer_dashboard.html', workouts=my_workouts)

@app.route('/trainer/add_workout', methods=['POST'])
def add_workout():
    if 'user_id' not in session or session['role'] != 'trainer':
        return redirect(url_for('login'))
        
    title = request.form['title']
    workout_date = request.form['workout_date']
    workout_time = request.form['workout_time']
    
    conn = get_db_connection()
    conn.execute('''
        INSERT INTO workouts (trainer_id, title, workout_date, workout_time)
        VALUES (?, ?, ?, ?)
    ''', (session['user_id'], title, workout_date, workout_time))
    conn.commit()
    conn.close()
    
    flash('Занятие успешно добавлено в расписание!', 'success')
    return redirect(url_for('trainer_dashboard'))

@app.route('/trainer/edit_workout/<int:workout_id>', methods=['POST'])
def edit_workout(workout_id):
    """Новая функция: Редактирование параметров тренировки тренером"""
    if 'user_id' not in session or session['role'] != 'trainer':
        return redirect(url_for('login'))
        
    title = request.form['title']
    workout_date = request.form['workout_date']
    workout_time = request.form['workout_time']
    
    conn = get_db_connection()
    conn.execute('''
        UPDATE workouts 
        SET title = ?, workout_date = ?, workout_time = ? 
        WHERE id = ? AND trainer_id = ?
    ''', (title, workout_date, workout_time, workout_id, session['user_id']))
    conn.commit()
    conn.close()
    
    flash('Параметры тренировки успешно изменены!', 'success')
    return redirect(url_for('trainer_dashboard'))

@app.route('/trainer/delete_workout/<int:workout_id>', methods=['POST', 'GET'])
def delete_workout(workout_id):
    """Новая функция: Удаление тренировки тренером"""
    if 'user_id' not in session or session['role'] != 'trainer':
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    conn.execute('DELETE FROM workouts WHERE id = ? AND trainer_id = ?', (workout_id, session['user_id']))
    conn.commit()
    conn.close()
    
    flash('Занятие успешно удалено из расписания.', 'success')
    return redirect(url_for('trainer_dashboard'))


if __name__ == '__main__':
    app.run(debug=True)