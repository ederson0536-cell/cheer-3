#!/usr/bin/env python3
"""
File Catalog Scanner - 与 FileGovernance 组件兼容
扫描工作区文件，综合 root_file_registry.json + 实际文件系统
"""
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
import hashlib

WORKSPACE = Path(__file__).resolve().parents[1]
DB_PATH = WORKSPACE / "memory/file_catalog.sqlite"
ROOT_REGISTRY = WORKSPACE / "evoclaw/runtime/config/root_file_registry.json"
MEM_DIR_REGISTRY = WORKSPACE / "evoclaw/runtime/config/memory_directory_registry.json"

def get_db():
    conn = sqlite3.connect(DB_PATH)
    return conn

def load_json(path):
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return None

def generate_file_id(path: str) -> str:
    """生成稳定的 file_id"""
    return f"file_{hashlib.md5(path.encode()).hexdigest()[:12]}"

def scan_filesystem():
    """扫描实际文件系统"""
    files = []
    exclude_dirs = {'.git', '__pycache__', 'node_modules', '.openclaw', 'evoclaw/runtime', '.venv', 'venv', 'logs'}
    
    for root, dirs, filenames in os.walk(WORKSPACE):
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        
        for f in filenames:
            if f.startswith('.'):
                continue
            try:
                full_path = Path(root) / f
                rel_path = full_path.relative_to(WORKSPACE).as_posix()
            except (OSError, ValueError):
                continue
            
            # 跳过内存数据库文件
            if rel_path in {'memory/memory.db', 'memory/memory.db-shm', 'memory/memory.db-wal'}:
                continue
            
            files.append({
                'path': rel_path,
                'size': full_path.stat().st_size if full_path.exists() else 0
            })
    
    return files

def classify_file(rel_path: str) -> dict:
    """分类文件 - 与 FileGovernance._classify 保持一致"""
    # 根文件
    if rel_path in {'SOUL.md', 'AGENTS.md'} or rel_path.startswith('evoclaw/runtime/'):
        return {
            'file_class': 'CORE',
            'owner_domain': 'system',
            'task_risk_level': 'high',
            'writable_mode': 'review-only',
            'file_status': 'locked',
            'primary_function': 'Runtime/core governance code.',
            'change_trigger': 'Change only with reviewed runtime governance updates'
        }
    if rel_path.startswith('evoclaw/runtime/contracts/') or rel_path.startswith('evoclaw/runtime/config/'):
        return {
            'file_class': 'CONTROLLED',
            'owner_domain': 'contracts',
            'task_risk_level': 'medium',
            'writable_mode': 'review-only',
            'file_status': 'review_pending',
            'primary_function': 'Runtime contracts and policies.',
            'change_trigger': 'When schema/policy contracts are revised'
        }
    if rel_path.startswith('docs/'):
        return {
            'file_class': 'WORKING',
            'owner_domain': 'docs',
            'task_risk_level': 'low',
            'writable_mode': 'auto',
            'file_status': 'active',
            'primary_function': 'Documentation and reports.',
            'change_trigger': 'When docs/reporting needs updates'
        }
    if rel_path.startswith('memory/'):
        return {
            'file_class': 'GENERATED',
            'owner_domain': 'runtime-memory',
            'task_risk_level': 'medium',
            'writable_mode': 'auto',
            'file_status': 'active',
            'primary_function': 'Generated runtime memory artifacts.',
            'change_trigger': 'Managed by runtime pipeline outputs'
        }
    if rel_path.startswith('scripts/'):
        return {
            'file_class': 'WORKING',
            'owner_domain': 'scripts',
            'task_risk_level': 'medium',
            'writable_mode': 'auto',
            'file_status': 'active',
            'primary_function': 'Automation and utility scripts.',
            'change_trigger': 'When automation needs updates'
        }
    return {
        'file_class': 'WORKING',
        'owner_domain': 'general',
        'task_risk_level': 'medium',
        'writable_mode': 'auto',
        'file_status': 'active',
        'primary_function': 'General workspace file.',
        'change_trigger': 'When implementation/tasks require update'
    }

