# Further-evolution · 展台再进化

> 原项目名：OCR2Word。拍照/扫描/截图 → 多模态 AI 识别 → 结构化 OCRDocument JSON → 人工校对 → 导出可编辑 Word（.docx）。Windows 桌面端，支持真实双栏数学练习卷、行内公式 OMML、手写与表格保留。

---

## 1. 功能特性

- **图片 → AI → OCRDocument JSON**：JSON Schema 校验通过后再渲染，block 类型覆盖 heading / paragraph / list / table / formula / image / handwritten，支持 `runs` 内 text + formula 混排。
- **归一化 bbox + 真实双栏检测**：bbox 使用 `x,y,width,height ∈ [0,1]`（左上角原点）；双栏判定基于 `cx = x + width/2` 的排序后相邻最大间隙，阈值已针对真实数学卷窄间隙（≈0.20）校准，并用正例 + 反例 fixture 锁定，防止误伤单栏。
- **高块按「顶部 y」排序**：避免高度较大的答案块因中心 y 错位而被排到图片/错题本之后。
- **横向 16:9 多栏渲染 + 公式 OMML**：`phase2/reflow` 把双栏重排为横向表格，LaTeX 公式走 `latex2mathml → MML2OMML.xsl` 渲染成 Word 原生 OMML。
- **Windows 桌面 GUI（PySide6）**：选图 → 填本次模型配置 → 生成 Word；内置 OCRDocument JSON 编辑器；API Key **仅内存使用、关闭软件时才清空**（处理完一张后可以连续处理多张不用反复输 Key）。
- **中间产物隔离**：JSON、去重记录、失败目录统一写入 `%TEMP%\further_evolution`，用户输出目录**只保留最终 docx**。
- **GitHub Actions 单文件打包与发布**：推送 `v*` tag → `windows-latest` 自动构建 `FurtherEvolution.exe` 并上传 GitHub Release。

---

## 2. 目录结构

```
.
├── phase0/               OCR + schema + DOCX 渲染（最小验证与基础模块）
│   ├── provider.py       多模态 API 兼容层
│   ├── ocrdoc_schema.py  OCRDocument JSON Schema 校验
│   └── docx_builder.py   JSON → .docx（含 MML2OMML 公式渲染）
├── phase1/               文件夹轮询 + 去重流水线（ProcessRecordStore）
├── phase2/               基于 bbox 的版面理解、阅读顺序重建、多栏重排、16:9 渲染
├── phase6/               桌面 GUI 主窗口 + 后台 QThread OCR + OCRDocument 编辑器
├── .github/workflows/build.yml   tag 触发打包 + 发布 Release
├── further_evolution.spec        PyInstaller 单文件、无控制台窗口
├── run.py                PyInstaller 打包入口（启动 phase6.main_window.main）
├── requirements.txt      GUI 运行时与打包时依赖
└── PROJECT_SPEC.md       项目总体规范（OCRDocument 结构、开发阶段、Git 规则）
```

---

## 3. 本地运行（GUI）

```powershell
# 1. 安装依赖
python -m pip install --upgrade pip
pip install -r requirements.txt

# 2. 启动桌面应用
python run.py
```

主窗口会让你：
1. 选一张 jpg/png/webp/... 输入图片
2. 填本次 API Endpoint（默认 `https://api.deepseek.com`）、模型名、API Key、超时、重试次数
3. 点击「开始识别并生成 Word」→ 结束后「打开结果编辑器」校对 JSON 或直接用生成的 `.docx`

> API Key 安全策略：
> - 不写入磁盘、日志、项目文件
> - 处理完一张图片后 **不清空**，可以连续识别多张
> - 关闭主窗口时才会被清空（见 `phase6/main_window.py#closeEvent`）

---

## 4. 命令行验证（不用 GUI）

### Phase 0：单张图片 → OCRDocument JSON

```powershell
$env:FURTHEREVO_API_KEY="sk-xxx"
python phase0/verify.py .\path\to\image.jpg
```

支持的环境变量：

| 变量 | 必填 | 默认 |
|---|---|---|
| `FURTHEREVO_API_KEY` | ✅ | — |
| `FURTHEREVO_API_BASE` | | `https://api.openai.com/v1` |
| `FURTHEREVO_MODEL` | | `gpt-4o` |
| `FURTHEREVO_TIMEOUT` | | `120`（秒） |
| `FURTHEREVO_MAX_RETRIES` | | `2` |
| `FURTHEREVO_MML2OMML_XSL` | | 打包内置 MML2OMML.xsl（见 `phase0/docx_builder.py`） |

### Phase 1：文件夹轮询自动 OCR → DOCX

```powershell
$env:FURTHEREVO_API_KEY="sk-xxx"
python phase1/main.py --input-dir .\input --output-dir .\output --failed-dir .\failed
```

支持与 Phase 0 同一套 `FURTHEREVO_*` 环境变量（默认 base/model 是 DeepSeek 配置）。

### Phase 2：测试双栏/重排/渲染

```powershell
python -m unittest discover -s phase2/tests -p "test_*.py" -v
python -m unittest discover -s phase6/tests -p "test_*.py" -v
```

---

## 5. 本地打包成单文件 exe

```powershell
pip install pyinstaller
pyinstaller --clean --noconfirm further_evolution.spec
# 产物：dist\FurtherEvolution.exe
```

注意：
- `latex2mathml` 的 `unimathsymbols.txt` 已在 `further_evolution.spec` 的 `datas` 中显式收集，避免打包后运行 `FileNotFoundError`。
- `phase1/pipeline.py` 用无包前缀导入 phase0 模块，已在 spec 的 `hiddenimports` 中声明 `docx_builder / ocrdoc_schema / provider`。

---

## 6. GitHub Actions 自动构建与发布

工作流见 [.github/workflows/build.yml](.github/workflows/build.yml)：

```
推送 tag 形如 v*
  → windows-latest + Python 3.11
  → pip install -r requirements.txt pyinstaller
  → pyinstaller --clean --noconfirm further_evolution.spec
  → softprops/action-gh-release@v2 上传 dist/FurtherEvolution.exe
     并自动生成 Release Notes
```

操作示例：

```powershell
git tag v0.2.0
git push origin v0.2.0
```

完成后在仓库 `Releases` 页面下载 `FurtherEvolution.exe` 即可。

---

## 7. 分支约定（重要）

- **Evolution**：改名后的新分支，项目名为「Further-evolution / 展台再进化」，环境变量前缀 `FURTHEREVO_*`、临时目录 `%TEMP%\further_evolution`、打包产物 `FurtherEvolution.exe`。
- **main**：保留原项目名 OCR2Word 的主干（环境变量前缀 `OCR2WORD_*` / 产物 `OCR2Word.exe`），用于与旧流程兼容。
- 所有 commit 都发生在各自特性分支上，**禁止 reset/rebase/squash/force push 受保护分支**；API Key 严禁硬编码进仓库。
