from typing import Any, Literal, Protocol

from ..providers.agnes_platform import AgnesImage, AgnesVideo
from ..providers.openai_platform import OpenaiImage
from .config import DrawpicConfig, OpenAICompatibilityMode


class ImageProvider(Protocol):
    def generate_images(self, prompt: str, model: str, n: int = 1) -> list[bytes]:
        """根据文本提示生成图片。"""

    def edit_images(self, prompt: str, model: str, image_bytes: bytes, n: int = 1) -> list[bytes]:
        """基于输入图片执行编辑。"""


class ProviderRouter:
    """负责模型归属判断与 Provider 创建。"""

    def __init__(self, config: DrawpicConfig, logger: Any | None = None):
        self.config = config
        self.logger = logger

    def get_openai_models(self) -> list[str]:
        """获取 OpenAI 模型列表。"""

        return [model.strip() for model in self.config.openai.models if model.strip()]

    def get_agnes_image_models(self) -> list[str]:
        """获取 Agnes 图片模型列表。"""

        return [model.strip() for model in self.config.agnes.image_models if model.strip()]

    def get_agnes_video_models(self) -> list[str]:
        """获取 Agnes 视频模型列表。"""

        return [model.strip() for model in self.config.agnes.video_models if model.strip()]

    def get_all_image_models(self) -> list[str]:
        """获取全部可用图片模型列表。"""

        return self.get_openai_models() + self.get_agnes_image_models()

    def get_all_models(self) -> list[str]:
        """获取全部可用模型列表（图片+视频）。"""

        return self.get_all_image_models() + self.get_agnes_video_models()

    def get_model_provider(self, model: str) -> Literal["openai", "agnes_image", "agnes_video", ""]:
        """根据模型名称判断其所属提供商。"""

        normalized_model = model.strip()
        if normalized_model in self.get_openai_models():
            return "openai"
        if normalized_model in self.get_agnes_image_models():
            return "agnes_image"
        if normalized_model in self.get_agnes_video_models():
            return "agnes_video"
        return ""

    def is_video_model(self, model: str) -> bool:
        """判断模型是否为视频模型。"""

        return self.get_model_provider(model) == "agnes_video"

    def resolve_default_model(self) -> str:
        """解析当前有效的默认图片模型。"""

        configured_default = self.config.general.default_model.strip()
        if self.get_model_provider(configured_default) in {"openai", "agnes_image"}:
            return configured_default

        all_image_models = self.get_all_image_models()
        if all_image_models:
            return all_image_models[0]
        raise ValueError("当前未配置任何可用图片模型")

    def resolve_default_video_model(self) -> str:
        """解析当前有效的默认视频模型。"""

        video_models = self.get_agnes_video_models()
        if video_models:
            return video_models[0]
        raise ValueError("当前未配置任何可用视频模型")

    def resolve_openai_compatibility_mode(self, mode: str = "") -> OpenAICompatibilityMode:
        """解析最终使用的 OpenAI 兼容模式。"""

        normalized_mode = mode.strip()
        if normalized_mode in {"auto", "images_api", "chat_completions", "novelai_images_api"}:
            return normalized_mode  # type: ignore[return-value]

        default_mode = self.config.openai.default_openai_compatibility_mode
        if default_mode in {"auto", "images_api", "chat_completions", "novelai_images_api"}:
            return default_mode
        return "auto"

    def resolve_request_timeout_seconds(self) -> int:
        """解析最终使用的请求超时时间。"""

        timeout_seconds = int(self.config.general.request_timeout_seconds)
        if timeout_seconds < 5:
            return 5
        if timeout_seconds > 600:
            return 600
        return timeout_seconds

    def should_rewrite_prompt_to_english(self, provider_name: str) -> bool:
        """判断指定提供商是否需要先把提示词改写为英文。"""

        normalized_provider = provider_name.strip().lower()
        if normalized_provider == "openai":
            return self.config.openai.rewrite_prompt_to_english
        return False

    def resolve_model_name(self, model: str = "", allow_unknown_model: bool = False) -> str:
        """解析最终使用的模型名。"""

        normalized_model = model.strip()
        if normalized_model and self.get_model_provider(normalized_model) in {"openai", "agnes_image"}:
            return normalized_model
        if normalized_model and allow_unknown_model:
            return normalized_model
        return self.resolve_default_model()

    def resolve_video_model_name(self, model: str = "") -> str:
        """解析最终使用的视频模型名。"""

        normalized_model = model.strip()
        if normalized_model and self.get_model_provider(normalized_model) == "agnes_video":
            return normalized_model
        return self.resolve_default_video_model()

    def create_openai_provider(self, compatibility_mode: OpenAICompatibilityMode) -> OpenaiImage:
        """创建 OpenAI 图片提供商实例。"""

        return OpenaiImage(
            api_key=self.config.openai.api_key,
            base_url=self.config.openai.base_url,
            compatibility_mode=compatibility_mode,
            logger=self.logger,
            request_timeout_seconds=self.resolve_request_timeout_seconds(),
        )

    def supports_image_edit(self, model: str) -> bool:
        """判断模型是否支持图生图编辑。"""

        provider = self.get_model_provider(model)
        return provider in {"openai", "agnes_image"}

    def create_agnes_image_provider(self) -> AgnesImage:
        """创建 Agnes 图片提供商实例。"""

        return AgnesImage(
            api_key=self.config.agnes.api_key,
            base_url=self.config.agnes.base_url,
            logger=self.logger,
            request_timeout_seconds=self.resolve_request_timeout_seconds(),
        )

    def create_agnes_video_provider(self) -> AgnesVideo:
        """创建 Agnes 视频提供商实例。"""

        return AgnesVideo(
            api_key=self.config.agnes.api_key,
            base_url=self.config.agnes.base_url,
            logger=self.logger,
            request_timeout_seconds=self.config.agnes.video_request_timeout_seconds,
        )

    def require_platform_for_model(
        self,
        model: str,
        openai_compatibility_mode: str = "",
    ) -> tuple[ImageProvider, Literal["openai", "agnes_image"]]:
        """根据模型解析并创建对应的图片平台实例。"""

        provider_type = self.get_model_provider(model)
        if provider_type == "openai":
            return self.create_openai_provider(
                self.resolve_openai_compatibility_mode(openai_compatibility_mode)
            ), "openai"
        if provider_type == "agnes_image":
            return self.create_agnes_image_provider(), "agnes_image"
        raise RuntimeError(f"模型未归属于任何已配置图片提供商：{model}")
