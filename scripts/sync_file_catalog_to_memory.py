#!/usr/bin/env python3
"""
同步 file_catalog.sqlite -> memory.db system_readable_checklist
"""
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/home/bro/.openclaw/workspace-cheer")
CATALOG_DB = WORKSPACE / "memory/file_catalog.sqlite"
MEMORY_DB = WORKSPACE / "memory/memory.db"

def main():
    print("🔄 同步 file_catalog -> memory.db system_readable_checklist...")
    
    cat_conn = sqlite3.connect(CATALOG_DB)
    cat_conn.row_factory = sqlite3.Row
    
    mem_conn = sqlite3.connect(MEMORY_DB)
    
    count = 0
    
    # 1. 导入根文件 (root_file)
    print("1. 同步根文件...")
    for row in cat_conn.execute("SELECT * FROM file_catalog WHERE file_class IN ('CORE', 'CONTROLLED') AND path NOT LIKE 'evoclaw/%'").fetchall():
        checklist_id = f"root_{row['path'].replace('.', '_').replace('/', '_')}"
        mem_conn.execute("""
            INSERT OR REPLACE INTO system_readable_checklist
            (checklist_id, checklist_type, target_path, purpose, when_to_change, source, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            checklist_id, 
            'root_file',
            row['path'],
            row['primary_function'] or '',
            row['change_trigger'] or '',
            'root_file_registry.json',
            datetime.now(timezone.utc).isoformat()
        ))
        count += 1
    
    # 2. 导入 evolaw 核心文件
    print("2. 同步 evolaw 核心文件...")
    for row in cat_conn.execute("SELECT * FROM file_catalog WHERE path LIKE 'evoclaw/runtime/%' OR path LIKE 'evoclaw/runtime/contracts/%'").fetchall():
        checklist_id = f"runtime_{row['path'].replace('.', '_').replace('/', '_')[:50]}"
        mem_conn.execute("""
            INSERT OR REPLACE INTO system_readable_checklist
            (checklist_id, checklist_type, target_path, purpose, when_to_change, source, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            checklist_id,
            'runtime_file',
            row['path'],
            row['primary_function'] or '',
            row['change_trigger'] or '',
            'file_catalog.sqlite',
            datetime.now(timezone.utc).isoformat()
        ))
        count += 1
    
    mem_conn.commit()
    
    # 验证
    total = mem_conn.execute("SELECT COUNT(*) FROM system_readable_checklist").fetchone()[0]
    
    print(f"\n✅ 完成！同步 {count} 条")
    print(f"📊 memory.db system_readable_checklist 总数: {total}")
    
    cat_conn.close()
    mem_conn.close()

if __name__ == "__main__":
    main()
