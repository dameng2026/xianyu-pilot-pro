"""Bounded knowledge-file parsing and AI rule extraction routes.

Supported formats are UTF-8/GB18030 text, CSV, and the OOXML .xlsx/.pptx
containers handled by the pinned parsers. Legacy binary .xls/.ppt files are
rejected explicitly instead of advertising a capability the runtime lacks.
"""
import asyncio
import io
import csv
import logging
import stat
import zipfile
from pathlib import PurePosixPath
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, File, Form, Header, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from ....core.database import get_db
from ....core.http_failures import log_route_failure, safe_route_failure
from ....core.response import ResultObject
from ....services.ai_provider import generate_text
from ....services.ai_billing import (
    AiBillingError,
    AiBillingPaymentRequired,
    charge_text_usage,
    estimate_text_tokens,
    precheck_ai_usage,
)
from ....services.upload_governance import UploadGovernanceError, govern_transient_upload
from .internal import verify_internal_token
from ..deps import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/knowledge-base", tags=["knowledgeBase"])

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
MAX_OOXML_MEMBERS = 512
MAX_OOXML_UNCOMPRESSED_BYTES = 50 * 1024 * 1024
MAX_OOXML_COMPRESSION_RATIO = 100
MAX_OOXML_MEMBER_BYTES = 20 * 1024 * 1024
MAX_PARSED_CHARACTERS = 100_000
MAX_WORKSHEETS = 50
MAX_SPREADSHEET_ROWS = 10_000
MAX_SPREADSHEET_CELLS = 100_000
MAX_SLIDES = 200
MAX_PRESENTATION_SHAPES = 5_000
MAX_PRESENTATION_TABLE_CELLS = 50_000
PARSE_TIMEOUT_SECONDS = 15.0
_PARSE_CONCURRENCY = 2
_parse_semaphore = asyncio.Semaphore(_PARSE_CONCURRENCY)

# Legacy binary .xls/.ppt files are deliberately not advertised: the pinned
# parsers support OOXML (.xlsx/.pptx), not the older OLE container formats.
ALLOWED_EXTENSIONS = {".md", ".txt", ".pptx", ".xlsx", ".csv"}

_ALLOWED_MEDIA_TYPES = {
    ".md": {"application/octet-stream", "text/markdown", "text/plain", "text/x-markdown"},
    ".txt": {"application/octet-stream", "text/plain"},
    ".csv": {
        "application/csv",
        "application/octet-stream",
        "application/vnd.ms-excel",
        "text/csv",
        "text/plain",
    },
    ".xlsx": {
        "application/octet-stream",
        "application/zip",
        "application/x-zip-compressed",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    },
    ".pptx": {
        "application/octet-stream",
        "application/zip",
        "application/x-zip-compressed",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    },
}


class KnowledgeUploadError(ValueError):
    def __init__(self, public_message: str, status_code: int = 422):
        self.public_message = public_message
        self.status_code = status_code
        super().__init__(public_message)

EXTRACT_PROMPT_TEMPLATE = """你是客服规则提取助手。请从以下文件内容中提取所有可作为 AI 客服回复规则的信息，输出为结构化 Markdown 文本。

要求：
1. 按类别分组，使用二级标题（如 ## 售后政策 / ## 发货说明 / ## 商品 FAQ / ## 退换货规则 / ## 价格优惠 / ## 规格参数）
2. 每条规则用 "- " 开头，包含：触发场景、回复要点、注意事项
3. 只输出与客服回复相关的内容，忽略文件中的导航、版权、广告等无关信息
4. 保持原文事实，不要编造规则
5. 如果文件内容与客服无关，返回空字符串

文件内容：
{file_content}
"""


def _authenticated_tenant_id(current_user: dict) -> int:
    try:
        tenant_id = int(current_user.get("tenant_id") or 0)
    except (TypeError, ValueError):
        tenant_id = 0
    if tenant_id <= 0:
        raise ValueError("缺少租户上下文")
    return tenant_id


