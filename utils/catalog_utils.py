"""Утилиты для работы с каталогом и постоянными элементами"""


def get_item_path(item, parent_path=""):
    current_path = f"{parent_path}/{item['name']}" if parent_path else item['name']
    return current_path


def mark_permanent_recursive(items, permanent_paths, parent_path=""):
    for item in items:
        current_path = get_item_path(item, parent_path)
        if current_path in permanent_paths:
            item['permanent'] = True
        if 'children' in item and item['children']:
            mark_permanent_recursive(item['children'], permanent_paths, current_path)


def merge_with_permanent(new_data, existing_catalog, permanent_paths, parent_path=""):
    """
    Объединяет новые данные парсера с существующим каталогом,
    полностью сохраняя постоянные элементы со всеми их свойствами.
    
    Если элемент является постоянным и существует в старом каталоге,
    он берётся из старого каталога целиком (сохраняются все свойства: icon, children и т.д.)
    
    Для НЕпостоянных элементов также сохраняются существующие свойства (icon и др.),
    обновляются только базовые данные из парсера (children, modified, url).
    Свойство 'icon' никогда не перезаписывается данными из парсера - оно сохраняется из существующего каталога.
    """
    result = []
    existing_by_name = {item['name']: item for item in existing_catalog}
    
    for new_item in new_data:
        current_path = get_item_path(new_item, parent_path)
        
        # Если элемент постоянный и существует в старом каталоге - используем старую версию
        if current_path in permanent_paths and new_item['name'] in existing_by_name:
            existing_item = existing_by_name[new_item['name']]
            # Берём существующий элемент целиком (полное сохранение)
            merged_item = existing_item.copy()
            
            # Если это папка - рекурсивно объединяем children
            # При этом сохраняем ВСЕ существующие children постоянного элемента
            # и добавляем новые из парсера
            if (merged_item.get('children') is not None and 
                new_item.get('children') is not None):
                merged_item['children'] = _merge_children_keep_all(
                    new_item['children'], 
                    existing_item.get('children', []),
                    permanent_paths,
                    current_path
                )
            
            result.append(merged_item)
        else:
            # Для непостоянных элементов
            # Если элемент уже существовал - сохраняем его свойства (icon и др.)
            if new_item['name'] in existing_by_name:
                existing_item = existing_by_name[new_item['name']]
                # Начинаем с копии существующего элемента (сохраняем icon и другие свойства)
                merged_item = existing_item.copy()
                
                # Проверяем, есть ли у элемента пользовательская иконка (не пустая и не None)
                has_custom_icon = existing_item.get('icon') and existing_item.get('icon').strip() != ''
                
                # Обновляем только базовые данные из парсера (children, url, modified)
                # Никогда не перезаписываем icon и другие пользовательские свойства
                if 'children' in new_item:
                    if new_item['children'] is not None:
                        merged_item['children'] = _merge_children_keep_all(
                            new_item['children'],
                            existing_item.get('children', []),
                            permanent_paths,
                            current_path
                        )
                    else:
                        merged_item['children'] = None
                # НЕ обновляем url и modified из парсера для элементов с пользовательской иконкой
                # Сохраняем пользовательский icon навсегда
                if not has_custom_icon:
                    if 'url' in new_item:
                        merged_item['url'] = new_item['url']
                    if 'modified' in new_item:
                        merged_item['modified'] = new_item['modified']
                
                result.append(merged_item)
            else:
                # Новый элемент - берём данные из парсера
                # но пытаемся сохранить children из существующих если они есть
                if 'children' in new_item and new_item['children'] is not None:
                    new_item['children'] = _merge_children_keep_all(
                        new_item['children'],
                        existing_by_name.get(new_item['name'], {}).get('children', []),
                        permanent_paths,
                        current_path
                    )
                result.append(new_item)
    
    # Добавляем постоянные элементы, которых нет в новых данных парсера
    for name, existing_item in existing_by_name.items():
        current_path = get_item_path(existing_item, parent_path)
        if current_path in permanent_paths and name not in [item['name'] for item in result]:
            result.append(existing_item)
    
    return result


def _merge_children_keep_all(new_children, existing_children, permanent_paths, parent_path):
    """
    Рекурсивно объединяет children, сохраняя ВСЕ существующие элементы
    и добавляя новые из парсера.
    
    Для существующих элементов сохраняются пользовательские свойства (icon и др.),
    обновляются только базовые данные из парсера (children, url, modified).
    Свойство 'icon' никогда не перезаписывается данными из парсера.
    """
    # Начинаем с копии всех существующих детей
    result = []
    for existing_item in existing_children:
        copied_item = existing_item.copy()
        result.append(copied_item)
    
    existing_names = {item['name'] for item in existing_children}
    
    for new_item in new_children:
        current_path = get_item_path(new_item, parent_path)
        
        # Если элемент уже существует - обновляем его рекурсивно
        if new_item['name'] in existing_names:
            # Находим существующий элемент в результате
            for i, result_item in enumerate(result):
                if result_item['name'] == new_item['name']:
                    # Сохраняем icon (никогда не перезаписываем)
                    saved_icon = result_item.get('icon')
                    saved_permanent = result_item.get('permanent')
                    
                    # Проверяем, есть ли пользовательская иконка
                    has_custom_icon = saved_icon and saved_icon.strip() != ''
                    
                    # Рекурсивно обновляем children
                    if new_item.get('children') is not None:
                        result[i]['children'] = _merge_children_keep_all(
                            new_item['children'],
                            result_item.get('children', []),
                            permanent_paths,
                            current_path
                        )
                    
                    # Обновляем url и modified из парсера, но не icon
                    # НЕ обновляем url/modified если есть пользовательский icon
                    if not has_custom_icon:
                        if 'url' in new_item:
                            result[i]['url'] = new_item['url']
                        if 'modified' in new_item:
                            result[i]['modified'] = new_item['modified']
                    
                    # Восстанавливаем сохранённый icon и permanent статус
                    if saved_icon is not None:
                        result[i]['icon'] = saved_icon
                    if saved_permanent is not None:
                        result[i]['permanent'] = saved_permanent
                    
                    break
        else:
            # Новый элемент - добавляем
            new_item_copy = new_item.copy()
            if new_item.get('children') is not None:
                new_item_copy['children'] = _merge_children_keep_all(
                    new_item['children'],
                    [],
                    permanent_paths,
                    current_path
                )
            result.append(new_item_copy)
    
    return result


def find_item_by_path(items, target_path, current_path=""):
    for item in items:
        item_path = get_item_path(item, current_path)
        
        if item_path == target_path:
            return item
        
        if 'children' in item and item['children']:
            found = find_item_by_path(item['children'], target_path, item_path)
            if found:
                return found
    
    return None


def delete_item_by_path(items, target_path, current_path=""):
    for i, item in enumerate(items):
        item_path = get_item_path(item, current_path)
        
        if item_path == target_path:
            items.pop(i)
            return True
        
        if 'children' in item and item['children']:
            if delete_item_by_path(item['children'], target_path, item_path):
                return True
    
    return False


def update_item_by_path(items, target_path, updates, current_path=""):
    for item in items:
        item_path = get_item_path(item, current_path)
        
        if item_path == target_path:
            item.update(updates)
            return True
        
        if 'children' in item and item['children']:
            if update_item_by_path(item['children'], target_path, updates, item_path):
                return True
    
    return False
