"""Optional plain-language explanation of a finding through an OpenAI-compatible API.

The model only *rephrases* evidence the tools already produced (counterexample,
diagnosis, raw logs). Its answer is never used for verdicts, CWE mapping or the
exported ``results/``. Configuration comes from the environment or a git-ignored
``.env`` file at the project root:

    AEGIS_AI_BASE_URL  or OPENAI_BASE_URL / OPENAI_API_BASE   (default https://api-ai.vnhat.dev/v1)
    AEGIS_AI_MODEL     or OPENAI_MODEL / MODEL_NAME            (default v8)
    AEGIS_AI_KEY       or OPENAI_API_KEY   (required; the feature is disabled without it)
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BASE_URL = "https://api-ai.vnhat.dev/v1"
DEFAULT_MODEL = "v8"
MAX_CONTEXT = 8000

SYSTEM_PROMPT = """Bạn giải thích kết quả của một công cụ kiểm chứng an toàn phần mềm (Kripke/CTL, BMC, \
ASan/UBSan, Z3, fuzzing) cho sinh viên. Chỉ dựa trên dữ liệu được cung cấp; không suy diễn thêm trạng thái, \
dòng mã hay giá trị không có trong dữ liệu; nếu dữ liệu không đủ để kết luận thì nói rõ. Trả lời bằng tiếng \
Việt, ngắn gọn, dạng markdown thuần (không dùng LaTeX; viết mũi tên là →) với 4 mục:
1. **Lỗi là gì**: một câu.
2. **Vì sao xảy ra**: đọc theo phản ví dụ / log / model.
3. **Hậu quả**: với một hệ thống thanh toán thật.
4. **Cách sửa**: thay đổi cụ thể trong thiết kế hoặc mã."""


@dataclass
class AIConfig:
    base_url: str
    model: str
    api_key: str | None

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)


def _dotenv(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                values[k.strip()] = v.strip().strip("'\"")
    return values


def load_config(env_file: Path | None = None) -> AIConfig:
    values = {**_dotenv(env_file or ROOT / ".env"), **os.environ}

    def first(*keys: str) -> str | None:
        return next((values[k] for k in keys if values.get(k)), None)

    return AIConfig((first("AEGIS_AI_BASE_URL", "OPENAI_BASE_URL", "OPENAI_API_BASE") or DEFAULT_BASE_URL).rstrip("/"),
                    first("AEGIS_AI_MODEL", "OPENAI_MODEL", "MODEL_NAME") or DEFAULT_MODEL,
                    first("AEGIS_AI_KEY", "OPENAI_API_KEY"))


def explain(cfg: AIConfig, context: str, timeout: int = 90) -> str:
    return chat(cfg, SYSTEM_PROMPT, context[:MAX_CONTEXT], timeout=timeout)


def chat(cfg: AIConfig, system: str, user: str, *, temperature: float = 0.2, timeout: int = 90) -> str:
    """One chat-completion round trip; returns the assistant text or raises RuntimeError."""
    if not cfg.enabled:
        raise RuntimeError("Chưa cấu hình API key (AEGIS_AI_KEY hoặc OPENAI_API_KEY, qua biến môi trường "
                           "hoặc file .env).")
    body = json.dumps({
        "model": cfg.model,
        "temperature": temperature,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
    }).encode()
    req = urllib.request.Request(f"{cfg.base_url}/chat/completions", data=body, method="POST", headers={
        "Content-Type": "application/json", "Authorization": f"Bearer {cfg.api_key}",
        # Cloudflare-fronted endpoints reject urllib's default "Python-urllib" agent (error 1010)
        "User-Agent": "AegisFlow/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"API trả lỗi HTTP {e.code}: {e.read().decode(errors='replace')[:300]}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"Không kết nối được {cfg.base_url}: {e.reason}") from e
    try:
        return data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError) as e:
        raise RuntimeError(f"Phản hồi không đúng định dạng OpenAI: {str(data)[:300]}") from e
