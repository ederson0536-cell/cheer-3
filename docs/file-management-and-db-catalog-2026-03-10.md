# 文件管理办法 + 数据库文件目录机制（OpenClaw）

## 为什么需要
是的，应该有两套能力一起上：
1. **文件管理办法（治理规则）**：明确什么文件可以自动改、什么必须评审。
2. **数据库文件目录（File Catalog DB）**：让 Claw 在改动前先知道“有哪些文件、归属哪个域、风险级别是什么”。

这能显著降低误改核心文件和越权写入的概率。

---

## 1) 文件管理办法（治理）

### 1.1 文件分类（File Classification）
- **CORE**：身份、治理、主流程（如 `SOUL.md`、核心 policy、runtime 主路由）
- **CONTROLLED**：合同、策略、运行文档（如 contracts/policies）
- **WORKING**：任务中间产物、报告、草稿
- **GENERATED**：可重建产物（报表、缓存、索引）

### 1.2 写入策略（Write Policy）
- CORE：`review-only`，禁止 direct write
- CONTROLLED：`patch-first + review gate`
- WORKING：允许 auto write，但要记录 trace
- GENERATED：允许重建覆盖，不进入核心审批链

### 1.3 发布与回滚
- 所有 CORE/CONTROLLED 变更必须有：
  - `proposal_id`
  - `review record`
  - `release_version`
  - `rollback plan`

---

## 2) 数据库文件目录（File Catalog DB）

### 2.1 目标
在执行任何文件写操作前，先查目录库：
- 文件是否存在
- 属于哪个分类
- 是否允许当前任务写
- 需要走 auto/review/reject 哪条路径

### 2.2 建议表结构

```sql
CREATE TABLE file_catalog (
  path TEXT PRIMARY KEY,
  file_class TEXT NOT NULL,            -- CORE/CONTROLLED/WORKING/GENERATED
  owner_domain TEXT,                   -- runtime/contracts/docs/skills/...
  risk_level TEXT NOT NULL,            -- low/medium/high
  writable_mode TEXT NOT NULL,         -- auto/review-only/forbidden
  last_hash TEXT,
  last_indexed_at TEXT NOT NULL,
  exists_flag INTEGER NOT NULL         -- 1/0
);

CREATE INDEX idx_file_catalog_class ON file_catalog(file_class);
CREATE INDEX idx_file_catalog_mode ON file_catalog(writable_mode);
```

### 2.3 运行时接入点
- `before_task`：根据任务 file_scope 预检可写范围
- `before_subtask`：子任务写入前做逐文件权限判定
- `execute`：执行器落地前二次校验（防止绕过）
- `after_task`：增量刷新目录索引

---

## 3) 与当前方案的结合方式

- 机制运行表第 14 节（File Governance）作为入口。
- 新增 `File Catalog Resolver` 作为 mandatory check。
- 高风险文件（CORE）默认 `review-only`。
- candidate 建议不得直接修改 file catalog policy（需 governance 审批）。

---

## 4) 最小落地步骤（可直接执行）

1. 增加目录库构建脚本（扫描仓库，写入 sqlite）。
2. 在路由前增加 `catalog_precheck(file_scope)`。
3. 在执行器增加 `catalog_enforce(path, mode)`。
4. 在回归报告增加两项指标：
   - `file_policy_block_count`
   - `unauthorized_write_attempt_count`

---

## 5) 一句话结论

你提的方向是对的：
**“文件管理办法 + 数据库文件目录”** 应该成为 Claw 的基础设施，
这样系统改文件会更稳、更可控、更可审计。

---

## 6) 字段与对象统一（必须）

为避免“同名不同义 / 不同名同义 / join 不稳定 / 指标口径漂移”，新增两份强制契约：

- `evoclaw/runtime/contracts/canonical_field_dictionary.yaml`
- `evoclaw/runtime/contracts/canonical_object_schema.yaml`

执行要求：
1. 新表/新 schema 必须先对齐字段字典，再允许合并。
2. 所有对象必须使用 canonical object schema 里的必填字段集合。
3. 发现同义异名字段（如 `job_type/work_type`）一律视为 schema violation。
