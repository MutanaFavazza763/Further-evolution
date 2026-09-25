"""桌面 UI 到既有 OCR 流水线的适配层。"""

import hashlib
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

from phase0.provider import MIME_TYPES, OpenAICompatProvider
from phase1.pipeline import Pipeline, ProcessRecordStore


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

    # 仅把 DOCX 复制到用户目录；JSON/去重记录/failed 留在 temp
    final_docx = None
    if work_docx and work_docx.exists():
        final_docx = request.output_dir / work_docx.name
        shutil.copy2(work_docx, final_docx)

    return ProcessingResult(
        status=status,
        output_json=work_json,
        output_docx=final_docx,
        error=record.get("error"),
    )
