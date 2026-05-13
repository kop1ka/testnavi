"""Утилиты для аутентификации и управления пользователями"""
import bcrypt
from datetime import datetime
from flask_login import UserMixin
from functools import wraps
from flask import flash, redirect, url_for
from flask_login import current_user


class User(UserMixin):
    """Класс пользователя для Flask-Login"""
    def __init__(self, id, username, is_admin=False):
        self.id = id
        self.username = username
        self.is_admin = is_admin
    
    def get_id(self):
        return str(self.id)


def hash_password(password):
    """Хеширование пароля с bcrypt"""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password, password_hash):
    """Проверка пароля по хешу"""
    try:
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    except Exception:
        return False


def create_user(username, password, is_admin=False):
    """Создать структуру данных пользователя"""
    return {
        "id": None,
        "username": username,
        "password_hash": hash_password(password),
        "is_admin": is_admin,
        "created_at": datetime.now().isoformat()
    }


def admin_required_decorator(f):
    """Декоратор для ограничения доступа администраторам"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not getattr(current_user, 'is_admin', False):
            flash('Требуется права администратора', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function
