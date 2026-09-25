# 展台再进化（Further-evolution） 项目规范

## 1. 项目目标

展台再进化（原 OCR2Word）是一个 Windows 桌面软件。

核心流程：

图片
→ 多模态 AI OCR / 图片理解
→ 结构化 OCR JSON
→ 用户检查和编辑
→ 生成可编辑 Word (.docx)

主要使用场景：

* 拍照图片
* 扫描图片
* 截图
* 手写文字
* 印刷体文字
* 中英文混排
* 数学公式
* 表格
* 题目/答案
* 简单图片和图形

目标不是简单提取纯文本，而是尽可能恢复原图片的逻辑结构。

---

## 2. 第一版技术栈

第一版固定使用：

* Python 3.11+
* PySide6
* watchdog
* Pillow
* OpenCV（按需要使用）
* SQLite
* python-docx
* lxml

AI 接口采用可插拔设计。

优先支持 OpenAI-compatible API。

不要把代码绑定到某一家 AI 服务商。

---

## 3. 核心架构

软件分为：

### UI 层

负责：

* 主窗口
* 系统托盘
* 设置
* OCR 结果预览
* 编辑
* 处理记录
* 错误提示

### Service 层

负责：

* 文件监控
* 任务调度
* OCR 流程
* Word 导出流程

### Domain 层

负责：

* OCR 数据模型
* 图片处理
* AI Provider
* 数学公式处理
* Word 生成

### Infrastructure 层

负责：

* SQLite
* 配置
* 日志
* 缓存
* 重试

---

## 4. 最重要的设计原则

AI OCR 的输出必须首先转换成统一的结构化 JSON。

AI 不应该直接负责生成 Word。

正确流程：

图片
↓
AI
↓
OCRDocument JSON
↓
Preview
↓
Word Renderer
↓
.docx

AI Provider 和 Word Renderer 必须相互独立。

这样以后更换 AI 服务商时，不需要重写 Word 生成系统。

---

## 5. OCRDocument

OCRDocument 是整个项目最重要的数据契约。

基本结构：

```json
{
  "schema_version": "1.0",
  "meta": {
    "source_path": "",
    "sha256": "",
    "width": 0,
    "height": 0,
    "language": "zh-CN"
  },
  "blocks": []
}
```

Block 可以包括：

* heading
* paragraph
* list
* table
* formula
* image
* handwritten

文字和公式允许在同一个段落中混排。

例如：

```json
{
  "type": "paragraph",
  "runs": [
    {
      "kind": "text",
      "text": "已知函数 "
    },
    {
      "kind": "formula",
      "latex": "f(x)=x^2"
    },
    {
      "kind": "text",
      "text": "，求："
    }
  ]
}
```

---

## 6. 数学公式

第一版：

AI 优先输出 LaTeX。

流程：

LaTeX
→ MathML
→ OMML
→ Word 原生公式

不要要求 AI 直接生成 OMML。

如果公式无法可靠转换：

保留对应图片区域作为图片。

绝对不要因为公式识别失败而让整个任务失败。

---

## 7. 文件夹监控

软件需要监控用户指定的输入文件夹。

支持：

* jpg
* jpeg
* png
* webp
* bmp
* tif
* tiff

文件刚出现时不能立即处理。

必须确认文件已经写入完成。

必须防止同一文件重复处理。

建议使用：

SHA-256 + SQLite。

---

## 8. AI Provider

AI Provider 必须抽象。

至少需要：

```text
recognize(image)
recognize_region(image_crop)
```

配置包括：

* API Endpoint
* API Key
* Model
* Timeout
* Retry
* Prompt Version

API Key 不能写死在代码里。

---

## 9. 缓存

缓存必须支持。

缓存键至少包含：

* 图片 SHA-256
* model
* prompt_version
* recognition_mode

重新排版、修改文字、生成 Word时，不应该重新调用 AI。

---

## 10. 错误处理

单个任务失败不能导致程序崩溃。

需要处理：

* 网络错误
* API 超时
* API 返回错误
* JSON 格式错误
* 图片格式错误
* 图片过大
* Word 文件占用
* 文件写入未完成

失败任务应该可以重新处理。

日志不能保存 API Key。

---

## 11. 第一版范围

第一版只实现：

1. Windows 桌面程序
2. 系统托盘
3. 输入文件夹监控
4. 图片稳定性检测
5. SHA-256 去重
6. 一个 AI Provider
7. 图片 → OCRDocument JSON
8. 基础预览
9. 用户编辑 OCR 结果
10. 生成 Word
11. 基础公式
12. SQLite 处理记录
13. 错误处理
14. 手动重新处理

---

## 12. 第一版暂时不要做

暂时不要实现：

* PDF
* 多 AI Provider UI
* 本地大模型
* 专用公式 OCR
* 高级版式重建
* 云同步
* 用户账号系统
* 在线数据库
* 自动更新系统

