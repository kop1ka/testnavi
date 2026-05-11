"""
Flask приложение для управления мультимедийным контентом
с парсером FTP-каталога и возможностью сохранения постоянных элементов
"""

import os
import json
import re
import threading
import requests
from datetime import datetime, timedelta
from urllib.parse import unquote, urlparse
from flask import Flask, render_template_string, request, jsonify, send_from_directory, redirect, url_for, session, flash, Response
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_wtf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from config.settings import (
    DATA_DIR, CATALOG_FILE, PERMANENT_FILE, USERS_FILE, PARSER_IMAGES_FILE, SECRET_KEY,
    FTP_BASE_URL, PARSER_MAX_DEPTH, PARSER_TIMEOUT,
    RATELIMIT_STORAGE_URI, RATELIMIT_DEFAULT, RATELIMIT_LOGIN, RATELIMIT_ENABLED,
    LOGIN_VIEW, LOGIN_MESSAGE, SESSION_PROTECTION
)

from utils.data_utils import (
    ensure_data_dir, load_json_file, save_json_file, get_current_timestamp, get_full_timestamp,
    load_users, save_users, load_catalog, save_catalog, load_permanent_items, save_permanent_items
)
from utils.parser_utils import extract_items_from_html, parse_folder
from utils.auth_utils import User, hash_password, verify_password, admin_required_decorator
from utils.catalog_utils import (
    get_item_path, mark_permanent_recursive, merge_with_permanent,
    find_item_by_path, delete_item_by_path, update_item_by_path
)

PROJECTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'projects')

app = Flask(__name__, static_folder='.', static_url_path='')
app.secret_key = SECRET_KEY

MIME_TYPES = {'.css': 'text/css; charset=utf-8', '.js': 'application/javascript; charset=utf-8',
              '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.gif': 'image/gif',
              '.webp': 'image/webp', '.svg': 'image/svg+xml', '.html': 'text/html; charset=utf-8'}

@app.after_request
def add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, X-CSRFToken'
    if not response.headers.get('Content-Type'):
        ext = os.path.splitext(request.path)[1].lower()
        if ext in MIME_TYPES:
            response.headers['Content-Type'] = MIME_TYPES[ext]
    return response

csrf = CSRFProtect(app)

def limiter_enabled():
    if request.path.startswith(('/page/', '/static/', '/projects/', '/css/', '/js/')) or request.path == '/api/proxy-image':
        return False
    return RATELIMIT_ENABLED

limiter = Limiter(key_func=get_remote_address, app=app, default_limits=RATELIMIT_DEFAULT,
                  storage_uri=RATELIMIT_STORAGE_URI, enabled=limiter_enabled)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = LOGIN_VIEW
login_manager.login_message = LOGIN_MESSAGE
login_manager.session_protection = SESSION_PROTECTION

parser_status = {'running': False, 'last_run': None, 'message': 'Парсер не запущен', 'images': []}

@login_manager.user_loader
def load_user(user_id):
    users_data = load_users(USERS_FILE, hash_password)
    for user in users_data.get('users', []):
        if str(user['id']) == str(user_id):
            return User(user['id'], user['username'], user.get('is_admin', False))
    return None

def run_parser_task():
    global parser_status
    try:
        parser_status['running'] = True
        parser_status['message'] = 'Парсинг запущен...'

        existing_images_data = load_json_file(PARSER_IMAGES_FILE, {'images': []})
        existing_images = set(existing_images_data.get('images', []))

        items = parse_folder(FTP_BASE_URL, max_depth=PARSER_MAX_DEPTH, timeout=PARSER_TIMEOUT)

        new_parser_images = []
        def collect_images(items_list):
            for item in items_list:

                if item.get('children') is None:

                    url = item.get('url', '')
                    if url and (url.lower().endswith('.png') or url.lower().endswith('.jpg') or 
                                url.lower().endswith('.jpeg') or url.lower().endswith('.gif') or 
                                url.lower().endswith('.webp')):
                        if url not in new_parser_images:
                            new_parser_images.append(url)
                else:

                    if item.get('children'):
                        collect_images(item['children'])
        
        collect_images(items)

        all_images = list(existing_images)
        for img_url in new_parser_images:
            if img_url not in existing_images:
                all_images.append(img_url)

        save_json_file(PARSER_IMAGES_FILE, {'images': all_images})

        parser_status['images'] = all_images

        permanent_items = load_permanent_items(PERMANENT_FILE)
        permanent_paths = set(permanent_items.get('permanent_items', []))

        existing_catalog = load_catalog(CATALOG_FILE)
        existing_children = existing_catalog.get('children', [])

        merged_children = merge_with_permanent(items, existing_children, permanent_paths)

        existing_catalog['children'] = merged_children
        existing_catalog['modified'] = get_current_timestamp()
        save_catalog(CATALOG_FILE, existing_catalog)

        parser_status['last_run'] = get_full_timestamp()
        parser_status['message'] = f'Парсинг завершён успешно. Найдено элементов: {len(items)}. Всего изображений: {len(all_images)}'
        
    except Exception as e:
        parser_status['message'] = f'Ошибка парсинга: {str(e)}'
    finally:
        parser_status['running'] = False

