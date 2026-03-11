# 文件管理系统 - 整合版

> 最后更新: 2026-03-11
> 状态: 整合完成

---

## 一、核心组件

| 组件 | 路径 | 职责 |
|------|------|------|
| **FileGovernance** | `evoclaw/runtime/components/file_governance.py` | 文件权限检查 + 审计 |
| **file_catalog** | `memory/file_catalog.sqlite` | 全量文件清单（唯一数据源） |
| **根文件配置** | `evoclaw/runtime/config/root_file_registry.json` | 根文件元数据 |
| **目录配置** | `evoclaw/runtime/config/memory_directory_registry.json` | memory 目录元数据 |

---

## 二、文件分类

| 类别 | 说明 | 写入规则 |
|------|------|----------|
| **CORE** | 核心身份/系统文件 | 禁止直接写，需走提案流程 |
| **CONTROLLED** | 受控文件 | 需审批 |
| **WORKING** | 工作文件 | 自动写 |
| **GENERATED** | 生成文件 | 自动写 |

### 根文件归属

| 文件 | 类别 | 领域 |
|------|------|------|
| SOUL.md | CORE | identity |
| AGENTS.md | CORE | governance |
| USER.md | CONTROLLED | context |
| MEMORY.md | CONTROLLED | memory |
| TOOLS.md | CONTROLLED | tooling |
| HEARTBEAT.md | CONTROLLED | operations |

---

## 三、核心流程

### 3.1 文件修改流程

```
用户请求 → ingress → before_subtask hook 
         → FileGovernance.catalog_precheck() 
         → 允许? → 执行 → 审计 → 更新 catalog
```

### 3.2 检查点

| 函数 | 作用 |
|------|------|
| `catalog_precheck(file_scope)` | 批量检查文件权限 |
| `catalog_enforce(path, mode, operation)` | 单文件强制检查 |
| `transactional_patch_apply()` | 事务化写入 |

### 3.3 审计记录

- 路径: `memory/governance/file_ops_audit.jsonl`
- 记录: 时间、文件、操作、结果、evidence_hash

---

## 四、数据同步

### 当前数据流

```
扫描脚本 (scan_file_catalog.py)
    ↓
file_catalog.sqlite (全量文件)
    ↓
同步脚本 (sync_file_catalog_to_memory.py)
    ↓
memory.db.system_readable_checklist (核心文件清单)
```

### 扫描脚本

| 脚本 | 功能 |
|------|------|
| `scripts/scan_file_catalog.py` | 扫描文件系统 + 导入配置 |
| `scripts/index_file_content.py` | 关键词 + 内容搜索 + 关系 |
| `scripts/sync_file_catalog_to_memory.py` | 同步到 memory.db |

---

## 五、搜索能力

### 使用方式

```python
from scripts.index_file_content import search_content, search_by_keywords

# 内容搜索
search_content("关键词")

# 关键词搜索
search_by_keywords("关键词")

# 找相关文件
find_related_files("文件路径")
```

### 索引数据

- 关键词索引: 2103 个文件
- FTS 内容搜索: 2295 个文件
- 文件关系: 3203 个

---

## 六、验证命令

```bash
# 文件治理验证
python3 evoclaw/validators/validate_week5_file_governance.py

# 全量巡检
python3 evoclaw/validators/run_all.py
```

---

## 七、待整合/修复