def import_root_registry(conn):
    """导入 root_file_registry.json"""
    data = load_json(ROOT_REGISTRY)
    if not data:
        return 0
    
    count = 0
    now = datetime.now(timezone.utc).isoformat()
    
    for f in data.get('files', []):
        file_id = generate_file_id(f['path'])
        conn.execute("""
            INSERT OR REPLACE INTO file_catalog 
            (file_id, path, file_status, file_class, owner_domain, task_risk_level, writable_mode, primary_function, change_trigger, schema_version, policy_version, created_at, updated_at, exists_flag)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            file_id, 
            f['path'],
            f.get('file_status', 'locked'),
            f.get('file_class', 'CORE'),
            f.get('owner_domain', 'system'),
            f.get('task_risk_level', 'high'),
            f.get('writable_mode', 'review-only'),
            f.get('primary_function', ''),
            f.get('change_trigger', ''),
            'v1', 'v1',
            now, now, 1
        ))
        count += 1
    
    conn.commit()
    return count

def import_filesystem(conn):
    """导入文件系统扫描结果"""
    files = scan_filesystem()
    count = 0
    now = datetime.now(timezone.utc).isoformat()
    
    for f in files:
        # 检查是否已在 registry 中
        cur = conn.execute("SELECT path FROM file_catalog WHERE path = ?", (f['path'],)).fetchone()
        
        if not cur:
            # 自动分类
            classification = classify_file(f['path'])
            file_id = generate_file_id(f['path'])
            
            conn.execute("""
                INSERT INTO file_catalog 
                (file_id, path, file_status, file_class, owner_domain, task_risk_level, writable_mode, primary_function, change_trigger, schema_version, policy_version, created_at, updated_at, exists_flag)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                file_id,
                f['path'],
                classification['file_status'],
                classification['file_class'],
                classification['owner_domain'],
                classification['task_risk_level'],
                classification['writable_mode'],
                classification['primary_function'],
                classification['change_trigger'],
                'v1', 'v1',
                now, now, 1
            ))
            count += 1
    
    conn.commit()
    return count

def main():
    print("📂 File Catalog Scanner (兼容 FileGovernance)...")
    
    conn = get_db()
    
    # 1. 导入配置
    print("1. 导入 root_file_registry.json...")
    c1 = import_root_registry(conn)
    print(f"   导入 {c1} 个根文件")
    
    print("2. 扫描文件系统...")
    c2 = import_filesystem(conn)
    print(f"   新增 {c2} 个文件")
    
    # 统计
    total = conn.execute("SELECT COUNT(*) FROM file_catalog").fetchone()[0]
    
    print(f"\n✅ 完成！文件总数: {total}")
    
    # 显示分类统计
    print("\n📊 分类统计:")
    for row in conn.execute("SELECT file_class, COUNT(*) as c FROM file_catalog GROUP BY file_class ORDER BY c DESC").fetchall():
        print(f"   {row[0]}: {row[1]}")
    
    # 显示根文件
    print("\n📋 根文件配置:")
    for row in conn.execute("SELECT path, file_class, owner_domain FROM file_catalog WHERE file_class = 'CORE' OR file_class = 'CONTROLLED'").fetchall():
        print(f"   {row[0]} ({row[1]}, {row[2]})")
    
    conn.close()
    
    # 验证 FileGovernance 能用
    print("\n🔍 验证 FileGovernance 组件...")
    import sys
    sys.path.insert(0, str(WORKSPACE))
    from evoclaw.runtime.components.file_governance import FileGovernance
    gov = FileGovernance()
    count = gov.refresh_catalog()
    print(f"   FileGovernance.refresh_catalog() = {count} 文件")
    
    # 测试 precheck
    pre = gov.catalog_precheck(["SOUL.md", "docs/test.md"], mode="auto")
    print(f"   catalog_precheck: pass={pre['pass']}, blocked={len(pre['blocked'])}, allowed={len(pre['allowed'])}")

if __name__ == "__main__":
    main()
