from __future__ import annotations

import base64
import mimetypes
import time
from io import BytesIO
from typing import Any

import aiohttp
from PIL import Image as PILImage


class OpenaiImage:
    """OpenAI 兼容图片接口封装。"""

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.openai.com",
        compatibility_mode: str = "auto",
        logger: Any | None = None,
        request_timeout_seconds: int = 150,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.compatibility_mode = compatibility_mode
        self.logger = logger
        self.request_timeout_seconds = request_timeout_seconds

    async def generate_images(self, prompt: str, model: str, n: int = 1) -> list[bytes]:
        """文生图。POST /v1/images/generations"""

        payload: dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "n": n,
            "size": "1024x1024",
        }
        response = await self._request_json("POST", "/v1/images/generations", json_payload=payload)
        return self._extract_images(response)

    async def edit_images(self, prompt: str, model: str, image_bytes: bytes, n: int = 1) -> list[bytes]:
        """图生图。POST /v1/images/edits"""

        mime_type = self._detect_mime_type(image_bytes)
        filename = self._guess_filename(mime_type)
        form_data: dict[str, str] = {
            "model": model,
            "prompt": prompt,
            "n": str(n),
            "size": "1024x1024",
        }
        file_data = {"image": (filename, image_bytes, mime_type)}
        response = await self._request_form("POST", "/v1/images/edits", fields=form_data, files=file_data)
        return self._extract_images(response)

    def _build_headers(self, with_json: bool = False) -> dict[str, str]:
        headers = {"Authorization": f"Bearer {self.api_key}"}
        if with_json:
            headers["Content-Type"] = "application/json"
        return headers

    async def _request_json(self, method: str, path: str, json_payload: dict[str, Any] | None = None) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        start = time.time()
        timeout = aiohttp.ClientTimeout(total=self.request_timeout_seconds)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url, headers=self._build_headers(with_json=True), json=json_payload) as resp:
                duration = time.time() - start
                if resp.status != 200:
                    error_text = await resp.text()
                    self._log_error("OpenAI API错误: status=%s duration=%.2fs url=%s response=%s", resp.status, duration, url, error_text[:1200])
                    raise RuntimeError(f"OpenAI 接口错误 ({resp.status}, 耗时: {duration:.2f}s): {error_text}")
                return await resp.json()

    async def _request_form(
        self,
        method: str,
        path: str,
        fields: dict[str, str],
        files: dict[str, tuple[str, bytes, str]],
    ) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        start = time.time()
        timeout = aiohttp.ClientTimeout(total=self.request_timeout_seconds)
        form = aiohttp.FormData()
        for key, value in fields.items():
            form.add_field(key, value)
        for key, (filename, data, content_type) in files.items():
            form.add_field(key, data, filename=filename, content_type=content_type)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url, headers=self._build_headers(), data=form) as resp:
                duration = time.time() - start
                if resp.status != 200:
                    error_text = await resp.text()
                    self._log_error("OpenAI API错误: status=%s duration=%.2fs url=%s response=%s", resp.status, duration, url, error_text[:1200])
                    raise RuntimeError(f"OpenAI 接口错误 ({resp.status}, 耗时: {duration:.2f}s): {error_text}")
                return await resp.json()

    def _extract_images(self, response: dict[str, Any]) -> list[bytes]:
        data = response.get("data")
        if not isinstance(data, list) or not data:
            raise RuntimeError(f"接口响应中没有图片数据: {str(response)[:800]}")
        image_bytes_list: list[bytes] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            b64 = item.get("b64_json")
            if isinstance(b64, str) and b64:
                image_bytes_list.append(base64.b64decode(b64))
                continue
            url = item.get("url")
            if isinstance(url, str) and url:
                image_bytes_list.append(self._download_image_sync(url))
        if not image_bytes_list:
            raise RuntimeError("响应中没有可识别的图片")
        return image_bytes_list

    @staticmethod
    def _detect_mime_type(image_bytes: bytes) -> str:
        with PILImage.open(BytesIO(image_bytes)) as image:
            fmt = str(image.format or "PNG").upper()
        mime_map = {"JPEG": "image/jpeg", "JPG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}
        return mime_map.get(fmt, "image/png")

    @staticmethod
    def _guess_filename(mime_type: str) -> str:
        ext_map = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}
        return f"source.{ext_map.get(mime_type, 'png')}"

    def _download_image_sync(self, url: str) -> bytes:
        import urllib.request
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {self.api_key}"})
        with urllib.request.urlopen(req, timeout=self.request_timeout_seconds) as resp:
            return resp.read()

    def _log_error(self, message: str, *args: Any) -> None:
        if self.logger is not None:
            self.logger.error(message, *args)