@app.route('/login', methods=['GET', 'POST'])
@limiter.limit(RATELIMIT_LOGIN)  # Ограничение частоты запросов для защиты от брутфорса
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    error = None
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        remember = request.form.get('remember', False)
        
        if not username or not password:
            error = 'Введите имя пользователя и пароль'
        else:
            users_data = load_users(USERS_FILE, hash_password)
            user_found = None
            for user in users_data.get('users', []):
                if user['username'] == username:
                    user_found = user
                    break
            
            if user_found and verify_password(password, user_found['password_hash']):
                user_obj = User(user_found['id'], user_found['username'], user_found.get('is_admin', False))
                login_user(user_obj, remember=remember)
                next_page = request.args.get('next')
                flash('Вы успешно вошли в систему', 'success')
                return redirect(next_page if next_page else url_for('index'))
            else:
                error = 'Неверное имя пользователя или пароль'
    
    return render_template_string('''
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Вход в систему</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        body {
            font-family: Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
        }
        .login-container {
            background: white;
            padding: 40px;
            border-radius: 10px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.2);
            width: 100%;
            max-width: 400px;
        }
        h1 {
            text-align: center;
            color: #333;
            margin-bottom: 30px;
            font-size: 24px;
        }
        .form-group {
            margin-bottom: 20px;
        }
        label {
            display: block;
            margin-bottom: 8px;
            color: #555;
            font-weight: bold;
        }
        input[type="text"],
        input[type="password"] {
            width: 100%;
            padding: 12px 15px;
            border: 2px solid #e0e0e0;
            border-radius: 5px;
            font-size: 16px;
            transition: border-color 0.3s;
        }
        input[type="text"]:focus,
        input[type="password"]:focus {
            outline: none;
            border-color: #667eea;
        }
        .checkbox-group {
            display: flex;
            align-items: center;
            margin-bottom: 20px;
        }
        .checkbox-group input {
            margin-right: 10px;
        }
        .checkbox-group label {
            margin: 0;
            font-weight: normal;
            cursor: pointer;
        }
        .btn-submit {
            width: 100%;
            padding: 14px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 5px;
            font-size: 16px;
            font-weight: bold;
            cursor: pointer;
            transition: transform 0.2s, box-shadow 0.2s;
        }
        .btn-submit:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 20px rgba(102, 126, 234, 0.4);
        }
        .error-message {
            background: #fee;
            color: #c00;
            padding: 12px;
            border-radius: 5px;
            margin-bottom: 20px;
            text-align: center;
            border: 1px solid #fcc;
        }
        .flash-messages {
            margin-bottom: 20px;
        }
        .flash-message {
            padding: 12px;
            border-radius: 5px;
            margin-bottom: 10px;
            text-align: center;
        }
        .flash-success {
            background: #efe;
            color: #0a0;
            border: 1px solid #cfc;
        }
        .flash-error {
            background: #fee;
            color: #c00;
            border: 1px solid #fcc;
        }
        .flash-info {
            background: #eef;
            color: #00a;
            border: 1px solid #ccf;
        }
    </style>
</head>
<body>
    <div class="login-container">
        <h1>Вход в систему</h1>
        
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                <div class="flash-messages">
                    {% for category, message in messages %}
                        <div class="flash-message flash-{{ category }}">{{ message }}</div>
                    {% endfor %}
                </div>
            {% endif %}
        {% endwith %}
        
        {% if error %}
            <div class="error-message">{{ error }}</div>
        {% endif %}
        
        <form method="POST" action="{{ url_for('login') }}">
            <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
            
            <div class="form-group">
                <label for="username">Имя пользователя</label>
                <input type="text" id="username" name="username" required autofocus>
            </div>
            
            <div class="form-group">
                <label for="password">Пароль</label>
                <input type="password" id="password" name="password" required>
            </div>
            
            <div class="checkbox-group">
                <input type="checkbox" id="remember" name="remember">
                <label for="remember">Запомнить меня</label>
            </div>
            
            <button type="submit" class="btn-submit">Войти</button>
        </form>
    </div>
</body>
</html>
''', error=error)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Вы вышли из системы', 'info')
    return redirect(url_for('index'))

