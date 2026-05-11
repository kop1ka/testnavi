"""Утилиты для парсинга FTP-каталога"""
import json
import requests
from bs4 import BeautifulSoup
from urllib.parse import unquote, urljoin


def extract_items_from_html(html_content, base_url):
    soup = BeautifulSoup(html_content, 'html.parser')
    items = []
    
    table = soup.find('table')
    if not table:
        return items
    
    rows = table.find_all('tr')
    
    for row in rows:
        cells = row.find_all('td')
        if len(cells) >= 5:
            name_cell = cells[1]
            link = name_cell.find('a')
            if not link:
                continue
            
            name_text = link.get_text(strip=True)
            
            if name_text == 'Parent Directory':
                continue
            
            href = link.get('href', '')
            modified_cell = cells[2]
            modified = modified_cell.get_text(strip=True) if modified_cell else None
            
            img = cells[0].find('img')
            is_folder = False
            if img:
                alt = img.get('alt', '')
                is_folder = '[DIR]' in alt
            
            full_url = urljoin(base_url, href)
            
            if is_folder:
                item = {
                    'name': unquote(name_text.rstrip('/')),
                    'icon': 'page/logo.png',
                    'children': [],
                    'url': full_url,
                    'modified': modified
                }
                items.append(item)
            else:
                name_without_ext = unquote(name_text)
                if '.' in name_without_ext:
                    name_without_ext = name_without_ext.rsplit('.', 1)[0]
                item = {
                    'name': name_without_ext,
                    'icon': 'page/logo.png',
                    'children': None,
                    'url': full_url,
                    'modified': modified
                }
                items.append(item)
    
    return items


def parse_folder(url, visited=None, depth=0, max_depth=10, timeout=10):
    if visited is None:
        visited = set()
    
    if depth > max_depth or url in visited:
        return []
    
    visited.add(url)
    
    try:
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
        
        items = extract_items_from_html(response.text, url)
        
        for item in items:
            if item['children'] is not None and item['url']:
                try:
                    children = parse_folder(item['url'], visited, depth + 1, max_depth, timeout)
                    item['children'] = children
                except Exception:
                    item['children'] = []
        
        return items
        
    except Exception:
        return []
