from __future__ import annotations

import asyncio
import base64
import time
from io import BytesIO
from typing import Any

import aiohttp
from PIL import Image as PILImage


class AgnesImage:
    """Agnes 图片生成接口封装。"""

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://apihub.agnes-ai.com",
        logger: Any | None = None,
        request_timeout_seconds: int = 150,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.logger = logger
        self.request_timeout_seconds = request_timeout_seconds

    async def generate_images(self, prompt: str, model: str, n: int = 1) -> list[bytes]:
        """文生图。"""

        del n
        response = await self._post_json(
            url=f"{self.base_url}/v1/images/generations",
            payload={
                "model": model,
                "prompt": prompt,
            },
        )
        return await self._extract_images(response)

    async def edit_images(self, prompt: str, model: str, image_bytes: bytes, n: int = 1) -> list[bytes]:
        """图生图。"""

        del n
        image_url = self._bytes_to_data_url(image_bytes)
        response = await self._post_json(
            url=f"{self.base_url}/v1/images/generations",
            payload={
                "model": model,
                "prompt": prompt,
                "extra_body": {
                    "image": [image_url],
                    "response_format": "url",
                },
            },
        )
        return await self._extract_images(response)

    def _build_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    @staticmethod
    def _bytes_to_data_url(image_bytes: bytes) -> str:
        with PILImage.open(BytesIO(image_bytes)) as image:
            format_name = str(image.format or "PNG").upper()
        mime_map = {"JPEG": "image/jpeg", "JPG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}
        mime_type = mime_map.get(format_name, "image/png")
        encoded = base64.b64encode(image_bytes).decode("utf-8")
        return f"data:{mime_type};base64,{encoded}"

    async def _post_json(self, url: str, payload: dict[str, Any]) -> dict[str, Any]:
        start_time = time.time()
        timeout = aiohttp.ClientTimeout(total=self.request_timeout_seconds)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url, headers=self._build_headers(), json=payload) as response:
                duration = time.time() - start_time
                if response.status != 200:
                    error_text = await response.text()
                    self._log_error(
                        "Agnes 图片接口错误: status=%s duration=%.2fs url=%s response=%s",
                        response.status, duration, url, error_text[:1200],
                    )
                    raise RuntimeError(f"Agnes 图片接口错误 ({response.status}, 耗时: {duration:.2f}s): {error_text}")
                return await response.json()

    async def _extract_images(self, response: dict[str, Any]) -> list[bytes]:
        data = response.get("data")
        if not isinstance(data, list) or not data:
            raise RuntimeError(f"Agnes 图片接口未返回图片数据: {str(response)[:800]}")

        image_bytes_list: list[bytes] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            url = item.get("url")
            if isinstance(url, str) and url:
                image_bytes_list.append(await self._download_image(url))
                continue
            b64 = item.get("b64_json")
            if isinstance(b64, str) and b64:
                image_bytes_list.append(base64.b64decode(b64))
        if not image_bytes_list:
            raise RuntimeError("Agnes 图片接口返回数据中无可用图片")
        return image_bytes_list

    async def _download_image(self, url: str) -> bytes:
        timeout = aiohttp.ClientTimeout(total=self.request_timeout_seconds)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url) as response:
                if response.status != 200:
                    raise RuntimeError(f"下载 Agnes 生成图片失败: status={response.status}")
                return await response.read()

    def _log_info(self, message: str, *args: Any) -> None:
        if self.logger is not None:
            self.logger.info(message, *args)

    def _log_error(self, message: str, *args: Any) -> None:
        if self.logger is not None:
            self.logger.error(message, *args)


