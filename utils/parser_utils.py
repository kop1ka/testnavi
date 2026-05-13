"""Утилиты для парсинга FTP-каталога"""
import requests
from bs4 import BeautifulSoup
from urllib.parse import unquote, urljoin
from concurrent.futures import ThreadPoolExecutor, as_completed


def extract_items_from_html(html_content, base_url):
    """Извлечь элементы каталога из HTML страницы FTP"""
    soup = BeautifulSoup(html_content, 'html.parser')
    items = []
    
    table = soup.find('table')
    if not table:
        return items
    
    for row in table.find_all('tr'):
        cells = row.find_all('td')
        if len(cells) < 5:
            continue
        
        link = cells[1].find('a')
        if not link:
            continue
        
        name_text = link.get_text(strip=True)
        if name_text == 'Parent Directory':
            continue
        
        href = link.get('href', '')
        modified = cells[2].get_text(strip=True) if cells[2] else None
        
        img = cells[0].find('img')
        is_folder = img and '[DIR]' in img.get('alt', '')
        
        full_url = urljoin(base_url, href)
        
        if is_folder:
            items.append({
                'name': unquote(name_text.rstrip('/')),
                'icon': 'page/logo.png',
                'children': [],
                'url': full_url,
                'modified': modified
            })
        else:
            name_without_ext = unquote(name_text)
            if '.' in name_without_ext:
                name_without_ext = name_without_ext.rsplit('.', 1)[0]
            items.append({
                'name': name_without_ext,
                'icon': 'page/logo.png',
                'children': None,
                'url': full_url,
                'modified': modified
            })
    
    return items


def parse_folder(url, visited=None, depth=0, max_depth=10, timeout=10, max_workers=5):
    """
    Парсинг FTP-каталога с многопоточностью
    
    Args:
        url: URL для парсинга
        visited: множество посещённых URL
        depth: текущая глубина рекурсии
        max_depth: максимальная глубина парсинга
        timeout: таймаут запроса в секундах
        max_workers: количество потоков для параллельного парсинга
    
    Returns:
        list: список элементов каталога
    """
    if visited is None:
        visited = set()
    
    if depth > max_depth or url in visited:
        return []
    
    visited.add(url)
    
    try:
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
        
        items = extract_items_from_html(response.text, url)
        
        folders_to_parse = [item for item in items if item['children'] is not None and item['url']]
        
        if folders_to_parse and depth < max_depth:
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_item = {
                    executor.submit(_parse_folder_recursive, item['url'], visited, depth + 1, max_depth, timeout): item
                    for item in folders_to_parse
                }
                
                for future in as_completed(future_to_item):
                    item = future_to_item[future]
                    try:
                        item['children'] = future.result()
                    except Exception:
                        item['children'] = []
        
        return items
        
    except Exception:
        return []


def _parse_folder_recursive(url, visited, depth, max_depth, timeout):
    """Вспомогательная функция для рекурсивного парсинга"""
    return parse_folder(url, visited, depth, max_depth, timeout)
