import os
import hashlib
import sqlite3
from functools import wraps
from datetime import datetime

from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_file

app = Flask(__name__)
app.secret_key = 'supersecretkeychangeme'  # В продакшене сменить!

# ------------------- Конфигурация БД (SQLite) -------------------
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'parad_zvezd.db')

# Данные для входа администратора
ADMIN_USERNAME = 'admin'
ADMIN_PASSWORD_HASH = hashlib.sha256('anosov.museum'.encode()).hexdigest()

# Список всех номинаций (id => название)
NOMINATIONS = {
    'zvezdnyy-lider': 'Звёздный лидер',
    'zvezdnyy-nastavnik': 'Звёздный наставник',
    'zvezdnyy-partner': 'Звёздный партнёр',
    'zvezdnyy-aktiv': 'Звёздный актив',
    'zvezdnaya-stsena': 'Звёздная сцена',
    'zvezdnaya-podderzhka': 'Звёздная поддержка',
    'zvezdnyy-start': 'Звёздный старт',
    'zvezdnoe-stremlenie': 'Звёздное стремление',
    'zvezdnoe-masterstvo': 'Звёздное мастерство',
    'zvezdnyy-intellekt': 'Звёздный интеллект',
    'zvezdnyy-vypusknik': 'Звёздный выпускник'
}