@app.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        current_password = request.form.get('current_password', '')
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')
        
        if not current_password or not new_password or not confirm_password:
            flash('Заполните все поля', 'error')
            return redirect(url_for('change_password'))
        
        if new_password != confirm_password:
            flash('Новые пароли не совпадают', 'error')
            return redirect(url_for('change_password'))
        
        if len(new_password) < 6:
            flash('Пароль должен быть не менее 6 символов', 'error')
            return redirect(url_for('change_password'))

        users_data = load_users(USERS_FILE, hash_password)
        user_found = None
        user_index = None
        for idx, user in enumerate(users_data.get('users', [])):
            if user['username'] == current_user.username:
                user_found = user
                user_index = idx
                break
        
        if not user_found or not verify_password(current_password, user_found['password_hash']):
            flash('Текущий пароль неверен', 'error')
            return redirect(url_for('change_password'))

        users_data['users'][user_index]['password_hash'] = hash_password(new_password)
        save_users(USERS_FILE, users_data)
        
        flash('Пароль успешно изменён', 'success')
        return redirect(url_for('admin'))
    
    return render_template_string('''
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Изменение пароля</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        body {
            font-family: Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
        }
        .container {
            background: white;
            padding: 40px;
            border-radius: 10px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.2);
            width: 100%;
            max-width: 450px;
        }
        h1 {
            text-align: center;
            color: #333;
            margin-bottom: 30px;
            font-size: 24px;
        }
        .form-group {
            margin-bottom: 20px;
        }
        label {
            display: block;
            margin-bottom: 8px;
            color: #555;
            font-weight: bold;
        }
        input[type="password"] {
            width: 100%;
            padding: 12px 15px;
            border: 2px solid #e0e0e0;
            border-radius: 5px;
            font-size: 16px;
            transition: border-color 0.3s;
        }
        input[type="password"]:focus {
            outline: none;
            border-color: #667eea;
        }
        .btn-submit {
            width: 100%;
            padding: 14px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 5px;
            font-size: 16px;
            font-weight: bold;
            cursor: pointer;
            transition: transform 0.2s, box-shadow 0.2s;
        }
        .btn-submit:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 20px rgba(102, 126, 234, 0.4);
        }
        .btn-secondary {
            display: block;
            width: 100%;
            padding: 14px;
            background: #f0f0f0;
            color: #333;
            border: none;
            border-radius: 5px;
            font-size: 16px;
            cursor: pointer;
            margin-top: 10px;
            text-align: center;
            text-decoration: none;
        }
        .btn-secondary:hover {
            background: #e0e0e0;
        }
        .flash-messages {
            margin-bottom: 20px;
        }
        .flash-message {
            padding: 12px;
            border-radius: 5px;
            margin-bottom: 10px;
            text-align: center;
        }
        .flash-success {
            background: #efe;
            color: #0a0;
            border: 1px solid #cfc;
        }
        .flash-error {
            background: #fee;
            color: #c00;
            border: 1px solid #fcc;
        }
        .password-requirements {
            background: #f8f9fa;
            padding: 12px;
            border-radius: 5px;
            margin-bottom: 20px;
            font-size: 14px;
            color: #666;
        }
        .password-requirements ul {
            margin-left: 20px;
            margin-top: 8px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Изменение пароля</h1>
        
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                <div class="flash-messages">
                    {% for category, message in messages %}
                        <div class="flash-message flash-{{ category }}">{{ message }}</div>
                    {% endfor %}
                </div>
            {% endif %}
        {% endwith %}
        
        <div class="password-requirements">
            <strong>Требования к паролю:</strong>
            <ul>
                <li>Минимум 6 символов</li>
                <li>Подтверждение пароля должно совпадать</li>
            </ul>
        </div>
        
        <form method="POST" action="{{ url_for('change_password') }}">
            <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
            
            <div class="form-group">
                <label for="current_password">Текущий пароль</label>
                <input type="password" id="current_password" name="current_password" required autofocus>
            </div>
            
            <div class="form-group">
                <label for="new_password">Новый пароль</label>
                <input type="password" id="new_password" name="new_password" required>
            </div>
            
            <div class="form-group">
                <label for="confirm_password">Подтверждение нового пароля</label>
                <input type="password" id="confirm_password" name="confirm_password" required>
            </div>
            
            <button type="submit" class="btn-submit">Изменить пароль</button>
            <a href="{{ url_for('admin') }}" class="btn-secondary">Отмена</a>
        </form>
    </div>
</body>
</html>
''')

