"""Safe, atomic file artifacts (PDF and user supplied screenshots)."""
import base64
import binascii
import hashlib
import os
import re
import struct
import tempfile
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
from .attachment_lock import attachment_lifecycle_lock


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
    with attachment_lifecycle_lock(target.parents[1]):
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
    with attachment_lifecycle_lock(data_dir):
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


def _valid_png(raw: bytes) -> bool:
    signature = b"\x89PNG\r\n\x1a\n"
    if not raw.startswith(signature):
        return False
    offset = len(signature)
    saw_header = False
    saw_end = False
    chunks = 0
    while offset + 12 <= len(raw):
        length = struct.unpack(">I", raw[offset:offset + 4])[0]
        if length > 5 * 1024 * 1024 or offset + 12 + length > len(raw):
            return False
        kind = raw[offset + 4:offset + 8]
        payload_start = offset + 8
        payload_end = payload_start + length
        payload = raw[payload_start:payload_end]
        expected_crc = struct.unpack(">I", raw[payload_end:payload_end + 4])[0]
        if binascii.crc32(kind + payload) & 0xffffffff != expected_crc:
            return False
        if not saw_header:
            if kind != b"IHDR" or length != 13:
                return False
            width, height = struct.unpack(">II", payload[:8])
            if not (0 < width <= 10000 and 0 < height <= 10000):
                return False
            saw_header = True
        if kind == b"IEND":
            saw_end = length == 0 and payload_end + 4 == len(raw)
            break
        offset = payload_end + 4
        chunks += 1
        if chunks > 100000:
            return False
    return saw_header and saw_end


def _valid_jpeg(raw: bytes) -> bool:
    if not (raw.startswith(b"\xff\xd8") and raw.endswith(b"\xff\xd9")):
        return False
    offset = 2
    saw_frame = False
    while offset + 1 < len(raw) - 2:
        if raw[offset] != 0xff:
            return False
        while offset < len(raw) and raw[offset] == 0xff:
            offset += 1
        if offset >= len(raw) - 2:
            return False
        marker = raw[offset]
        offset += 1
        if marker == 0xda:  # Start of scan; the bounded structural checks end here.
            return saw_frame
        if marker in (0xd8, 0xd9) or 0xd0 <= marker <= 0xd7:
            continue
        if offset + 2 > len(raw):
            return False
        length = struct.unpack(">H", raw[offset:offset + 2])[0]
        if length < 2 or offset + length > len(raw):
            return False
        if 0xc0 <= marker <= 0xc3 or 0xc5 <= marker <= 0xc7 or 0xc9 <= marker <= 0xcb or 0xcd <= marker <= 0xcf:
            if length < 8:
                return False
            height, width = struct.unpack(">HH", raw[offset + 3:offset + 7])
            if not (0 < width <= 10000 and 0 < height <= 10000):
                return False
            saw_frame = True
        offset += length
    return False


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
    valid = _valid_png(raw) if media == "image/png" else _valid_jpeg(raw)
    if not valid:
        raise ArtifactError("截图内容与 media_type 不匹配")
    with attachment_lifecycle_lock(data_dir):
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