# ------------------- Вспомогательные функции БД -------------------
def get_db_connection():
    """Создаёт и возвращает соединение с БД"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Создаёт таблицы, если их нет, и заполняет номинации"""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        # Таблица номинаций
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS nominations (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL
            )
        ''')
        # Таблица записей (фото+описание)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nomination_id TEXT NOT NULL,
                photo TEXT NOT NULL,
                description TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (nomination_id) REFERENCES nominations(id) ON DELETE CASCADE
            )
        ''')
        # Таблица сценариев
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS scenarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                file_name TEXT NOT NULL,
                file_data TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        ''')

        # Заполнение таблицы nominations, если пусто
        cursor.execute('SELECT COUNT(*) as cnt FROM nominations')
        if cursor.fetchone()['cnt'] == 0:
            for nom_id, nom_name in NOMINATIONS.items():
                cursor.execute('INSERT INTO nominations (id, name) VALUES (?, ?)', (nom_id, nom_name))
        conn.commit()
    finally:
        conn.close()


# Вызов инициализации при старте
init_db()


# ------------------- Декоратор авторизации -------------------
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('is_admin'):
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated


# ------------------- Пользовательские маршруты -------------------
@app.route('/')
def index():
    return render_template('index.html')


@app.route('/nominations')
def nominations_public():
    return render_template('nominations-public.html')


@app.route('/nomination/<nomination_id>')
def nomination_public(nomination_id):
    if nomination_id not in NOMINATIONS:
        return "Номинация не найдена", 404
    return render_template('nomination-public.html', nomination_id=nomination_id)


@app.route('/scenarios')
def scenarios_public():
    return render_template('scenarios-public.html')


# ------------------- API (публичные) -------------------
@app.route('/api/nomination/<nomination_id>')
def api_get_nomination(nomination_id):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT id, photo, description FROM entries WHERE nomination_id = ? ORDER BY created_at', (nomination_id,))
        entries = cursor.fetchall()
        # Преобразуем id в строку для совместимости со старым форматом
        result = []
        for e in entries:
            result.append({
                'id': str(e['id']),
                'photo': e['photo'],
                'description': e['description']
            })
        return jsonify(result)
    finally:
        conn.close()


@app.route('/api/scenarios')
def api_get_scenarios():
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT id, name, file_name, file_data, created_at FROM scenarios ORDER BY created_at DESC')
        scenarios = cursor.fetchall()
        result = []
        for s in scenarios:
            result.append({
                'id': str(s['id']),
                'name': s['name'],
                'file_name': s['file_name'],
                'file_data': s['file_data'],
                'created_at': s['created_at']
            })
        return jsonify(result)
    finally:
        conn.close()


# ------------------- Административные маршруты -------------------
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        pwd_hash = hashlib.sha256(password.encode()).hexdigest()
        if username == ADMIN_USERNAME and pwd_hash == ADMIN_PASSWORD_HASH:
            session['is_admin'] = True
            return redirect(url_for('admin_panel'))
        return render_template('login.html', error='Неверный логин или пароль')
    return render_template('login.html')


@app.route('/admin/logout')
def admin_logout():
    session.pop('is_admin', None)
    return redirect(url_for('index'))


@app.route('/admin/')
@login_required
def admin_panel():
    return render_template('admin-panel.html')


@app.route('/admin/nominations')
@login_required
def admin_nominations():
    return render_template('admin-nominations.html')


@app.route('/admin/nomination/<nomination_id>')
@login_required
def admin_nomination(nomination_id):
    if nomination_id not in NOMINATIONS:
        return "Номинация не найдена", 404
    return render_template('admin-nomination.html', nomination_id=nomination_id)


@app.route('/admin/scenarios')
@login_required
def admin_scenarios():
    return render_template('admin-scenarios.html')


# ------------------- API для администратора (защищённые) -------------------
@app.route('/api/admin/nomination/<nomination_id>', methods=['GET', 'POST', 'PUT', 'DELETE'])
@login_required
def api_admin_nomination(nomination_id):
    if nomination_id not in NOMINATIONS:
        return jsonify({'error': 'Номинация не найдена'}), 404

    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        if request.method == 'GET':
            cursor.execute('SELECT id, photo, description FROM entries WHERE nomination_id = ? ORDER BY created_at', (nomination_id,))
            entries = cursor.fetchall()
            result = []
            for e in entries:
                result.append({
                    'id': str(e['id']),
                    'photo': e['photo'],
                    'description': e['description']
                })
            return jsonify(result)

        elif request.method == 'POST':
            data = request.json
            if not data.get('photo') or not data.get('description'):
                return jsonify({'error': 'Фото и описание обязательны'}), 400
            cursor.execute(
                'INSERT INTO entries (nomination_id, photo, description) VALUES (?, ?, ?)',
                (nomination_id, data['photo'], data['description'])
            )
            conn.commit()
            new_id = cursor.lastrowid
            return jsonify({'id': str(new_id), 'photo': data['photo'], 'description': data['description']}), 201

        elif request.method == 'PUT':
            data = request.json
            entry_id = data.get('id')
            if not entry_id:
                return jsonify({'error': 'id не указан'}), 400
            cursor.execute(
                'UPDATE entries SET photo = ?, description = ? WHERE id = ? AND nomination_id = ?',
                (data['photo'], data['description'], entry_id, nomination_id)
            )
            conn.commit()
            if cursor.rowcount == 0:
                return jsonify({'error': 'Запись не найдена'}), 404
            return jsonify({'id': entry_id, 'photo': data['photo'], 'description': data['description']})

        elif request.method == 'DELETE':
            entry_id = request.args.get('id')
            if not entry_id:
                return jsonify({'error': 'id не указан'}), 400
            cursor.execute('DELETE FROM entries WHERE id = ? AND nomination_id = ?', (entry_id, nomination_id))
            conn.commit()
            if cursor.rowcount == 0:
                return jsonify({'error': 'Запись не найдена'}), 404
            return jsonify({'success': True})
    finally:
        conn.close()


@app.route('/api/admin/scenarios', methods=['GET', 'POST', 'DELETE'])
@login_required
def api_admin_scenarios():
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        if request.method == 'GET':
            cursor.execute('SELECT id, name, file_name, file_data, created_at FROM scenarios ORDER BY created_at DESC')
            scenarios = cursor.fetchall()
            result = []
            for s in scenarios:
                result.append({
                    'id': str(s['id']),
                    'name': s['name'],
                    'file_name': s['file_name'],
                    'file_data': s['file_data'],
                    'created_at': s['created_at']
                })
            return jsonify(result)

        elif request.method == 'POST':
            data = request.json
            if not data.get('name') or not data.get('fileData'):
                return jsonify({'error': 'Название и ссылка на файл обязательны'}), 400
            created_at = datetime.now().strftime('%d.%m.%Y')
            cursor.execute(
                'INSERT INTO scenarios (name, file_name, file_data, created_at) VALUES (?, ?, ?, ?)',
                (data['name'], data.get('fileName', ''), data['fileData'], created_at)
            )
            conn.commit()
            new_id = cursor.lastrowid
            return jsonify({'id': str(new_id), 'name': data['name'], 'fileName': data.get('fileName', ''), 'fileData': data['fileData'], 'createdAt': created_at}), 201

        elif request.method == 'DELETE':
            scenario_id = request.args.get('id')
            if not scenario_id:
                return jsonify({'error': 'id не указан'}), 400
            cursor.execute('DELETE FROM scenarios WHERE id = ?', (scenario_id,))
            conn.commit()
            if cursor.rowcount == 0:
                return jsonify({'error': 'Сценарий не найден'}), 404
            return jsonify({'success': True})
    finally:
        conn.close()


@app.route('/api/admin/export')
@login_required
def admin_export():
    conn = get_db_connection()
    try:
        # Экспортируем все данные
        cursor = conn.cursor()
        cursor.execute('SELECT id, name FROM nominations')
        nominations_rows = cursor.fetchall()
        nominations_data = {}
        for row in nominations_rows:
            nom_id = row['id']
            cursor.execute('SELECT id, photo, description FROM entries WHERE nomination_id = ?', (nom_id,))
            entries = cursor.fetchall()
            result_entries = []
            for e in entries:
                result_entries.append({
                    'id': str(e['id']),
                    'photo': e['photo'],
                    'description': e['description']
                })
            nominations_data[nom_id] = result_entries

        cursor.execute('SELECT id, name, file_name, file_data, created_at FROM scenarios')
        scenarios_rows = cursor.fetchall()
        scenarios_data = []
        for s in scenarios_rows:
            scenarios_data.append({
                'id': str(s['id']),
                'name': s['name'],
                'fileName': s['file_name'],
                'fileData': s['file_data'],
                'createdAt': s['created_at']
            })

        all_data = {
            'exportDate': datetime.now().isoformat(),
            'nominations': nominations_data,
            'scenarios': scenarios_data
        }
        # Временно сохраняем файл для скачивания
        import tempfile
        import json
        fd, path = tempfile.mkstemp(suffix='.json')
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(all_data, f, ensure_ascii=False, indent=2)
        return send_file(path, as_attachment=True,
                         download_name=f'parad-zvezd-backup-{datetime.now().strftime("%Y%m%d")}.json')
    finally:
        conn.close()


@app.route('/api/admin/import', methods=['POST'])
@login_required
def admin_import():
    if 'file' not in request.files:
        return jsonify({'error': 'Файл не загружен'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'Файл не выбран'}), 400
    try:
        import json
        data = json.load(file)
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            # Очищаем существующие данные
            cursor.execute('DELETE FROM entries')
            cursor.execute('DELETE FROM scenarios')
            # Импортируем номинации (записи)
            if 'nominations' in data:
                for nom_id, entries in data['nominations'].items():
                    if nom_id in NOMINATIONS:  # только валидные
                        for entry in entries:
                            cursor.execute(
                                'INSERT INTO entries (nomination_id, photo, description) VALUES (?, ?, ?)',
                                (nom_id, entry['photo'], entry['description'])
                            )
            # Импортируем сценарии
            if 'scenarios' in data:
                for sc in data['scenarios']:
                    cursor.execute(
                        'INSERT INTO scenarios (name, file_name, file_data, created_at) VALUES (?, ?, ?, ?)',
                        (sc['name'], sc.get('fileName', ''), sc['fileData'], sc.get('createdAt', datetime.now().strftime('%d.%m.%Y')))
                    )
            conn.commit()
            return jsonify({'success': True})
        finally:
            conn.close()
    except Exception as e:
        return jsonify({'error': f'Ошибка импорта: {str(e)}'}), 400

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)