@app.route('/')
def index():
    response = send_from_directory('.', 'index.html')

    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

@app.route('/admin')
@login_required
@admin_required_decorator  # Только для администраторов
def admin():
    response = send_from_directory('.', 'admin.html')

    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

@app.route('/api/catalog')
def get_catalog():
    catalog = load_catalog(CATALOG_FILE)
    permanent_items = load_permanent_items(PERMANENT_FILE)
    permanent_paths = set(permanent_items.get('permanent_items', []))
    mark_permanent_recursive(catalog.get('children', []), permanent_paths)

    if os.path.exists(PROJECTS_DIR):
        for project_name in os.listdir(PROJECTS_DIR):
            project_path = os.path.join(PROJECTS_DIR, project_name)
            if os.path.isdir(project_path):
                index_html_path = os.path.join(project_path, 'index.html')
                if os.path.exists(index_html_path):
                    project_item = {
                        "name": project_name,
                        "icon": "page/logo.png",
                        "children": None,
                        "url": f"/projects/{project_name}/index.html",
                        "modified": datetime.fromtimestamp(os.path.getmtime(index_html_path)).strftime('%Y-%m-%d %H:%M'),
                        "permanent": True
                    }
                    catalog["children"].insert(0, project_item)
    
    response = jsonify(catalog)

    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

@app.route('/api/parser/status')
@login_required
@admin_required_decorator
def get_parser_status():
    return jsonify(parser_status)

@app.route('/api/parser/start', methods=['POST'])
@login_required
@admin_required_decorator
@csrf.exempt  # Освободить от CSRF защиты
def start_parser():
    if not parser_status['running']:
        thread = threading.Thread(target=run_parser_task)
        thread.daemon = True
        thread.start()
        return jsonify({'status': 'started'})
    return jsonify({'status': 'already_running'})

@app.route('/api/import/json', methods=['POST'])
@login_required
@admin_required_decorator
@csrf.exempt  # Освободить от CSRF защиты
def import_json():
    try:
        data = request.json
        json_data = data.get('json_data')
        parent_path = data.get('parent_path', '')
        
        if not json_data:
            return jsonify({'error': 'JSON данные не предоставлены'}), 400

        imported_items = json.loads(json_data)

        catalog = load_catalog(CATALOG_FILE)

        if not parent_path:
            target_list = catalog['children']
        else:
            parent_item = find_item_by_path(catalog['children'], parent_path)
            if parent_item and 'children' in parent_item:
                target_list = parent_item['children']
            else:
                return jsonify({'error': 'Родительская папка не найдена'}), 404

        def add_imported_items(items, target):
            if isinstance(items, list):
                for item in items:
                    if isinstance(item, dict):
                        target.append(item)
                    elif isinstance(item, list):
                        add_imported_items(item, target)
            elif isinstance(items, dict):
                target.append(items)
        
        add_imported_items(imported_items, target_list)
        save_catalog(CATALOG_FILE, catalog)
        
        return jsonify({'status': 'success', 'message': f'Импортировано элементов: {len(target_list)}'})
    
    except json.JSONDecodeError as e:
        return jsonify({'error': f'Ошибка парсинга JSON: {str(e)}'}), 400
    except Exception as e:
        return jsonify({'error': f'Ошибка импорта: {str(e)}'}), 500

@app.route('/api/permanent', methods=['GET', 'POST', 'DELETE'])
@login_required
@admin_required_decorator
@csrf.exempt  # Освободить от CSRF защиты
def permanent_api():
    permanent_data = load_permanent_items(PERMANENT_FILE)
    
    if request.method == 'POST':
        path = request.json.get('path')
        if path and path not in permanent_data['permanent_items']:
            permanent_data['permanent_items'].append(path)
            save_permanent_items(PERMANENT_FILE, permanent_data)
        return jsonify({'status': 'success'})
    
    elif request.method == 'DELETE':
        path = request.json.get('path')
        if path in permanent_data['permanent_items']:
            permanent_data['permanent_items'].remove(path)
            save_permanent_items(PERMANENT_FILE, permanent_data)
        return jsonify({'status': 'success'})
    
    return jsonify(permanent_data)

