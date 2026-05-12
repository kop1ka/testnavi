# Шаблон проекта для основной системы

Этот шаблон демонстрирует, как создать новый проект, который будет автоматически регистрироваться в главной системе через Flask Blueprint.

## Структура проекта

```
my_project/
├── app.py                 # Главный файл с Blueprint
├── templates/             # HTML шаблоны
│   └── index.html
├── static/                # Статические файлы (CSS, JS, изображения)
│   ├── css/
│   ├── js/
│   └── img/
└── README.md              # Документация проекта
```

## Создание нового проекта

### Шаг 1: Создайте директорию проекта

```bash
mkdir -p projects/my_new_project/templates
mkdir -p projects/my_new_project/static
```

### Шаг 2: Создайте app.py с функцией create_blueprint()

```python
from flask import Blueprint, render_template

def create_blueprint():
    """
    Фабрика Blueprint для проекта
    
    Returns:
        Blueprint: Настроенный Blueprint проекта
    """
    bp = Blueprint(
        'my_new_project',  # Уникальное имя Blueprint
        __name__,
        template_folder='templates',
        static_folder='static'
    )
    
    # Определение маршрутов
    @bp.route('/')
    def index():
        return render_template('index.html')
    
    @bp.route('/about')
    def about():
        return render_template('about.html')
    
    return bp
```

### Шаг 3: Создайте шаблоны и статические файлы

Пример `templates/index.html`:
```html
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <title>Мой Проект</title>
    <link rel="stylesheet" href="{{ url_for('my_new_project.static', filename='css/style.css') }}">
</head>
<body>
    <h1>Добро пожаловать!</h1>
    <a href="{{ url_for('my_new_project.about') }}">О проекте</a>
</body>
</html>
```

### Шаг 4: Автоматическая регистрация

После создания файла `app.py` с функцией `create_blueprint()`, проект будет **автоматически зарегистрирован** в главном приложении при следующем запуске.

URL для доступа к проекту: `/projects/my_new_project/`

## Важные замечания

1. **Функция create_blueprint() обязательна** - система ищет эту функцию для регистрации проекта

2. **Не указывайте url_prefix при создании Blueprint** - префикс добавляется автоматически при регистрации

3. **Используйте относительные пути в маршрутах** - например, `@bp.route('/')` вместо `@bp.route('/projects/my_project/')`

4. **Уникальные имена Blueprint** - каждый проект должен иметь уникальное имя Blueprint

5. **Для доступа к URL используйте url_for()** с префиксом имени Blueprint:
   ```python
   url_for('my_new_project.index')  # Вернёт /projects/my_new_project/
   ```

## Примеры использования

### Работа с базой данных

```python
from flask import Blueprint, jsonify
import pymysql

def create_blueprint():
    bp = Blueprint('db_project', __name__, template_folder='templates')
    
    DB_CONFIG = {
        'host': 'localhost',
        'user': 'root',
        'password': '',
        'database': 'my_db',
        'charset': 'utf8mb4'
    }
    
    @bp.route('/api/data')
    def get_data():
        conn = pymysql.connect(**DB_CONFIG)
        try:
            with conn.cursor() as cursor:
                cursor.execute('SELECT * FROM my_table')
                data = cursor.fetchall()
                return jsonify(data)
        finally:
            conn.close()
    
    return bp
```

### API проект

```python
from flask import Blueprint, request, jsonify

def create_blueprint():
    bp = Blueprint('api_project', __name__)
    
    @bp.route('/api/v1/items', methods=['GET'])
    def get_items():
        return jsonify({'items': []})
    
    @bp.route('/api/v1/items', methods=['POST'])
    def create_item():
        data = request.json
        return jsonify({'id': 1, **data}), 201
    
    return bp
```

### Проект с авторизацией

```python
from flask import Blueprint, render_template, session, redirect, url_for
from functools import wraps

def create_blueprint():
    bp = Blueprint('secure_project', __name__, template_folder='templates')
    
    def login_required(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if not session.get('is_admin'):
                return redirect(url_for('secure_project.login'))
            return f(*args, **kwargs)
        return decorated
    
    @bp.route('/login')
    def login():
        return render_template('login.html')
    
    @bp.route('/dashboard')
    @login_required
    def dashboard():
        return render_template('dashboard.html')
    
    return bp
```

## Масштабирование

При добавлении новых проектов:

1. Просто создайте новую папку в `projects/`
2. Добавьте `app.py` с `create_blueprint()`
3. Перезапустите главное приложение

Все проекты будут доступны по URL:
- `/projects/project_name_1/`
- `/projects/project_name_2/`
- `/projects/project_name_3/`

## Отладка проекта

Для тестирования проекта отдельно от главной системы:

```python
if __name__ == '__main__':
    from flask import Flask
    
    app = Flask(__name__)
    app.secret_key = 'dev-secret-key'
    
    # Регистрируем Blueprint для тестирования
    bp = create_blueprint()
    app.register_blueprint(bp)
    
    app.run(host='0.0.0.0', port=5000, debug=True)
```
