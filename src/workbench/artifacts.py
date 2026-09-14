"""Safe, atomic file artifacts (PDF and user supplied screenshots)."""
import base64
import binascii
import hashlib
import os
import re
import tempfile
from io import BytesIO
from pathlib import Path
from typing import Dict

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase.ttfonts import TTFont
from xml.sax.saxutils import escape


class ArtifactError(Exception):
    pass


_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_FONT_NAME = "CareerOSChinese"
_font_ready = False
_font_selected = None


def _font():
    global _font_ready, _font_selected
    if _font_ready:
        return _font_selected
    candidates = [
        "/System/Library/Fonts/PingFang.ttc", "/System/Library/Fonts/STHeiti Light.ttc",
        "/Library/Fonts/Arial Unicode.ttf", "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    ]
    for candidate in candidates:
        if os.path.isfile(candidate):
            try:
                pdfmetrics.registerFont(TTFont(_FONT_NAME, candidate, subfontIndex=0))
                _font_ready = True
                _font_selected = _FONT_NAME
                return _font_selected
            except Exception:
                pass
    # ReportLab's CID font is embedded by reference and supports Chinese glyphs.
    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
    _font_ready = True
    _font_selected = "STSong-Light"
    return _font_selected


def _target(data_dir: Path, artifact_id: str, suffix: str) -> Path:
    if not isinstance(artifact_id, str) or not _SAFE_ID.fullmatch(artifact_id):
        raise ArtifactError("artifact_id 不安全")
    root = Path(data_dir).resolve()
    directory = root / "artifacts"
    directory.mkdir(parents=True, exist_ok=True)
    target = (directory / (artifact_id + suffix)).resolve()
    if target.parent != directory:
        raise ArtifactError("附件路径越界")
    return target


def _atomic_write(target: Path, data: bytes):
    fd, name = tempfile.mkstemp(prefix=".tmp-", dir=str(target.parent))
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(name, target)
    except Exception:
        try:
            os.unlink(name)
        except OSError:
            pass
        raise


def _meta(target: Path, media_type: str) -> Dict[str, object]:
    data = target.read_bytes()
    return {"path": str(target.relative_to(target.parents[1])), "sha256": hashlib.sha256(data).hexdigest(), "media_type": media_type, "size": len(data)}


def write_pdf(data_dir: Path, artifact_id: str, content: str) -> Dict[str, object]:
    if not isinstance(content, str):
        raise ArtifactError("PDF 内容必须是文本")
    target = _target(data_dir, artifact_id, ".pdf")
    fd, name = tempfile.mkstemp(prefix=".tmp-", suffix=".pdf", dir=str(target.parent))
    os.close(fd)
    try:
        style = ParagraphStyle("CareerOS", fontName=_font(), fontSize=10, leading=15, alignment=TA_LEFT, wordWrap="CJK")
        doc = SimpleDocTemplate(name, pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm, topMargin=18 * mm, bottomMargin=18 * mm)
        flow = []
        for line in content.splitlines() or [""]:
            flow.append(Paragraph(escape(line) or "&nbsp;", style))
            flow.append(Spacer(1, 2 * mm))
        doc.build(flow)
        with open(name, "rb") as handle:
            os.fsync(handle.fileno())
        os.replace(name, target)
    except Exception as exc:
        try: os.unlink(name)
        except OSError: pass
        raise ArtifactError("生成 PDF 失败") from exc
    return _meta(target, "application/pdf")


def write_screenshot(data_dir: Path, artifact_id: str, screenshot: dict) -> Dict[str, object]:
    if not isinstance(screenshot, dict) or screenshot.get("media_type") not in ("image/png", "image/jpeg"):
        raise ArtifactError("截图仅支持 PNG 或 JPEG")
    try:
        raw = base64.b64decode(screenshot.get("data_base64", ""), validate=True)
    except (binascii.Error, ValueError, TypeError) as exc:
        raise ArtifactError("截图数据不是有效 Base64") from exc
    if not raw or len(raw) > 5 * 1024 * 1024:
        raise ArtifactError("截图大小必须不超过 5MB")
    media = screenshot["media_type"]
    valid = False
    try:
        from PIL import Image
        with Image.open(BytesIO(raw)) as image:
            if (media == "image/png" and image.format == "PNG") or (media == "image/jpeg" and image.format == "JPEG"):
                image.verify()
                valid = True
    except Exception:
        valid = False
    if not valid:
        raise ArtifactError("截图内容与 media_type 不匹配")
    target = _target(data_dir, artifact_id, ".png" if media == "image/png" else ".jpg")
    try:
        _atomic_write(target, raw)
    except Exception as exc:
        raise ArtifactError("保存截图失败") from exc
    return _meta(target, media)


def read_artifact(data_dir: Path, relative_path: str) -> Path:
    if not isinstance(relative_path, str):
        raise ArtifactError("附件路径无效")
    root = Path(data_dir).resolve()
    candidate = (root / relative_path).resolve()
    artifacts = (root / "artifacts").resolve()
    if root not in artifacts.parents or artifacts not in candidate.parents or not candidate.is_file():
        raise ArtifactError("附件路径无效")
    return candidate
