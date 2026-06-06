from __future__ import annotations

from typing import Any

import aiohttp


def _normalize_str_value(value: Any) -> str:
    """将候选值规范化为可用的字符串。"""

    if isinstance(value, str) and value.strip():
        return value.strip()
    return ""


def _extract_image_info_from_segment(segment: dict[str, Any]) -> dict[str, str]:
    """从单个消息段中提取图片信息，优先返回 base64，其次 file_id，其次 URL。"""

    segment_type = str(segment.get("type") or "").strip()
    if segment_type != "image":
        return {}

    result: dict[str, str] = {}

    base64_keys = ("binary_data_base64", "base64", "image_base64", "file_base64")
    for key in base64_keys:
        val = _normalize_str_value(segment.get(key))
        if val:
            result["base64"] = val
            return result

    nested_data = segment.get("data")
    if isinstance(nested_data, dict):
        for key in base64_keys:
            val = _normalize_str_value(nested_data.get(key))
            if val:
                result["base64"] = val
                return result

    file_id_keys = ("file_id", "file", "image_file_id")
    for key in file_id_keys:
        val = _normalize_str_value(segment.get(key))
        if val:
            result["file_id"] = val
            break

    if not result and isinstance(nested_data, dict):
        for key in file_id_keys:
            val = _normalize_str_value(nested_data.get(key))
            if val:
                result["file_id"] = val
                break

    url_keys = ("url", "image_url", "file_url")
    for key in url_keys:
        val = _normalize_str_value(segment.get(key))
        if val:
            result["url"] = val
            break

    if not result and isinstance(nested_data, dict):
        for key in url_keys:
            val = _normalize_str_value(nested_data.get(key))
            if val:
                result["url"] = val
                break

    return result


def _extract_segments_from_message(message: dict[str, Any]) -> list[dict[str, Any]]:
    """兼容不同消息格式，提取统一的消息段列表。"""

    normalized_segments: list[dict[str, Any]] = []
    candidate_segment_lists = (
        message.get("message_segments"),
        message.get("raw_message"),
    )
    for candidate_segments in candidate_segment_lists:
        if not isinstance(candidate_segments, list):
            continue
        for segment in candidate_segments:
            if not isinstance(segment, dict):
                continue
            normalized_segments.append(segment)
    return normalized_segments


def extract_image_base64_from_message(message: dict[str, Any]) -> str:
    """从消息结构中提取第一张图片的 Base64（仅直接可用的 base64）。"""

    for segment in _extract_segments_from_message(message):
        info = _extract_image_info_from_segment(segment)
        if info.get("base64"):
            return info["base64"]
    return ""


def extract_first_image_info(message: dict[str, Any]) -> dict[str, str]:
    """从消息结构中提取第一张图片的信息（base64 / file_id / url）。"""

    for segment in _extract_segments_from_message(message):
        info = _extract_image_info_from_segment(segment)
        if info:
            return info
    return {}


def _unwrap_message_result(result: Any) -> dict[str, Any] | None:
    """兼容运行时包装层，提取单条消息对象。"""

    if isinstance(result, list):
        for item in result:
            if isinstance(item, dict):
                return item
        return None

    if not isinstance(result, dict):
        return None

    direct_message = result.get("message")
    if isinstance(direct_message, dict):
        return direct_message

    nested_result = result.get("result")
    if isinstance(nested_result, dict):
        nested_message = nested_result.get("message")
        if isinstance(nested_message, dict):
            return nested_message

    return None


def _unwrap_messages_result(result: Any) -> list[dict[str, Any]]:
    """兼容运行时包装层，提取消息列表。"""

    if isinstance(result, list):
        return [message for message in result if isinstance(message, dict)]

    if not isinstance(result, dict):
        return []

    direct_messages = result.get("messages")
    if isinstance(direct_messages, list):
        return [message for message in direct_messages if isinstance(message, dict)]

    nested_result = result.get("result")
    if isinstance(nested_result, dict):
        nested_messages = nested_result.get("messages")
        if isinstance(nested_messages, list):
            return [message for message in nested_messages if isinstance(message, dict)]

    return []


async def get_image_from_napcat(
    napcat_api_url: str,
    file_id: str = "",
    file: str = "",
) -> dict[str, str]:
    """调用 NapCat /get_image 接口获取图片信息。

    返回 dict，可能包含 keys: base64, url, file
    """

    if not napcat_api_url:
        raise ValueError("NapCat API 地址未配置")

    payload: dict[str, str] = {}
    if file_id:
        payload["file_id"] = file_id
    elif file:
        payload["file"] = file
    else:
        raise ValueError("必须提供 file_id 或 file")

    url = f"{napcat_api_url.rstrip('/')}/get_image"
    timeout = aiohttp.ClientTimeout(total=30)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(url, json=payload) as response:
            if response.status != 200:
                error_text = await response.text()
                raise RuntimeError(f"NapCat /get_image 请求失败 ({response.status}): {error_text}")
            result = await response.json()

    if result.get("status") != "ok":
        raise RuntimeError(f"NapCat /get_image 返回失败: {result.get('message') or result.get('wording') or result}")

    data = result.get("data", {})
    if not isinstance(data, dict):
        raise RuntimeError(f"NapCat /get_image 返回数据格式不正确")

    extracted: dict[str, str] = {}
    if data.get("base64"):
        extracted["base64"] = str(data["base64"]).strip()
    if data.get("url"):
        extracted["url"] = str(data["url"]).strip()
    if data.get("file"):
        extracted["file"] = str(data["file"]).strip()

    if not extracted:
        raise RuntimeError("NapCat /get_image 未返回可用的图片数据")

    return extracted


