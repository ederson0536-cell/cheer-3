#!/usr/bin/env python3
"""
Working Buffer - 工作缓冲区
暂存中间结果、状态、临时数据
"""

import json
from pathlib import Path

from evoclaw.workspace_resolver import resolve_workspace
from datetime import datetime
from typing import Any, Dict, Optional
import threading

WORKSPACE = resolve_workspace(__file__)


class WorkingBuffer:
    """工作缓冲区 - 线程安全"""
    
    def __init__(self):
        self.buffer_dir = WORKSPACE / "memory" / "buffer"
        self.buffer_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        
        # 内存缓存
        self._cache = {}
    
    def set(self, key: str, value: Any, ttl: int = 3600) -> bool:
        """
        设置缓冲区数据
        key: 键名
        value: 值
        ttl: 过期时间(秒)
        """
        
        with self._lock:
            entry = {
                "key": key,
                "value": value,
                "created_at": datetime.now().isoformat(),
                "ttl": ttl,
                "expires_at": datetime.fromtimestamp(
                    datetime.now().timestamp() + ttl
                ).isoformat()
            }
            
            # 内存缓存
            self._cache[key] = entry
            
            # 持久化
            self._persist(key, entry)
            
            return True
    
    def get(self, key: str) -> Optional[Any]:
        """获取缓冲区数据"""
        
        with self._lock:
            # 先从内存获取
            if key in self._cache:
                entry = self._cache[key]
                if self._is_valid(entry):
                    return entry["value"]
                else:
                    # 过期删除
                    del self._cache[key]
            
            # 从持久化加载
            entry = self._load(key)
            if entry and self._is_valid(entry):
                self._cache[key] = entry
                return entry["value"]
            
            return None
    
    def delete(self, key: str) -> bool:
        """删除缓冲区数据"""
        
        with self._lock:
            # 内存删除
            if key in self._cache:
                del self._cache[key]
            
            # 文件删除
            file_path = self.buffer_dir / f"{key}.json"
            if file_path.exists():
                file_path.unlink()
            
            return True
    
    def clear_expired(self) -> int:
        """清理过期数据"""
        
        count = 0
        with self._lock:
            # 清理内存
            expired_keys = [
                k for k, v in self._cache.items()
                if not self._is_valid(v)
            ]
            for k in expired_keys:
                del self._cache[k]
                count += 1
            
            # 清理持久化
            for f in self.buffer_dir.glob("*.json"):
                try:
                    with open(f) as fp:
                        entry = json.load(fp)
                    if not self._is_valid(entry):
                        f.unlink()
                        count += 1
                except:
                    pass
        
        return count
    
    def list_keys(self) -> list:
        """列出所有键"""
        
        with self._lock:
            # 合并内存和持久化
            keys = set(self._cache.keys())
            
            for f in self.buffer_dir.glob("*.json"):
                key = f.stem
                if key not in self._cache:
                    try:
                        with open(f) as fp:
                            entry = json.load(fp)
                        if self._is_valid(entry):
                            keys.add(key)
                    except:
                        pass
            
            return list(keys)
    
    def _is_valid(self, entry: Dict) -> bool:
        """检查是否有效"""
        
        if not entry:
            return False
        
        expires_at = entry.get("expires_at")
        if not expires_at:
            return True
        
        try:
            return datetime.now() < datetime.fromisoformat(expires_at)
        except:
            return True
    
    def _persist(self, key: str, entry: Dict):
        """持久化"""
        
        file_path = self.buffer_dir / f"{key}.json"
        with open(file_path, "w") as f:
            json.dump(entry, f, indent=2, ensure_ascii=False)
    
    def _load(self, key: str) -> Optional[Dict]:
        """加载"""
        
        file_path = self.buffer_dir / f"{key}.json"
        if file_path.exists():
            try:
                with open(file_path) as f:
                    return json.load(f)
            except:
                return None
        
        return None


# 全局实例
_buffer = None

def get_buffer() -> WorkingBuffer:
    global _buffer
    if _buffer is None:
        _buffer = WorkingBuffer()
    return _buffer


if __name__ == "__main__":
    buffer = get_buffer()
    
    # Test
    buffer.set("test_key", {"data": "test"}, ttl=10)
    print(f"Keys: {buffer.list_keys()}")
    print(f"Get: {buffer.get('test_key')}")