def _optional_positive_id(value: object, field: str) -> int | None:
    if value in (None, "", 0, "0"):
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise KnowledgeUploadError(f"{field} 必须为正整数", 400) from exc
    if parsed <= 0:
        raise KnowledgeUploadError(f"{field} 必须为正整数", 400)
    return parsed


def _bind_internal_tenant(header_tenant_id: object, claimed_tenant_id: object) -> int:
    """Use the authenticated internal header as the only tenant authority."""

    tenant_id = _optional_positive_id(header_tenant_id, "内部租户上下文")
    if tenant_id is None:
        raise KnowledgeUploadError("缺少内部租户上下文", 400)
    claimed = _optional_positive_id(claimed_tenant_id, "tenantId")
    if claimed is not None and claimed != tenant_id:
        raise KnowledgeUploadError("请求租户上下文不一致", 403)
    return tenant_id


def _validate_claimed_tenant(claimed_tenant_id: object, authenticated_tenant_id: int) -> None:
    claimed = _optional_positive_id(claimed_tenant_id, "tenantId")
    if claimed is not None and claimed != authenticated_tenant_id:
        raise KnowledgeUploadError("请求租户上下文不一致", 403)


def _validate_declared_media_type(extension: str, declared_media_type: str | None) -> None:
    declared = str(declared_media_type or "").split(";", 1)[0].strip().lower()
    if not declared:
        return
    allowed = _ALLOWED_MEDIA_TYPES.get(extension, set())
    if declared not in allowed:
        raise KnowledgeUploadError("文件媒体类型与扩展名不匹配", 400)


async def _read_upload_limited(file: UploadFile) -> bytes:
    content = await file.read(MAX_FILE_SIZE + 1)
    if not content:
        raise KnowledgeUploadError("文件内容为空", 400)
    if len(content) > MAX_FILE_SIZE:
        raise KnowledgeUploadError("文件不能超过 10MB", 413)
    return bytes(content)


def _validate_ooxml_package(extension: str, content: bytes) -> None:
    """Reject malformed, mismatched, encrypted, or expansion-heavy OOXML."""

    if not content.startswith(b"PK\x03\x04") or not zipfile.is_zipfile(io.BytesIO(content)):
        raise KnowledgeUploadError("Office 文件内容与扩展名不匹配")
    required_member = {
        ".xlsx": "xl/workbook.xml",
        ".pptx": "ppt/presentation.xml",
    }.get(extension)
    if required_member is None:
        raise KnowledgeUploadError("不支持的 Office 文件类型", 400)

    try:
        with zipfile.ZipFile(io.BytesIO(content), "r") as archive:
            members = archive.infolist()
            if len(members) > MAX_OOXML_MEMBERS:
                raise KnowledgeUploadError("Office 文件包含过多内部条目")

            names: set[str] = set()
            total_uncompressed = 0
            for member in members:
                name = member.filename
                if not name or "\\" in name or "\x00" in name:
                    raise KnowledgeUploadError("Office 文件包含不安全路径")
                path = PurePosixPath(name)
                if path.is_absolute() or ".." in path.parts or ":" in path.parts[0]:
                    raise KnowledgeUploadError("Office 文件包含不安全路径")
                if name in names:
                    raise KnowledgeUploadError("Office 文件包含重复条目")
                names.add(name)
                if member.flag_bits & 0x1:
                    raise KnowledgeUploadError("不支持加密的 Office 文件")
                mode = (member.external_attr >> 16) & 0xFFFF
                if mode and stat.S_ISLNK(mode):
                    raise KnowledgeUploadError("Office 文件包含不安全链接")
                if member.is_dir():
                    continue
                if member.file_size < 0 or member.file_size > MAX_OOXML_MEMBER_BYTES:
                    raise KnowledgeUploadError("Office 文件内部条目过大")
                total_uncompressed += member.file_size
                if total_uncompressed > MAX_OOXML_UNCOMPRESSED_BYTES:
                    raise KnowledgeUploadError("Office 文件展开后超过 50MB")
                if member.file_size:
                    ratio = member.file_size / max(member.compress_size, 1)
                    if ratio > MAX_OOXML_COMPRESSION_RATIO:
                        raise KnowledgeUploadError("Office 文件压缩比超过安全限制")
                if name.lower().endswith((".xml", ".rels")):
                    with archive.open(member, "r") as stream:
                        prefix = stream.read(min(member.file_size, 64 * 1024)).upper()
                    if b"<!DOCTYPE" in prefix or b"<!ENTITY" in prefix:
                        raise KnowledgeUploadError("Office 文件包含不安全 XML 声明")

            if "[Content_Types].xml" not in names or required_member not in names:
                raise KnowledgeUploadError("Office 文件结构与扩展名不匹配")
    except KnowledgeUploadError:
        raise
    except (OSError, RuntimeError, zipfile.BadZipFile, zipfile.LargeZipFile) as exc:
        raise KnowledgeUploadError("Office 文件已损坏或无法安全解析") from exc


