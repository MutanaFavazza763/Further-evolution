# Further-evolution · 展台再进化

> 面向**希沃视频展台**场景的拍照 OCR + 智能排版工具。
> 老师用视频展台拍下试卷、作业、板书，一键识别成结构化文字，自动重排版（竖转横 / 多栏），导出可编辑 Word，方便在大屏上批注、讲评。

---

## 1. 项目定位

### 解决什么问题

在希沃视频展台 / 实物展台的日常教学中，老师常常需要：

1. 用展台拍下**试卷、作业、课本页、手写板书**；
2. 想把这些照片变成**可编辑、可再排版、可批注**的电子文档；
3. 希望排版适配**教学大屏 / 一体机的 16:9 横向显示**，而不是原样竖排。

本工具把这套流程串成一条线：

```
拍照(视频展台/相册)
  → 多模态 AI OCR / 图片理解
  → 结构化 OCRDocument JSON（带归一化 bbox）
  → 智能版面分析 + 阅读顺序重建
  → 重排版（竖转横 16:9 / 多栏）
  → 可编辑 Word (.docx)，便于批注讲评
```

### 典型使用场景

- 试卷 / 练习卷：拍照 → OCR → 双栏识别 → 横排多栏 → Word 批注
- 手写作业：保留手写/图片块，识别印刷文字并混排
- 理科题目：公式保留并转 Word 原生 OMML
- 板书 / 展台投影内容：转成可二次编辑的课件素材

---

## 2. 功能特性

- **图片 → AI → OCRDocument JSON**：JSON Schema 校验通过后再渲染，block 类型覆盖 `heading / paragraph / list / table / formula / image / handwritten`，支持 `runs` 内 text + formula 混排。
- **归一化 bbox + 真实双栏检测**：bbox 使用 `x,y,width,height ∈ [0,1]`（左上角原点）；双栏判定基于 `cx = x + width/2` 的排序后相邻最大间隙，阈值已针对真实数学卷窄间隙（≈0.20）校准，并用正例 + 反例 fixture 锁定，防止误伤单栏。
- **高块按「顶部 y」排序**：避免高度较大的答案块因中心 y 错位而被排到图片/错题本之后。
- **竖转横 16:9 多栏重排**：GUI 内可选「排版方式 → 竖转横」，把竖向内容流重排成适配大屏的横向多栏 Word；不勾选则保持原竖向。重排失败会自动回退竖向并在状态栏提示，不中断处理。
- **公式 OMML**：LaTeX 公式走 `latex2mathml → MML2OMML.xsl` 渲染成 Word 原生 OMML，可直接编辑。
- **Windows 桌面 GUI（PySide6）**：选图 → 填本次模型配置 → 生成 Word；内置 OCRDocument JSON 编辑器用于校对；API Key **仅内存使用、关闭软件时才清空**（处理完一张后可连续识别多张，无需反复输入）。
- **中间产物隔离**：JSON、去重记录、失败目录统一写入 `%TEMP%\further_evolution`，用户输出目录**只保留最终 docx**。
- **GitHub Actions 单文件打包与发布**：推送 `v*` tag → `windows-latest` 自动构建 `FurtherEvolution.exe` 并上传 GitHub Release。

---

## 3. 目录结构

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
├── app_icon.ico                  Windows 程序图标（16~256 多尺寸）
├── app_icon.png                  图标源文件（高分辨率 PNG）
├── run.py                PyInstaller 打包入口（启动 phase6.main_window.main）
├── requirements.txt      GUI 运行时与打包时依赖
└── PROJECT_SPEC.md       项目总体规范（OCRDocument 结构、开发阶段、Git 规则）
```

---

## 4. 本地运行（GUI）

```powershell
# 1. 安装依赖
python -m pip install --upgrade pip
pip install -r requirements.txt

# 2. 启动桌面应用
python run.py
```

主窗口操作：

1. 选一张 jpg/png/webp/... 输入图片（可来自视频展台拍照或相册）
2. 填本次 API Endpoint（默认 `https://api.deepseek.com`）、模型名、API Key、超时、重试次数
3. 勾选「排版方式 → 竖转横」可生成 16:9 横向多栏 Word（默认竖向）
4. 点击「开始识别并生成 Word」→ 结束后「打开结果编辑器」校对 JSON，或直接用生成的 `.docx` 批注讲评

> API Key 安全策略：
> - 不写入磁盘、日志、项目文件
> - 处理完一张图片后 **不清空**，可以连续识别多张
> - 关闭主窗口时才会被清空（见 `phase6/main_window.py#closeEvent`）

---

## 5. 命令行验证（不用 GUI）

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

### Phase 2：竖转横重排（独立 CLI）

```powershell
python phase2/pipeline.py .\path\to\result.json --output .\out_reflow.docx
```

### 测试

```powershell
python -m unittest discover -s phase2/tests -p "test_*.py" -v
python -m unittest discover -s phase6/tests -p "test_*.py" -v
```

---

## 6. 本地打包成单文件 exe

```powershell
pip install pyinstaller
pyinstaller --clean --noconfirm further_evolution.spec
# 产物：dist\FurtherEvolution.exe
```

程序图标：打包时 `further_evolution.spec` 会读取项目根的 `app_icon.ico`（含 16/24/32/48/64/128/256 多尺寸）写入 exe。如需更换图标，替换 `app_icon.ico`（Windows 用 `.ico`）即可，`app_icon.png` 为源文件。

注意：

- `latex2mathml` 的 `unimathsymbols.txt` 已在 `further_evolution.spec` 的 `datas` 中显式收集，避免打包后运行 `FileNotFoundError`。
- `phase1/pipeline.py` 用无包前缀导入 phase0 模块，已在 spec 的 `hiddenimports` 中声明 `docx_builder / ocrdoc_schema / provider`。

---

## 7. GitHub Actions 自动构建与发布

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

## 8. 分支约定（重要）

- **Evolution**：改名后的新分支，项目名为「Further-evolution / 展台再进化」，环境变量前缀 `FURTHEREVO_*`、临时目录 `%TEMP%\further_evolution`、打包产物 `FurtherEvolution.exe`。
- **main**：保留原项目名 OCR2Word 的主干（环境变量前缀 `OCR2WORD_*` / 产物 `OCR2Word.exe`），用于与旧流程兼容。
- 所有 commit 都发生在各自特性分支上，**禁止 reset/rebase/squash/force push 受保护分支**；API Key 严禁硬编码进仓库。