class AgnesVideo:
    """Agnes 视频生成接口封装。"""

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://apihub.agnes-ai.com",
        logger: Any | None = None,
        request_timeout_seconds: int = 900,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.logger = logger
        self.request_timeout_seconds = request_timeout_seconds

    async def create_video_task(
        self,
        prompt: str,
        model: str = "agnes-video-v2.0",
        *,
        image: str | list[str] | None = None,
        height: int = 768,
        width: int = 1152,
        num_frames: int = 121,
        frame_rate: int = 24,
        negative_prompt: str = "",
        seed: int | None = None,
        mode: str = "",
        extra_body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """创建视频任务。"""

        payload: dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "height": height,
            "width": width,
            "num_frames": num_frames,
            "frame_rate": frame_rate,
        }
        if negative_prompt:
            payload["negative_prompt"] = negative_prompt
        if seed is not None:
            payload["seed"] = seed

        if extra_body:
            payload["extra_body"] = extra_body
        elif image:
            payload["image"] = image
        if mode and "extra_body" not in payload:
            payload["extra_body"] = {"mode": mode}
        elif mode and "extra_body" in payload:
            payload["extra_body"]["mode"] = mode

        response = await self._post_json(f"{self.base_url}/v1/videos", payload)
        task_id = str(response.get("task_id") or response.get("id") or "").strip()
        if not task_id:
            raise RuntimeError(f"Agnes 视频任务未返回 task_id: {str(response)[:800]}")
        self._log_info("Agnes 视频任务已创建: task_id=%s model=%s", task_id, model)
        return response

    async def get_video_status(self, task_id: str) -> dict[str, Any]:
        """查询视频任务状态。"""

        url = f"{self.base_url}/v1/videos/{task_id}"
        timeout = aiohttp.ClientTimeout(total=60)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url, headers=self._build_headers()) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise RuntimeError(f"Agnes 视频状态查询失败 ({response.status}): {error_text}")
                return await response.json()

    async def poll_video_until_done(
        self,
        task_id: str,
        *,
        poll_interval: float = 12.0,
        timeout: float | None = None,
    ) -> str:
        """轮询视频任务直到完成，返回视频 URL。"""

        effective_timeout = timeout if timeout is not None else self.request_timeout_seconds
        start_time = time.monotonic()
        last_status = ""

        while True:
            elapsed = time.monotonic() - start_time
            if elapsed > effective_timeout:
                raise TimeoutError(f"Agnes 视频生成超时，已等待 {elapsed:.0f} 秒")

            try:
                result = await self.get_video_status(task_id)
            except Exception as poll_exc:
                self._log_error("Agnes 视频轮询异常: task_id=%s elapsed=%.0fs error=%s", task_id, elapsed, poll_exc)
                await asyncio.sleep(poll_interval)
                continue

            status = str(result.get("status") or "").strip()
            if status != last_status:
                self._log_info("Agnes 视频任务状态: task_id=%s status=%s progress=%s", task_id, status, result.get("progress"))
                last_status = status
            else:
                self._log_info("Agnes 视频轮询: task_id=%s status=%s elapsed=%.0fs", task_id, status, elapsed)

            if status == "completed":
                video_url = str(result.get("video_url") or result.get("remixed_from_video_id") or "").strip()
                if not video_url:
                    raise RuntimeError(f"Agnes 视频任务已完成但未返回 video_url: {str(result)[:800]}")
                return video_url
            if status == "failed":
                error_msg = result.get("error") or result.get("message") or "未知错误"
                raise RuntimeError(f"Agnes 视频任务失败: {error_msg}")

            await asyncio.sleep(poll_interval)

    def _build_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def _post_json(self, url: str, payload: dict[str, Any]) -> dict[str, Any]:
        start_time = time.time()
        timeout = aiohttp.ClientTimeout(total=120)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url, headers=self._build_headers(), json=payload) as response:
                duration = time.time() - start_time
                if response.status != 200:
                    error_text = await response.text()
                    self._log_error(
                        "Agnes 视频接口错误: status=%s duration=%.2fs url=%s response=%s",
                        response.status, duration, url, error_text[:1200],
                    )
                    raise RuntimeError(f"Agnes 视频接口错误 ({response.status}, 耗时: {duration:.2f}s): {error_text}")
                return await response.json()

    def _log_info(self, message: str, *args: Any) -> None:
        if self.logger is not None:
            self.logger.info(message, *args)

    def _log_error(self, message: str, *args: Any) -> None:
        if self.logger is not None:
            self.logger.error(message, *args)


import asyncio
