"""桌面 UI 到既有 OCR 流水线的适配层。"""

import hashlib
import json
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

from phase0.docx_builder import render_reflow
from phase0.provider import MIME_TYPES, OpenAICompatProvider
from phase1.pipeline import Pipeline, ProcessRecordStore
from phase2.layout import analyze_layout
from phase2.ordering import order_blocks, order_groups
from phase2.reflow import choose_columns, reflow


@dataclass(frozen=True)
class ProcessingRequest:
    """一次手动 OCR 请求；API Key 仅存在于此内存对象。"""

    image_path: Path
    output_dir: Path
    api_key: str
    base_url: str
    model: str
    timeout: int = 120
    max_retries: int = 2
    reflow: bool = False

    def validate(self):
        if not self.image_path.is_file():
            raise ValueError("请选择存在的图片文件")
        if self.image_path.suffix.lower() not in MIME_TYPES:
            raise ValueError("不支持的图片格式")
        if not self.output_dir:
            raise ValueError("请选择输出目录")
        if not self.api_key.strip():
            raise ValueError("请输入 API Key")
        if not self.base_url.strip().startswith(("https://", "http://")):
            raise ValueError("API Endpoint 必须以 http:// 或 https:// 开头")
        if not self.model.strip():
            raise ValueError("请输入模型名称")


@dataclass(frozen=True)
class ProcessingResult:
    status: str
    output_json: Path | None = None
    output_docx: Path | None = None
    error: str | None = None


def _work_dir():
    """中间产物（JSON、去重记录、failed）统一放系统 temp，用户目录只留 docx。"""
    return Path(tempfile.gettempdir()) / "further_evolution"


def _render_reflow_docx(json_path, output_path, xsl_path=None):
    """把 OCRDocument JSON 重排成横向 16:9 多栏 DOCX。"""
    data = json.loads(Path(json_path).read_text(encoding="utf-8"))
    blocks = order_blocks(data.get("blocks", []))
    layout = analyze_layout(blocks)
    groups = order_groups(layout.main)
    columns = choose_columns(len(groups))
    columns_list = reflow(groups, columns=columns)
    render_reflow(layout, columns_list, str(output_path), xsl_path)


def process_request(request, provider_factory=OpenAICompatProvider, pipeline_factory=Pipeline):
    """运行一次手动 OCR，复用 Phase 1 流水线且不移动用户原图。

    中间产物写入系统 temp 工作目录，最终仅将 DOCX 输出到用户选择的目录。
    """
    request.validate()
    request.output_dir.mkdir(parents=True, exist_ok=True)
    provider = provider_factory(
        request.api_key,
        request.base_url,
        request.model,
        request.timeout,
        request.max_retries,
    )
    work_dir = _work_dir()
    work_dir.mkdir(parents=True, exist_ok=True)
    store = ProcessRecordStore(work_dir / ".further_evolution_processed.json")
    pipeline = pipeline_factory(
        provider=provider,
        input_dir=request.image_path.parent,
        output_dir=work_dir,
        failed_dir=work_dir / "failed",
        store=store,
        move_failed=False,
    )
    status = pipeline.process_image(request.image_path)
    digest = hashlib.sha256(request.image_path.read_bytes()).hexdigest()
    record = store.records.get(digest, {})
    work_json = Path(record["output_json"]) if record.get("output_json") else None
    work_docx = Path(record["output_docx"]) if record.get("output_docx") else None

    # 竖转横：用 OCR 生成的 JSON 再重排成 16:9 多栏 DOCX（失败则回退竖向）
    reflow_warning = None
    if request.reflow and work_json and work_json.exists():
        reflow_docx = work_dir / (work_json.stem + "_reflow.docx")
        try:
            _render_reflow_docx(work_json, reflow_docx)
            work_docx = reflow_docx
        except Exception as exc:
            reflow_warning = "竖转横重排失败，已回退为竖向 Word：{}".format(exc)

    # 仅把 DOCX 复制到用户目录；JSON/去重记录/failed 留在 temp
    final_docx = None
    if work_docx and work_docx.exists():
        final_docx = request.output_dir / work_docx.name
        shutil.copy2(work_docx, final_docx)

    return ProcessingResult(
        status=status,
        output_json=work_json,
        output_docx=final_docx,
        error=record.get("error") or reflow_warning,
    )
