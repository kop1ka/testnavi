# Папка проектов

В эту папку загружаются проекты, которые будут отображаться в каталоге как постоянные элементы.

## 📁 Структура каталога проектов

```
projects/
├── __init__.py                 # Модуль автоматической регистрации Blueprint
├── ARCHITECTURE.md             # Подробная документация по архитектуре
├── TEMPLATE/                   # Шаблон для создания новых проектов
│   ├── app.py                  # Пример Blueprint
│   ├── templates/              # Шаблоны проекта
│   └── static/                 # Статические файлы
├── ПарадЗвёзд!/               # Проект "ПарадЗвёзд"
│   ├── app.py                  # Blueprint проекта
│   ├── templates/              # Шаблоны
│   └── static/                 # Статика
├── flask_test_project/         # Другие проекты
└── test_project/
```

## 🔌 Типы проектов

### 1. Статические проекты (HTML/CSS/JS)

Простые проекты без серверной логики:

```
my_static_site/
├── index.html
├── style.css
└── script.js
```

**Доступ:** `/projects/my_static_site/index.html`

### 2. Flask Blueprint проекты (рекомендуется)

Проекты с серверной логикой на Flask:

```
my_flask_app/
├── app.py                      # Обязательно: функция create_blueprint()
├── templates/                  # HTML шаблоны
│   └── index.html
└── static/                     # CSS, JS, изображения
    ├── css/
    └── js/
```

**Доступ:** `/projects/my_flask_app/` (автоматическая регистрация)

## 🚀 Быстрый старт нового проекта

### Вариант А: Копирование шаблона

```bash
cp -r projects/TEMPLATE projects/my_new_project
```

Затем отредактируйте `app.py` и шаблоны под свои нужды.

### Вариант Б: Создание с нуля

1. **Создайте директорию:**
   ```bash
   mkdir -p projects/my_project/templates
   mkdir -p projects/my_project/static
   ```

2. **Создайте `app.py`:**
   ```python
   from flask import Blueprint, render_template
   
   def create_blueprint():
       bp = Blueprint('my_project', __name__, 
                     template_folder='templates',
                     static_folder='static')
       
       @bp.route('/')
       def index():
           return render_template('index.html')
       
       return bp
   ```

3. **Создайте `templates/index.html`:**
   ```html
   <!DOCTYPE html>
   <html>
   <head><title>Мой проект</title></head>
   <body><h1>Привет!</h1></body>
   </html>
   ```

4. **Готово!** Проект автоматически зарегистрируется при запуске.

## 📡 Как это работает

### Автоматическое обнаружение

Модуль `projects/__init__.py` сканирует директорию и находит все проекты с `app.py`.

### Регистрация Blueprint

Для каждого проекта:
1. Динамически импортируется `app.py`
2. Вызывается функция `create_blueprint()`
3. Blueprint регистрируется в главном приложении с префиксом `/projects/{project_name}/`

### URL маршрутизация

```
Главное приложение:
/                           → Главная страница
/admin                      → Админка

Проекты (автоматически):
/projects/TEMPLATE/         → Шаблон проекта
/projects/parad-zvezd/      → Проект ПарадЗвёзд
/projects/my-project/       → Ваш проект
```

## 📋 Требования к проекту

### Обязательные

- ✅ Файл `app.py` с функцией `create_blueprint()` (для Flask проектов)
- ✅ Уникальное имя Blueprint
- ✅ Директории `templates/` и `static/` (если используются)

### Рекомендуемые

- ✅ `README.md` с описанием проекта
- ✅ `requirements.txt` с зависимостями
- ✅ Отдельная конфигурация БД (если нужна)

## ⚠️ Важные замечания

1. **Имена Blueprint должны быть уникальными**
   ```python
   # Правильно:
   bp = Blueprint('project_alpha', __name__)
   bp = Blueprint('project_beta', __name__)
   ```

2. **Не указывайте url_prefix при создании Blueprint**
   ```python
   # Неправильно:
   bp = Blueprint('app', __name__, url_prefix='/my-app')
   
   # Правильно:
   bp = Blueprint('app', __name__)
   # Префикс добавится автоматически: /projects/my-app/
   ```

3. **Используйте относительные пути в маршрутах**
   ```python
   @bp.route('/')        # Правильно
   @bp.route('/about')   # Правильно
   
   # Неправильно:
   @bp.route('/projects/my-app/')  # Префикс добавится дважды!
   ```

## 🔧 Интеграция с главным приложением

В главном `app.py` добавьте регистрацию проектов:

```python
from projects import register_all_blueprints

app = Flask(__name__)

# Автоматически регистрируем все проекты
register_all_blueprints(app, url_prefix='/projects')
```

## 📖 Дополнительная документация

- [`ARCHITECTURE.md`](ARCHITECTURE.md) - Подробное описание архитектуры
- [`TEMPLATE/README.md`](TEMPLATE/README.md) - Руководство по шаблону
- Примеры в [`TEMPLATE/app.py`](TEMPLATE/app.py)

## 🎯 Примеры использования

### API сервис

```python
from flask import Blueprint, request, jsonify

def create_blueprint():
    bp = Blueprint('api_service', __name__)
    
    @bp.route('/api/items', methods=['GET'])
    def get_items():
        return jsonify({'items': []})
    
    @bp.route('/api/items', methods=['POST'])
    def create_item():
        data = request.json
        return jsonify({'id': 1, **data}), 201
    
    return bp
```

### Проект с базой данных

```python
from flask import Blueprint, jsonify
import pymysql

def create_blueprint():
    bp = Blueprint('db_app', __name__, template_folder='templates')
    
    DB_CONFIG = {
        'host': 'localhost',
        'user': 'root',
        'password': '',
        'database': 'my_db'
    }
    
    @bp.route('/api/users')
    def get_users():
        conn = pymysql.connect(**DB_CONFIG)
        try:
            with conn.cursor() as cursor:
                cursor.execute('SELECT * FROM users')
                return jsonify(cursor.fetchall())
        finally:
            conn.close()
    
    return bp
```

### Проект с авторизацией

```python
from flask import Blueprint, session, redirect, url_for
from functools import wraps

def create_blueprint():
    bp = Blueprint('secure_app', __name__, template_folder='templates')
    
    def login_required(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if not session.get('is_admin'):
                return redirect(url_for('secure_app.login'))
            return f(*args, **kwargs)
        return decorated
    
    @bp.route('/dashboard')
    @login_required
    def dashboard():
        return render_template('dashboard.html')
    
    return bp
```

---

**Для добавления нового проекта:**
1. Создайте папку в `projects/`
2. Добавьте `app.py` с `create_blueprint()`
3. Перезапустите приложение

**Всё!** 🎉
