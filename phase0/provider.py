"""OpenAI-compatible 多模态 API 客户端（Phase 0 最小实现）。

仅负责：把一张图片发给配置好的多模态模型，返回模型输出的文本。
不涉及 GUI、监控、缓存等其它模块。
"""

import base64
import time

import requests

# 图片扩展名 -> MIME 类型
MIME_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".bmp": "image/bmp",
    ".tif": "image/tiff",
    ".tiff": "image/tiff",
    ".gif": "image/gif",
}

SYSTEM_PROMPT = """You are an OCR and document-structure extraction engine.

Analyze the image and output exactly one JSON object (no markdown fence, no extra text)
describing the document's logical structure, following this schema:

{
  "schema_version": "1.0",
  "blocks": [ ... ]
}

Each block object MUST have a "type" field, one of:
- "heading":   {"type":"heading","level":1-6,"text":"..."}
- "paragraph": {"type":"paragraph","runs":[{"kind":"text","text":"..."},{"kind":"formula","latex":"..."}]}
- "list":      {"type":"list","ordered":true|false,"items":[ [runs...], [runs...] ]}
- "table":     {"type":"table","rows":[ [ {"runs":[runs...]}, ... ], ... ]}
- "formula":   {"type":"formula","latex":"...","display":true|false}
- "image":     {"type":"image"}        // figures / illustrations / diagrams that are NOT text
- "handwritten": {"type":"handwritten","runs":[runs...]}   // handwritten content

A "run" object is either:
- {"kind":"text","text":"..."}
- {"kind":"formula","latex":"..."}

Rules:
- Preserve reading order (top to bottom, left to right).
- Distinguish headings, body paragraphs, list items, tables, and formulas.
- Every mathematical expression MUST be LaTeX in a "formula" run or "formula" block, NOT plain text.
- Inline math mixed with text -> use a "paragraph" with multiple runs.
- Handwritten content -> "handwritten" type.
- Pure figures/diagrams/illustrations (no text) -> "image" type.
- Output ONLY the JSON object."""

USER_PROMPT = "Extract the full document structure from this image as OCRDocument JSON."


class ProviderError(Exception):
    """AI 调用失败时抛出，携带可读的错误信息。"""


class OpenAICompatProvider:
    """极简 OpenAI-compatible 多模态客户端。"""

    def __init__(self, api_key, base_url, model, timeout=120, max_retries=2):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries

    def recognize(self, image_bytes, mime_type):
        """返回模型输出的原始文本内容（未解析）。"""
        data_url = "data:{mime};base64,{b64}".format(
            mime=mime_type,
            b64=base64.b64encode(image_bytes).decode("ascii"),
        )
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": USER_PROMPT},
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                },
            ],
            "temperature": 0,
        }
        headers = {
            "Authorization": "Bearer {}".format(self.api_key),
            "Content-Type": "application/json",
        }
        url = self.base_url + "/chat/completions"

        last_err = None
        for attempt in range(self.max_retries + 1):
            try:
                resp = requests.post(url, headers=headers, json=payload, timeout=self.timeout)
            except requests.exceptions.RequestException as exc:
                last_err = exc
                if attempt < self.max_retries:
                    time.sleep(2 ** attempt)
                    continue
                raise ProviderError("网络请求失败: {}".format(exc))

            if resp.status_code >= 400:
                raise ProviderError(
                    "API 返回 HTTP {}: {}".format(resp.status_code, resp.text[:500])
                )

            body = resp.json()
            content = body["choices"][0]["message"]["content"]
            if isinstance(content, list):
                content = "".join(
                    p.get("text", "") for p in content if isinstance(p, dict)
                )
            return content

        raise ProviderError("API 调用失败: {}".format(last_err))