def _decode_text(content: bytes) -> str:
    if b"\x00" in content:
        raise KnowledgeUploadError("文本文件包含二进制内容")
    for encoding in ("utf-8-sig", "gb18030"):
        try:
            text_value = content.decode(encoding)
            disallowed_controls = sum(
                1 for char in text_value if ord(char) < 32 and char not in "\r\n\t"
            )
            if disallowed_controls > max(4, len(text_value) // 1000):
                raise KnowledgeUploadError("文本文件包含过多控制字符")
            return text_value
        except UnicodeDecodeError:
            continue
    raise KnowledgeUploadError("文本文件编码不受支持，请使用 UTF-8 或 GB18030")


def _release_parse_slot(task: asyncio.Task) -> None:
    try:
        task.exception()
    except (asyncio.CancelledError, Exception):
        pass
    _parse_semaphore.release()


async def _parse_file_async(ext: str, content: bytes, filename: str) -> str:
    await _parse_semaphore.acquire()
    task = asyncio.create_task(asyncio.to_thread(_parse_file, ext, content, filename))
    release_in_finally = True
    try:
        return await asyncio.wait_for(asyncio.shield(task), timeout=PARSE_TIMEOUT_SECONDS)
    except asyncio.TimeoutError as exc:
        release_in_finally = False
        task.add_done_callback(_release_parse_slot)
        raise KnowledgeUploadError("文件解析超时或复杂度超过安全限制") from exc
    except asyncio.CancelledError:
        release_in_finally = False
        task.add_done_callback(_release_parse_slot)
        raise
    finally:
        if release_in_finally:
            _parse_semaphore.release()


async def _prepare_uploaded_file(file: UploadFile) -> tuple[str, str, bytes]:
    filename = str(file.filename or "unknown")
    extension = _get_extension(filename)
    if extension not in ALLOWED_EXTENSIONS:
        raise KnowledgeUploadError(
            f"不支持的文件格式：{extension or '无扩展名'}，仅支持 "
            + "/".join(sorted(ALLOWED_EXTENSIONS)),
            400,
        )
    _validate_declared_media_type(extension, getattr(file, "content_type", None))
    content = await _read_upload_limited(file)
    return filename, extension, content


async def _precheck_knowledge_usage(tenant_id: int, user_id: int, prompt: str) -> None:
    try:
        prompt_tokens = estimate_text_tokens(prompt)
        result = await precheck_ai_usage({
            "tenantId": tenant_id,
            "userId": user_id,
            "scene": "knowledge_base_extract",
            "providerName": "default",
            "modelName": "default",
            "modelType": "chat",
            "billingMode": "token",
            "promptTokens": prompt_tokens,
            "completionTokens": 2_000,
            "totalTokens": prompt_tokens + 2_000,
        })
        if not isinstance(result, dict) or result.get("skipped") is True:
            raise RuntimeError("billing precheck was skipped")
        if result.get("ok") is False or result.get("enough") is not True:
            raise RuntimeError(str(result.get("message") or "billing precheck rejected"))
    except AiBillingError as exc:
        raise KnowledgeUploadError(exc.user_message, exc.status_code) from exc
    except Exception as exc:
        raise KnowledgeUploadError("AI 计费预检查暂时不可用，尚未调用模型，请稍后重试", 503) from exc


async def _charge_knowledge_usage(
    *,
    tenant_id: int,
    user_id: int,
    prompt: str,
    extracted: str,
    ai_result: dict[str, Any],
) -> None:
    provider_request_id = str(ai_result.get("requestId") or "").strip()
    if not provider_request_id:
        raise KnowledgeUploadError("AI 返回结果缺少计费请求编号，结果未交付，请稍后重试", 503)
    try:
        charged = await charge_text_usage(
            tenant_id=tenant_id,
            user_id=user_id,
            scene="knowledge_base_extract",
            provider_name=str(ai_result.get("provider") or "default"),
            model_name=str(ai_result.get("model") or "default"),
            prompt=prompt,
            completion=extracted,
            request_id=provider_request_id,
            raw_usage=ai_result.get("usage") or {},
        )
        if not isinstance(charged, dict) or charged.get("skipped") is True:
            raise RuntimeError("billing charge was skipped")
        if charged.get("deducted") is not True and charged.get("duplicate") is not True:
            raise RuntimeError("billing charge was not confirmed")
    except AiBillingPaymentRequired as exc:
        raise KnowledgeUploadError(
            "AI 已完成处理，但 Token 余额不足；结果未交付，请充值后使用原请求重试",
            402,
        ) from exc
    except AiBillingError as exc:
        raise KnowledgeUploadError(
            "AI 已完成处理，但计费服务暂时不可用；结果未交付，请使用原请求重试",
            exc.status_code,
        ) from exc
    except Exception as exc:
        raise KnowledgeUploadError(
            "AI 已完成处理，但计费结果暂时无法确认；结果未交付，请使用原请求重试",
            503,
        ) from exc


@router.post("/extract")
async def extract_knowledge_base(
    file: UploadFile = File(...),
    userId: Optional[str] = Form(None),
    tenantId: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
    x_internal_tenant_id: Optional[str] = Header(None, alias="X-Internal-Tenant-Id"),
    _: None = Depends(verify_internal_token),
):
    """接收文件，解析后调用 AI 提取客服回复规则，返回结构化 Markdown。

    可选表单字段：
      userId:  当前用户 ID（由 Java 网关从 TenantContext 透传，用于 AI 调用扣费）
      tenantId: 当前租户 ID（同上）
    """
    filename = "unknown"
    try:
        authenticated_tenant_id = _bind_internal_tenant(x_internal_tenant_id, tenantId)
        authenticated_user_id = _optional_positive_id(userId, "userId")
        if authenticated_user_id is None:
            raise KnowledgeUploadError("缺少可计费用户上下文", 400)
        filename, ext, content = await _prepare_uploaded_file(file)

        async with govern_transient_upload(
            content,
            tenant_id=authenticated_tenant_id,
            user_id=authenticated_user_id,
            source_type="knowledge-base-extract",
        ):
            file_text = await _parse_file_async(ext, content, filename)
            if not file_text.strip():
                raise KnowledgeUploadError("文件内容为空或无法解析")
            if len(file_text) > 30000:
                file_text = file_text[:30000] + "\n\n（文件内容过长，已截断）"
                logger.info("知识库文件内容截断至 30000 字符")

            prompt = EXTRACT_PROMPT_TEMPLATE.format(file_content=file_text)
            await _precheck_knowledge_usage(authenticated_tenant_id, authenticated_user_id, prompt)
            extracted, ai_result = await _call_ai_extract(prompt)
            await _charge_knowledge_usage(
                tenant_id=authenticated_tenant_id,
                user_id=authenticated_user_id,
                prompt=prompt,
                extracted=extracted,
                ai_result=ai_result,
            )
            if not extracted or not extracted.strip():
                return ResultObject.failed("AI 未能从文件中提取有效规则，请检查文件内容或重试")

            rule_count = extracted.count("\n- ") + (1 if extracted.strip().startswith("- ") else 0)
            return ResultObject.success({
                "extractedText": extracted.strip(),
                "ruleCount": max(rule_count, 0),
                "fileName": filename,
            })
    except KnowledgeUploadError as e:
        return ResultObject.failed(e.public_message, code=e.status_code)
    except UploadGovernanceError as e:
        return ResultObject.failed(e.public_message, code=e.status_code)
    except Exception as e:
        return safe_route_failure(logger, e, operation="extract knowledge base file", user_message="文件处理失败，请稍后重试")


async def _call_ai_extract(prompt: str) -> tuple[str, Dict[str, Any]]:
    """调用 AI 生成文本。

    ai_provider.generate_text 是 async 函数，返回 dict：
    - 成功：{"ok": True, "content": "...", "provider": ..., "model": ..., "requestId": ..., "usage": ...}
    - 失败：{"ok": False, "error": "...", ...}
    本函数提取 content 文本，失败时抛 RuntimeError 由上层捕获。
    返回元组：(content 文本, 原始 ai_result dict) 供上层扣费使用。
    """
    result: Dict[str, Any] = await generate_text(
        scene="knowledge_base_extract",
        system_prompt="你是专业的客服规则提取助手，擅长从文档中提炼结构化的客服回复规则。",
        user_prompt=prompt,
        temperature=0.3,
    )

    if not result.get("ok"):
        err = result.get("error") or "AI 调用失败且未返回错误信息"
        raise RuntimeError(f"AI 提取失败：{err}")

    content = result.get("content") or ""
    return str(content).strip(), result


def _get_extension(filename: str) -> str:
    """获取文件扩展名（小写，带点）。"""
    if "." not in filename:
        return ""
    return "." + filename.rsplit(".", 1)[-1].lower()


def _parse_file(ext: str, content: bytes, filename: str) -> str:
    """根据扩展名选择解析器，提取纯文本。"""
    try:
        if ext in (".md", ".txt"):
            return _decode_text(content)[:MAX_PARSED_CHARACTERS]
        if ext == ".csv":
            return _parse_csv(content)
        if ext == ".xlsx":
            _validate_ooxml_package(ext, content)
            return _parse_excel(content)
        if ext == ".pptx":
            _validate_ooxml_package(ext, content)
            return _parse_ppt(content)
        raise KnowledgeUploadError(f"不支持的文件格式：{ext}", 400)
    except KnowledgeUploadError:
        raise
    except Exception as e:
        logger.warning(
            "知识库文件解析失败 ext=%s errorType=%s",
            ext,
            type(e).__name__,
        )
        raise KnowledgeUploadError("文件已损坏、过于复杂或无法安全解析") from e


def _parse_csv(content: bytes) -> str:
    """解析 CSV 文件，返回表格文本。"""
    text_value = _decode_text(content)
    reader = csv.reader(io.StringIO(text_value))
    lines: list[str] = []
    total_characters = 0
    total_cells = 0
    for row_index, row in enumerate(reader, start=1):
        if row_index > MAX_SPREADSHEET_ROWS:
            raise KnowledgeUploadError("CSV 行数超过安全限制")
        total_cells += len(row)
        if total_cells > MAX_SPREADSHEET_CELLS:
            raise KnowledgeUploadError("CSV 单元格数量超过安全限制")
        if any(cell.strip() for cell in row):
            line = " | ".join(cell[:4000] for cell in row)
            remaining = MAX_PARSED_CHARACTERS - total_characters
            if remaining <= 0:
                break
            lines.append(line[:remaining])
            total_characters += min(len(line), remaining) + 1
    return "\n".join(lines)


def _parse_excel(content: bytes) -> str:
    """解析 Excel 文件，返回所有 sheet 的表格文本。"""
    from openpyxl import load_workbook
    wb = load_workbook(io.BytesIO(content), data_only=True, read_only=True, keep_links=False)
    try:
        if len(wb.sheetnames) > MAX_WORKSHEETS:
            raise KnowledgeUploadError("工作表数量超过安全限制")
        lines: list[str] = []
        total_rows = 0
        total_cells = 0
        total_characters = 0
        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            heading = f"### 工作表：{str(sheet_name)[:200]}"
            lines.append(heading)
            total_characters += len(heading) + 1
            for row in ws.iter_rows(values_only=True):
                total_rows += 1
                total_cells += len(row)
                if total_rows > MAX_SPREADSHEET_ROWS:
                    raise KnowledgeUploadError("工作表总行数超过安全限制")
                if total_cells > MAX_SPREADSHEET_CELLS:
                    raise KnowledgeUploadError("工作表单元格数量超过安全限制")
                values = ["" if cell is None else str(cell)[:4000] for cell in row]
                if not any(value.strip() for value in values):
                    continue
                line = " | ".join(values)
                remaining = MAX_PARSED_CHARACTERS - total_characters
                if remaining <= 0:
                    return "\n".join(lines)
                lines.append(line[:remaining])
                total_characters += min(len(line), remaining) + 1
            lines.append("")
        return "\n".join(lines)
    finally:
        wb.close()


def _parse_ppt(content: bytes) -> str:
    """解析 PPT 文件，返回所有幻灯片文本。"""
    from pptx import Presentation
    prs = Presentation(io.BytesIO(content))
    if len(prs.slides) > MAX_SLIDES:
        raise KnowledgeUploadError("幻灯片数量超过安全限制")
    lines: list[str] = []
    total_shapes = 0
    total_table_cells = 0
    total_characters = 0
    for idx, slide in enumerate(prs.slides, start=1):
        total_shapes += len(slide.shapes)
        if total_shapes > MAX_PRESENTATION_SHAPES:
            raise KnowledgeUploadError("幻灯片对象数量超过安全限制")
        slide_texts: list[str] = []
        for shape in slide.shapes:
            if shape.has_text_frame:
                for paragraph in shape.text_frame.paragraphs:
                    paragraph_text = paragraph.text.strip()
                    if paragraph_text:
                        slide_texts.append(paragraph_text[:4000])
            if shape.has_table:
                for row in shape.table.rows:
                    total_table_cells += len(row.cells)
                    if total_table_cells > MAX_PRESENTATION_TABLE_CELLS:
                        raise KnowledgeUploadError("幻灯片表格单元格数量超过安全限制")
                    row_text = " | ".join(cell.text.strip() for cell in row.cells)
                    if row_text.strip(" |"):
                        slide_texts.append(row_text[:8000])
        if slide_texts:
            block = [f"### 幻灯片 {idx}", *slide_texts, ""]
            for line in block:
                remaining = MAX_PARSED_CHARACTERS - total_characters
                if remaining <= 0:
                    return "\n".join(lines)
                lines.append(line[:remaining])
                total_characters += min(len(line), remaining) + 1
    return "\n".join(lines)


# ============================================================
# RAG 知识库接口（基于 SimpleVectorStore 本地向量库）
# ============================================================
@router.post("/rag/add")
async def rag_add(
    data: dict = {},
    current_user: dict = Depends(get_current_user),
):
    """将文本切片向量化并写入 RAG 知识库。

    请求体: {
        "content": "文本内容",
        "goodsId": "123",       # 可选，关联商品 ID
        "source": "manual",      # 可选，来源标识
        "extraMetadata": {...}   # 可选，额外元数据
    }
    """
    try:
        from ....services.rag_service import add_to_rag
        tenant_id = _authenticated_tenant_id(current_user)
        content = data.get("content") or ""
        goods_id = data.get("goodsId")
        source = data.get("source")
        extra_metadata = data.get("extraMetadata")

        if not content.strip():
            return ResultObject.failed("content 不能为空")

        result = await add_to_rag(
            content=content,
            tenant_id=tenant_id,
            goods_id=str(goods_id) if goods_id else None,
            source=source,
            extra_metadata=extra_metadata,
        )
        if result.get("success"):
            return ResultObject.success(result)
        return ResultObject.failed(result.get("error") or "RAG 写入失败")
    except Exception as e:
        if isinstance(e, ValueError) and e.args == ("缺少租户上下文",):
            return ResultObject.failed("缺少租户上下文")
        return safe_route_failure(logger, e, operation="add RAG content", user_message="RAG 写入失败，请稍后重试")


@router.post("/rag/query")
async def rag_query(
    data: dict = {},
    current_user: dict = Depends(get_current_user),
):
    """检索 RAG 知识库中与问题相关的文档片段。

    请求体: {
        "question": "用户问题",
        "goodsId": "123",       # 可选，按商品过滤
        "topK": 5,               # 可选，默认 5
        "similarityThreshold": 0.3  # 可选，默认 0.3
    }
    """
    try:
        from ....services.rag_service import query_rag, DEFAULT_TOP_K, DEFAULT_SIMILARITY_THRESHOLD
        tenant_id = _authenticated_tenant_id(current_user)
        question = data.get("question") or ""
        goods_id = data.get("goodsId")
        top_k = int(data.get("topK") or DEFAULT_TOP_K)
        threshold = float(data.get("similarityThreshold") or DEFAULT_SIMILARITY_THRESHOLD)

        if not question.strip():
            return ResultObject.failed("question 不能为空")

        result = await query_rag(
            question=question,
            tenant_id=tenant_id,
            goods_id=str(goods_id) if goods_id else None,
            top_k=top_k,
            similarity_threshold=threshold,
        )
        if result.get("success"):
            return ResultObject.success(result)
        return ResultObject.failed(result.get("error") or "RAG 检索失败")
    except Exception as e:
        if isinstance(e, ValueError) and e.args == ("缺少租户上下文",):
            return ResultObject.failed("缺少租户上下文")
        return safe_route_failure(logger, e, operation="query RAG content", user_message="RAG 检索失败，请稍后重试")


@router.post("/rag/chat")
async def rag_chat(
    data: dict = {},
    current_user: dict = Depends(get_current_user),
):
    """RAG 完整链路：检索相关文档 + AI 生成回复。

    请求体: {
        "question": "用户问题",
        "goodsId": "123",
        "systemPrompt": "你是客服助手...",  # 可选
        "topK": 5,
        "similarityThreshold": 0.3
    }
    """
    try:
        from ....services.rag_service import chat_by_rag, DEFAULT_TOP_K, DEFAULT_SIMILARITY_THRESHOLD
        tenant_id = _authenticated_tenant_id(current_user)
        question = data.get("question") or ""
        goods_id = data.get("goodsId")
        system_prompt = data.get("systemPrompt")
        top_k = int(data.get("topK") or DEFAULT_TOP_K)
        threshold = float(data.get("similarityThreshold") or DEFAULT_SIMILARITY_THRESHOLD)

        if not question.strip():
            return ResultObject.failed("question 不能为空")

        result = await chat_by_rag(
            question=question,
            tenant_id=tenant_id,
            goods_id=str(goods_id) if goods_id else None,
            system_prompt=system_prompt,
            top_k=top_k,
            similarity_threshold=threshold,
        )
        if result.get("success"):
            return ResultObject.success(result)
        return ResultObject.failed(result.get("error") or "RAG 对话失败")
    except Exception as e:
        if isinstance(e, ValueError) and e.args == ("缺少租户上下文",):
            return ResultObject.failed("缺少租户上下文")
        return safe_route_failure(logger, e, operation="RAG chat", user_message="RAG 对话失败，请稍后重试")


@router.post("/rag/delete")
async def rag_delete(
    data: dict = {},
    current_user: dict = Depends(get_current_user),
):
    """删除指定商品的所有 RAG 文档。

    请求体: {"goodsId": "123"}
    """
    try:
        from ....services.rag_service import delete_rag_by_goods_id
        tenant_id = _authenticated_tenant_id(current_user)
        goods_id = data.get("goodsId")
        if not goods_id:
            return ResultObject.failed("goodsId 不能为空")

        result = await delete_rag_by_goods_id(str(goods_id), tenant_id=tenant_id)
        return ResultObject.success(result)
    except Exception as e:
        if isinstance(e, ValueError) and e.args == ("缺少租户上下文",):
            return ResultObject.failed("缺少租户上下文")
        return safe_route_failure(logger, e, operation="delete RAG content", user_message="RAG 删除失败，请稍后重试")


@router.get("/rag/stats")
async def rag_stats(
    current_user: dict = Depends(get_current_user),
):
    """获取 RAG 知识库统计信息"""
    try:
        from ....services.rag_service import get_rag_stats
        tenant_id = _authenticated_tenant_id(current_user)
        stats = await get_rag_stats(tenant_id=tenant_id)
        return ResultObject.success(stats)
    except Exception as e:
        if isinstance(e, ValueError) and e.args == ("缺少租户上下文",):
            return ResultObject.failed("缺少租户上下文")
        return safe_route_failure(logger, e, operation="get RAG stats", user_message="获取统计失败，请稍后重试")


@router.post("/rag/extract-and-add")
async def rag_extract_and_add(
    file: UploadFile = File(...),
    goodsId: Optional[str] = Form(None),
    userId: Optional[str] = Form(None),
    tenantId: Optional[str] = Form(None),
    current_user: dict = Depends(get_current_user),
):
    """一键完成：上传文件 → AI 提取规则 → 切片向量化 → 写入 RAG

    结合原有的 /extract 接口和 RAG /add 接口，端到端完成知识库入库。
    """
    filename = "unknown"
    try:
        from ....services.rag_service import add_to_rag
        authenticated_tenant_id = _authenticated_tenant_id(current_user)
        authenticated_user_id = _optional_positive_id(current_user.get("user_id"), "userId")
        if authenticated_user_id is None:
            raise KnowledgeUploadError("缺少可计费用户上下文", 400)
        _validate_claimed_tenant(tenantId, authenticated_tenant_id)
        claimed_user_id = _optional_positive_id(userId, "userId")
        if claimed_user_id is not None and claimed_user_id != authenticated_user_id:
            raise KnowledgeUploadError("请求用户上下文不一致", 403)

        filename, ext, content = await _prepare_uploaded_file(file)
        async with govern_transient_upload(
            content,
            tenant_id=authenticated_tenant_id,
            user_id=authenticated_user_id,
            source_type="knowledge-base-rag",
        ):
            file_text = await _parse_file_async(ext, content, filename)
            if not file_text.strip():
                raise KnowledgeUploadError("文件内容为空或无法解析")
            if len(file_text) > 30000:
                file_text = file_text[:30000] + "\n\n（文件内容过长，已截断）"

            prompt = EXTRACT_PROMPT_TEMPLATE.format(file_content=file_text)
            await _precheck_knowledge_usage(authenticated_tenant_id, authenticated_user_id, prompt)
            extracted, ai_result = await _call_ai_extract(prompt)
            await _charge_knowledge_usage(
                tenant_id=authenticated_tenant_id,
                user_id=authenticated_user_id,
                prompt=prompt,
                extracted=extracted,
                ai_result=ai_result,
            )
            if not extracted or not extracted.strip():
                return ResultObject.failed("AI 未能从文件中提取有效规则")

            rag_result = await add_to_rag(
                content=extracted,
                tenant_id=authenticated_tenant_id,
                goods_id=goodsId,
                source=f"file:{filename}",
                extra_metadata={"fileName": filename, "extractedBy": "ai"},
            )

            if not rag_result.get("success"):
                return ResultObject.success({
                    "extractedText": extracted.strip(),
                    "ruleCount": extracted.count("\n- ") + (1 if extracted.strip().startswith("- ") else 0),
                    "fileName": filename,
                    "ragWarning": rag_result.get("error") or "RAG 写入失败",
                })

            return ResultObject.success({
                "extractedText": extracted.strip(),
                "ruleCount": extracted.count("\n- ") + (1 if extracted.strip().startswith("- ") else 0),
                "fileName": filename,
                "ragChunkCount": rag_result.get("chunkCount", 0),
                "ragDocId": rag_result.get("docId"),
                "goodsId": goodsId,
            })
    except KnowledgeUploadError as e:
        return ResultObject.failed(e.public_message, code=e.status_code)
    except UploadGovernanceError as e:
        return ResultObject.failed(e.public_message, code=e.status_code)
    except Exception as e:
        if isinstance(e, ValueError) and e.args == ("缺少租户上下文",):
            return ResultObject.failed("缺少租户上下文")
        return safe_route_failure(logger, e, operation="extract and add RAG content", user_message="处理失败，请稍后重试")
