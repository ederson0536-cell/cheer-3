#!/usr/bin/env python3
"""
File Content Indexer
扩展 file_catalog：关键词 + 内容搜索 + 关系发现
"""
import os
import re
import sqlite3
from pathlib import Path
from datetime import datetime, timezone

WORKSPACE = Path("/home/bro/.openclaw/workspace-cheer")
DB_PATH = WORKSPACE / "memory/file_catalog.sqlite"

# 文件扩展名对应语言
LANG_EXT = {
    '.py': 'python',
    '.js': 'javascript',
    '.ts': 'typescript',
    '.md': 'markdown',
    '.json': 'json',
    '.yaml': 'yaml',
    '.yml': 'yaml',
    '.sql': 'sql',
    '.sh': 'bash',
}

def get_db():
    conn = sqlite3.connect(DB_PATH)
    return conn

def extract_keywords(content: str, file_type: str) -> str:
    """提取关键词"""
    keywords = set()
    
    # Python: import, from, class, def
    if file_type == 'python':
        keywords.update(re.findall(r'^(?:from|import)\s+([\w.]+)', content, re.M))
        keywords.update(re.findall(r'^class\s+(\w+)', content, re.M))
        keywords.update(re.findall(r'^def\s+(\w+)', content, re.M))
    
    # JavaScript/TypeScript: import, export, class, const, function
    elif file_type in ('javascript', 'typescript'):
        keywords.update(re.findall(r'^import\s+.*?from\s+[\'"](.+?)[\'"]', content, re.M))
        keywords.update(re.findall(r'^export\s+(?:default\s+)?(?:class|const|function|interface|type)\s+(\w+)', content, re.M))
        keywords.update(re.findall(r'^(?:const|let|var)\s+(\w+)\s*=', content, re.M))
    
    # Markdown: # 标题
    elif file_type == 'markdown':
        keywords.update(re.findall(r'^#+\s+(.+)$', content, re.M))
    
    # JSON: keys
    elif file_type == 'json':
        keywords.update(re.findall(r'"(\w+)":', content))
    
    return ','.join(list(keywords)[:20])  # 最多20个

def extract_summary(content: str, file_type: str) -> str:
    """提取内容摘要"""
    lines = content.split('\n')
    
    # 取前几行非空行作为摘要
    summary_lines = []
    for line in lines[:10]:
        line = line.strip()
        if line and not line.startswith('#') and not line.startswith('//') and not line.startswith('"""'):
            summary_lines.append(line[:100])
            if len(summary_lines) >= 3:
                break
    
    return ' | '.join(summary_lines)

def find_relations(content: str, file_type: str, current_path: str) -> list:
    """发现文件关系"""
    relations = []
    
    if file_type == 'python':
        # import X -> X
        imports = re.findall(r'^(?:from|import)\s+([\w.]+)', content, re.M)
        for imp in imports:
            if imp.startswith('.'):
                continue  # 跳过相对导入
            parts = imp.split('.')
            if len(parts) >= 2:
                # 可能是模块路径
                relations.append({
                    'target': parts[0],
                    'type': 'imports'
                })
    
    elif file_type in ('javascript', 'typescript'):
        # import X from 'Y' -> Y
        imports = re.findall(r"import\s+.*?from\s+['\"](.+?)['\"]", content)
        for imp in imports:
            if not imp.startswith('.'):
                relations.append({
                    'target': imp,
                    'type': 'imports'
                })
    
    elif file_type == 'markdown':
        # 链接 [text](path)
        links = re.findall(r'\[.+?\]\((.+?)\)', content)
        for link in links:
            if not link.startswith('http'):
                relations.append({
                    'target': link,
                    'type': 'links'
                })
    
    return relations