async def resolve_image_to_base64(
    napcat_api_url: str,
    image_info: dict[str, str],
) -> str:
    """将图片信息解析为 base64。

    优先直接返回 base64，其次通过 NapCat 获取，其次通过 URL 下载。
    """

    if image_info.get("base64"):
        return image_info["base64"]

    if napcat_api_url and image_info.get("file_id"):
        napcat_result = await get_image_from_napcat(
            napcat_api_url, file_id=image_info["file_id"],
        )
        if napcat_result.get("base64"):
            return napcat_result["base64"]
        if napcat_result.get("url"):
            return await _download_as_base64(napcat_result["url"])
        if napcat_result.get("file"):
            import base64
            from pathlib import Path

            file_path = Path(napcat_result["file"])
            if file_path.exists():
                return base64.b64encode(file_path.read_bytes()).decode("utf-8")

    if napcat_api_url and image_info.get("url"):
        napcat_result = await get_image_from_napcat(
            napcat_api_url, file=image_info["url"],
        )
        if napcat_result.get("base64"):
            return napcat_result["base64"]
        if napcat_result.get("url"):
            return await _download_as_base64(napcat_result["url"])

    if image_info.get("url"):
        return await _download_as_base64(image_info["url"])

    raise ValueError("无法将图片信息解析为 base64")


async def _download_as_base64(url: str) -> str:
    """下载 URL 图片并返回 base64。"""

    import base64

    timeout = aiohttp.ClientTimeout(total=30)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(url) as response:
            if response.status != 200:
                raise RuntimeError(f"下载图片失败: status={response.status}")
            image_bytes = await response.read()
            return base64.b64encode(image_bytes).decode("utf-8")


def extract_quoted_message_id(message: dict[str, Any]) -> str:
    """从消息中提取引用/回复的消息 ID。"""

    for segment in _extract_segments_from_message(message):
        segment_type = str(segment.get("type") or "").strip()
        if segment_type == "reply":
            msg_id = str(segment.get("data", {}).get("id") or "").strip()
            if msg_id:
                return msg_id
    source = message.get("source_message_id") or message.get("source")
    if isinstance(source, str) and source.strip():
        return source.strip()
    if isinstance(source, dict):
        return str(source.get("message_id") or source.get("id") or "").strip()
    return ""


async def find_source_image(
    ctx: Any,
    stream_id: str,
    source_message_id: str = "",
    source_image_base64: str = "",
    napcat_api_url: str = "",
    current_message: dict[str, Any] | None = None,
) -> tuple[str, str]:
    """查找待编辑的源图片。

    返回 (base64, message_id)。
    优先级：
    1. 直接传入的 base64
    2. 直接传入的 message_id
    3. 当前消息中的图片
    4. 当前消息引用/回复的消息中的图片
    5. 最近消息中的第一张图片
    """

    normalized_image_base64 = source_image_base64.strip()
    if normalized_image_base64:
        return normalized_image_base64, source_message_id.strip()

    normalized_message_id = source_message_id.strip()
    if normalized_message_id:
        result = await ctx.call_capability(
            "message.get_by_id",
            message_id=normalized_message_id,
            chat_id=stream_id,
            include_binary_data=True,
        )
        message = _unwrap_message_result(result)
        if isinstance(message, dict):
            image_info = extract_first_image_info(message)
            if image_info:
                base64_data = await resolve_image_to_base64(napcat_api_url, image_info)
                return base64_data, normalized_message_id

    if isinstance(current_message, dict):
        current_image_info = extract_first_image_info(current_message)
        if current_image_info:
            current_msg_id = str(current_message.get("message_id") or "").strip()
            base64_data = await resolve_image_to_base64(napcat_api_url, current_image_info)
            return base64_data, current_msg_id

        quoted_id = extract_quoted_message_id(current_message)
        if quoted_id:
            try:
                result = await ctx.call_capability(
                    "message.get_by_id",
                    message_id=quoted_id,
                    chat_id=stream_id,
                    include_binary_data=True,
                )
                quoted_msg = _unwrap_message_result(result)
                if isinstance(quoted_msg, dict):
                    quoted_image_info = extract_first_image_info(quoted_msg)
                    if quoted_image_info:
                        base64_data = await resolve_image_to_base64(napcat_api_url, quoted_image_info)
                        return base64_data, quoted_id
            except Exception:
                pass

    recent_result = await ctx.call_capability(
        "message.get_recent",
        chat_id=stream_id,
        limit=8,
        include_binary_data=True,
    )
    if not isinstance(recent_result, (dict, list)):
        raise ValueError("无法读取最近消息，无法自动寻找待编辑图片")
    recent_messages = _unwrap_messages_result(recent_result)
    if not recent_messages:
        raise ValueError("最近消息返回格式不正确，无法自动寻找待编辑图片")

    for message in reversed(recent_messages):
        image_info = extract_first_image_info(message)
        if image_info:
            base64_data = await resolve_image_to_base64(napcat_api_url, image_info)
            msg_id = str(message.get("message_id") or "").strip()
            return base64_data, msg_id

    raise ValueError("最近消息中没有找到图片，请先发送图片，或显式传入 source_message_id")