@app.route('/api/items', methods=['POST', 'PUT', 'DELETE'])
@login_required
@admin_required_decorator
@csrf.exempt  # Освободить от CSRF защиты
def items_api():
    catalog = load_catalog(CATALOG_FILE)
    data = request.json
    path = data.get('path', '')
    
    if request.method == 'POST':
        name = data.get('name')
        parent_path = data.get('parent_path', '')
        icon = data.get('icon', 'folder.png')
        url = data.get('url')

        if not parent_path:
            target_list = catalog['children']
        else:
            parent_item = find_item_by_path(catalog['children'], parent_path)
            if parent_item and 'children' in parent_item:
                target_list = parent_item['children']
            else:
                return jsonify({'error': 'Parent not found'}), 404

        new_item = {'name': name, 'icon': icon, 'children': []}
        if url:
            new_item['url'] = url
        target_list.append(new_item)
        save_catalog(CATALOG_FILE, catalog)
        response = jsonify({'status': 'success'})
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        return response
    
    elif request.method == 'DELETE':
        if delete_item_by_path(catalog['children'], path):
            save_catalog(CATALOG_FILE, catalog)
            response = jsonify({'status': 'success'})
            response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
            return response
        return jsonify({'error': 'Not found'}), 404
    
    elif request.method == 'PUT':
        updates = data.get('updates', {})

        if 'icon' in updates and updates['icon']:

            item = find_item_by_path(catalog['children'], path)
            if item:
                updates['permanent'] = True
        
        if update_item_by_path(catalog['children'], path, updates):
            save_catalog(CATALOG_FILE, catalog)
            response = jsonify({'status': 'success'})
            response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
            return response
        return jsonify({'error': 'Not found'}), 404
    
    return jsonify({'error': 'Invalid method'}), 400

@app.route('/api/images')
def get_images():
    page_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'page')
    images = []
    seen_paths = set()  # Для предотвращения дубликатов

    if os.path.exists(page_dir):
        for filename in os.listdir(page_dir):
            if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp')):
                path = f'page/{filename}'
                if path not in seen_paths:
                    images.append({'name': filename, 'path': path})
                    seen_paths.add(path)

    parser_images_data = load_json_file(PARSER_IMAGES_FILE, default={'images': []})
    parser_images = parser_images_data.get('images', [])

    for icon_url in parser_images:
        if icon_url and icon_url not in seen_paths:

            try:

                decoded_url = unquote(icon_url)
                filename = decoded_url.split('/')[-1]
            except:
                filename = os.path.basename(icon_url)
            images.append({'name': filename, 'path': icon_url})
            seen_paths.add(icon_url)

    if parser_status.get('images'):
        for icon_url in parser_status['images']:
            if icon_url and icon_url not in seen_paths:
                try:
                    decoded_url = unquote(icon_url)
                    filename = decoded_url.split('/')[-1]
                except:
                    filename = os.path.basename(icon_url)
                images.append({'name': filename, 'path': icon_url})
                seen_paths.add(icon_url)

    response = Response(
        json.dumps(images, ensure_ascii=False),
        mimetype='application/json; charset=utf-8'
    )

    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

@app.route('/page/<path:filename>')
def serve_page_image(filename):
    page_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'page')
    return send_from_directory(page_dir, filename, max_age=86400)  # Кэширование на 24 часа

@app.route('/css/<path:filename>')
def serve_css(filename):
    css_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'css')
    response = send_from_directory(css_dir, filename, max_age=86400)
    response.headers['Content-Type'] = 'text/css; charset=utf-8'
    return response

@app.route('/js/<path:filename>')
def serve_js(filename):
    js_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'js')
    response = send_from_directory(js_dir, filename, max_age=86400)
    response.headers['Content-Type'] = 'application/javascript; charset=utf-8'
    return response

@app.route('/projects/<path:filename>')
def serve_project_file(filename):
    return send_from_directory(PROJECTS_DIR, filename, max_age=86400)  # Кэширование на 24 часа

@app.route('/api/proxy-image')
def proxy_image():
    image_url = request.args.get('url', '')
    
    if not image_url:
        return jsonify({'error': 'URL не указан'}), 400

    parsed = urlparse(image_url)
    if parsed.netloc != 'vm-ftp.anosov.ru':
        return jsonify({'error': 'Недоверенный домен'}), 403
    
    try:

        response = requests.get(image_url, timeout=10, stream=True)
        response.raise_for_status()

        content_type = response.headers.get('Content-Type', 'image/jpeg')

        proxy_response = Response(
            response.content,
            status=200,
            content_type=content_type
        )

        proxy_response.headers['Cache-Control'] = 'public, max-age=86400'
        
        return proxy_response
        
    except requests.exceptions.RequestException as e:
        return jsonify({'error': f'Ошибка загрузки: {str(e)}'}), 500

if __name__ == '__main__':

    ensure_data_dir(DATA_DIR)

    load_users(USERS_FILE, hash_password)
    
    print("🚀 Запуск сервера...")
    app.run(debug=True, host='0.0.0.0', port=5000)
