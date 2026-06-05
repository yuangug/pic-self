from __future__ import annotations

from .provider_router import ProviderRouter
from .task_store import DrawTaskRecord


def build_command_usage_text() -> str:
    """构建基础命令用法文本。"""

    return "\n".join(
        [
            "可用子命令",
            "/绘图 模型",
            "查看当前模型与可用模型；后接模型名可切换。",
            "",
            "/绘图 状态",
            "查看当前会话模型、兼容模式、额度与绘图任务。",
            "",
            "/绘图 兼容模式",
            "查看或设置 OpenAI 兼容模式，仅对 OpenAI 提供商生效。",
            "",
            "/绘图 绘制 <prompt>",
            "发起文生图，prompt 可包含空格。",
            "",
            "/绘图 改图 <prompt>",
            "引用图片后执行，使用 Agnes 模型进行图生图编辑。",
            "",
            "/绘图 视频 <prompt>",
            "发起视频生成，可引用图片作为首帧。",
            "",
            "/绘图 添加/减少/设置 用户ID 次数",
            "管理员调整用户当前周期剩余绘图次数。",
        ]
    )


def build_model_text(router: ProviderRouter, session_preference: dict[str, str]) -> str:
    """构建模型列表文本。"""

    current_model = session_preference["model"] or router.resolve_default_model()
    current_provider = router.get_model_provider(current_model) or "unknown"
    provider_lines = [
        ("OpenAI", router.get_openai_models()),
        ("Agnes 图片", router.get_agnes_image_models()),
        ("Agnes 视频", router.get_agnes_video_models()),
    ]
    lines = [
        f"当前使用模型：{current_provider}：{current_model}",
        "后接模型名称即可切换当前会话模型。",
        "",
    ]
    for provider_name, models in provider_lines:
        models_text = "，".join(models) if models else "未配置"
        lines.append(f"{provider_name}：{models_text}")
    return "\n".join(lines)


def build_session_status_text(
    router: ProviderRouter,
    session_preference: dict[str, str],
    latest_task: DrawTaskRecord | None,
    *,
    quota_text: str,
) -> str:
    """构建当前会话的绘图状态文本。"""

    model_name = session_preference["model"] or router.resolve_default_model()
    provider_name = router.get_model_provider(model_name) or "unknown"
    lock_status = "已锁定" if session_preference["model"] else "未锁定，跟随默认模型"
    task_text = _format_task(latest_task)
    default_video_model = ""
    try:
        default_video_model = router.resolve_default_video_model()
    except ValueError:
        default_video_model = "未配置"
    return "\n".join(
        [
            f"当前绘图模型：{provider_name}：{model_name}",
            f"会话模型状态：{lock_status}",
            f"OpenAI 兼容模式：{session_preference['openai_compatibility_mode']}",
            f"默认图片模型：{router.resolve_default_model()}",
            f"默认视频模型：{default_video_model}",
            f"当前任务：{task_text}",
            f"用户次数：{quota_text}",
        ]
    )


def build_compatible_mode_text(current_mode: str) -> str:
    """构建兼容模式说明。"""

    return "\n".join(
        [
            f"当前 OpenAI 兼容模式：{current_mode}",
            "该设置仅对 OpenAI 提供商生效。",
            "",
            "可选模式：",
            "auto：自动选择，推荐默认使用",
            "images_api：OpenAI 标准 Images API",
            "chat_completions：Chat Completion 返回图片",
            "novelai_images_api：NovelAI 风格图片接口",
            "",
            "示例：/绘图 兼容模式 images_api",
        ]
    )


def build_quota_adjust_text(action_label: str, user_id: str, remaining: int) -> str:
    """构建次数调整结果文本。"""

    return f"已{action_label}用户 {user_id} 的当前周期剩余绘图次数。\n当前剩余：{remaining} 次"


def _format_task(record: DrawTaskRecord | None) -> str:
    if record is None:
        return "无"
    status_map: dict[str, str] = {
        "pending": "等待中",
        "running": "进行中",
        "completed": "已完成",
        "failed": "失败",
        "rejected": "审核拦截",
    }
    status_text = status_map.get(record.status, record.status)
    type_map: dict[str, str] = {
        "draw": "文生图",
        "edit_image": "图生图",
        "video": "视频",
    }
    type_text = type_map.get(record.task_type, record.task_type)
    progress_text = ""
    if record.task_type == "video" and record.progress is not None:
        progress_text = f"，进度={record.progress}%"
    return f"{type_text}，{status_text}，task_id={record.task_id}，模型={record.model}{progress_text}，更新时间={record.updated_at:%m-%d %H:%M}"