def index_files():
    """索引所有文件内容"""
    conn = get_db()
    exclude_dirs = {'.git', '__pycache__', 'node_modules', '.openclaw', '.venv', 'venv', 'logs'}
    
    count = 0
    rel_count = 0
    
    for root, dirs, filenames in os.walk(WORKSPACE):
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        
        for f in filenames:
            if f.startswith('.'):
                continue
            
            full_path = Path(root) / f
            try:
                rel_path = full_path.relative_to(WORKSPACE).as_posix()
            except ValueError:
                continue
            
            # 获取文件类型
            ext = full_path.suffix.lower()
            file_type = LANG_EXT.get(ext, 'other')
            
            # 跳过不支持的类型
            if file_type not in ('python', 'javascript', 'typescript', 'markdown', 'json'):
                continue
            
            try:
                content = full_path.read_text(encoding='utf-8', errors='ignore')
            except:
                continue
            
            # 提取关键词
            keywords = extract_keywords(content, file_type)
            
            # 提取摘要
            summary = extract_summary(content, file_type)
            
            # 更新数据库
            conn.execute("""
                UPDATE file_catalog 
                SET keywords = ?, content_summary = ?
                WHERE path = ?
            """, (keywords, summary, rel_path))
            
            # 发现关系
            relations = find_relations(content, file_type, rel_path)
            for rel in relations[:5]:  # 最多5个关系
                conn.execute("""
                    INSERT INTO file_relations (source_path, target_path, relation_type)
                    VALUES (?, ?, ?)
                """, (rel_path, rel['target'], rel['type']))
                rel_count += 1
            
            # 索引到 FTS
            conn.execute("""
                INSERT OR REPLACE INTO file_content_fts (path, content)
                VALUES (?, ?)
            """, (rel_path, content[:50000]))  # 限制长度
            
            count += 1
    
    conn.commit()
    conn.close()
    
    return count, rel_count

def search_content(query: str, limit: int = 10, db_path: Path = None):
    """搜索文件内容"""
    conn = sqlite3.connect(db_path or DB_PATH)
    conn.row_factory = sqlite3.Row
    
    results = conn.execute("""
        SELECT path, snippet(file_content_fts, 1, '<b>', '</b>', '...', 30) as snippet
        FROM file_content_fts
        WHERE file_content_fts MATCH ?
        LIMIT ?
    """, (query, limit)).fetchall()
    
    conn.close()
    return results

def search_by_keywords(keyword: str, limit: int = 10, db_path: Path = None):
    """通过关键词搜索"""
    conn = sqlite3.connect(db_path or DB_PATH)
    conn.row_factory = sqlite3.Row
    
    results = conn.execute("""
        SELECT path, keywords, content_summary
        FROM file_catalog
        WHERE keywords LIKE ? OR content_summary LIKE ?
        LIMIT ?
    """, (f'%{keyword}%', f'%{keyword}%', limit)).fetchall()
    
    conn.close()
    return results

def find_related_files(path: str, limit: int = 10):
    """找相关文件"""
    conn = get_db()
    conn.row_factory = sqlite3.Row
    
    # 找引用我的
    results = conn.execute("""
        SELECT source_path, relation_type FROM file_relations
        WHERE target_path = ? OR target_path LIKE ?
        LIMIT ?
    """, (path, f'{path}%', limit)).fetchall()
    
    conn.close()
    return results

def main():
    print("📂 文件内容索引器 - 扩展 file_catalog...")
    
    print("1. 索引文件内容 (关键词 + 摘要 + 关系)...")
    count, rel_count = index_files()
    print(f"   索引 {count} 个文件，发现 {rel_count} 个关系")
    
    # 测试搜索
    print("\n2. 测试搜索功能...")
    
    # 按关键词搜
    print("\n   关键词搜索 'governance':")
    for r in search_by_keywords('governance', 5):
        print(f"   - {r['path']}")
    
    print("\n✅ 扩展完成！")
    print("\n可用功能:")
    print("  - search_content(query)  # 内容搜索")
    print("  - search_by_keywords(kw)  # 关键词搜索")
    print("  - find_related_files(path)  # 找相关文件")

if __name__ == "__main__":
    main()