除非项目后续明确要求，否则不要提前实现。

---

## 13. 开发规则

### 规则 1

不要一次性生成整个项目。

每次只完成一个明确模块。

### 规则 2

不要擅自更换技术栈。

### 规则 3

不要因为实现方便而破坏模块边界。

### 规则 4

修改代码时尽量只修改当前任务相关文件。

### 规则 5

完成任务后必须说明：

* 修改了什么
* 为什么这样修改
* 如何测试
* 测试结果
* 下一步建议

### 规则 6

如果发现当前架构存在问题：

先指出问题。

不要未经允许直接大规模重构。

### 规则 7

任何 AI API Key 都不能写死。

### 规则 8

不要为了“看起来完整”添加没有要求的功能。

---

## 14. 开发顺序

严格按照以下顺序：

Phase 0：
技术验证

Phase 1：
项目骨架

Phase 2：
文件夹监控

Phase 3：
AI Provider

Phase 4：
OCRDocument Schema

Phase 5：
OCR 处理流程

Phase 6：
预览和编辑

Phase 7：
Word Renderer

Phase 8：
SQLite / Cache / Error handling

Phase 9：
系统托盘和设置

Phase 10：
完整测试和打包

---

## 15. 当前状态

项目目前处于：

Phase 0：技术验证

暂时不要开始大规模开发。

下一步应该验证：

1. 多模态 AI 能否稳定输出 OCRDocument JSON
2. 中文手写识别效果
3. 数学公式识别效果
4. 中英文混排
5. 表格识别
6. LaTeX → MathML → OMML → Word 是否可行

只有验证结果达到可接受程度后，才进入正式开发。

【Git / GitHub 提交规则——必须遵守】

从现在开始，本项目的所有开发工作都必须遵守以下 Git 规则。

1. 每次完成一个独立、可运行、可验证的功能或修改后，必须创建一次 Git commit。

2. 不允许长时间积累大量未提交修改。
   一个功能完成并通过基本测试后，应立即 commit。

3. 每次 commit 前必须检查：

   git status
   git diff
   git diff --cached

   确认没有意外修改、敏感信息或不应该提交的文件。

4. Commit message 必须清晰说明本次修改内容。

   推荐格式：

   feat: 添加文件夹自动监控
   feat: 添加 DOCX 自动生成
   fix: 修复公式渲染问题
   fix: 修复重复 OCR 问题
   refactor: 重构 OCR pipeline
   test: 添加 OCR 测试
   docs: 更新项目文档
   chore: 更新依赖

5. 每次 commit 完成后，必须立即推送到 GitHub。

   默认执行：

   git push

   如果当前分支尚未设置 upstream，则使用：

   git push -u origin <当前分支>

6. 如果项目存在 tags，并且本次开发创建了新的 tag，也必须同步推送：

   git push origin <tag>

7. 不允许为了方便而执行：

   git reset --hard
   git rebase
   git commit --amend
   git push --force
   git push --force-with-lease

   除非我明确要求。

8. 不允许删除、覆盖或重写已有 commit 历史。

9. 如果发现以下情况，必须暂停 push，并先告诉我：

   - API Key
   - Token
   - Password
   - 私钥
   - Cookie
   - .env 中的敏感信息
   - 其他凭据

10. 不要因为“需要 commit”而提交明显不应该进入 Git 的文件。

   包括但不限于：

   - .env
   - API 密钥文件
   - Python 虚拟环境
   - __pycache__
   - *.pyc
   - 临时日志
   - 临时 OCR 输出
   - 编译产生的临时文件

11. 如果某次修改没有实际产生代码或项目文件变化，则不需要创建空 commit。

12. 如果一次任务包含多个相互独立的功能，可以分别 commit，而不是把所有修改塞进一个巨大的 commit。

13. 如果一次修改涉及多个文件，但它们共同构成同一个完整功能，可以使用一个 commit。

14. 每次 commit 后必须确认 push 是否成功。

15. 如果 push 失败：
   - 不要假装成功
   - 不要重复进行危险操作
   - 分析失败原因
   - 告诉我具体错误
   - 等待进一步处理

16. 每次完成任务后，向我报告：

   Commit:
   <commit hash>

   Message:
   <commit message>

   Push:
   SUCCESS / FAILED

   Branch:
   <branch>

17. 最重要的规则：

   【完成一个可验证的开发步骤 → 测试 → 检查 → commit → push 到 GitHub】

   GitHub 上的仓库应始终尽可能保持与本地已完成开发状态同步。

18. 在开始下一项较大的开发任务之前，先确认当前工作区：

   git status

   如果存在上一阶段未提交的修改，应优先处理上一阶段的 commit，而不是继续无期限累积修改。