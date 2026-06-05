# PicVideoDraw

为 MaiBot 提供图片生成、图片编辑和视频生成能力。插件支持 OpenAI 兼容图片接口和 Agnes 多模态模型，支持命令调用和 LLM 工具调用。

## 功能特性

- **文生图与图生图**：根据提示词生成图片，也可以基于聊天中的图片继续编辑。
- **文生视频与图生视频**：根据提示词生成视频，支持引用聊天中的图片作为视频首帧。
- **多平台模型**：支持 OpenAI Images API、OpenAI Chat Completion 兼容、NovelAI 风格接口、Agnes Image 2.1 Flash 和 Agnes Video V2.0。
- **会话偏好**：群聊和私聊可分别保存模型与 OpenAI 兼容模式；新会话默认跟随全局默认模型。
- **后台任务**：绘图和视频生成不阻塞聊天流程，完成后自动发送结果，可通过状态命令或工具查询任务。
- **LLM 工具调用**：向 MaiBot 暴露 `draw`、`edit_image`、`generate_video`、`draw_status`，由 LLM 在合适场景自主调用。
- **英文提示词改写**：可在调用 OpenAI 兼容接口前，使用 MaiBot 的 `replyer` 模型把非英文提示词改写为英文。
- **审核与额度**：可选启用提示词审核、图片审核、管理员权限和用户绘图次数管理。
- **配置热更新**：订阅 `bot` / `model` 配置重载事件，主体配置更新后插件会刷新内部服务。

## 安装

在 MaiBot 的 `plugins` 目录中克隆本仓库：

```bash
cd plugins
git clone https://github.com/WhiteCloudOL/maimai-drawpic-plugin
```

在 MaiBot 主项目环境中安装依赖：

```bash
pip install -r plugins/maimai-drawpic-plugin/requirements.txt
```

使用 `uv` 时可执行：

```bash
uv pip install -r plugins/maimai-drawpic-plugin/requirements.txt
```

重启 MaiBot 后插件生效。首次加载会在插件目录生成本地 `config.toml`。

运行依赖：`aiohttp`、`pillow`。

## 配置

插件首次加载时会自动生成默认配置文件 `config.toml`。所有配置项均可通过 MaiBot 插件管理界面修改，无需手动编辑文件。

常用配置项说明：

| 配置段 | 字段 | 含义 |
| :--- | :--- | :--- |
| `[plugin]` | `enabled` | 是否启用插件 |
| `[plugin]` | `config_version` | 配置版本号，用于插件自身的配置迁移，请勿随意修改 |
| `[general]` | `default_model` | 默认图片模型名，插件会在 OpenAI 和 Agnes 图片模型列表中查找归属 |
| `[general]` | `request_timeout_seconds` | 单次图片请求超时时间（秒），取值会被夹紧到 `[5, 600]` 区间 |
| `[general]` | `command_reply_mode` | 聊天命令返回形式，可选 `图片` / `文本`，默认 `图片` |
| `[general]` | `permission_enabled` / `admin_user_ids` | 权限管理开关与插件管理员用户 ID 列表 |
| `[general]` | `quota_enabled` / `quota_period` / `default_quota` | 用户绘图次数管理开关、周期与默认可用次数 |
| `[general]` | `napcat_api_url` | NapCat HTTP API 地址，用于通过 `/get_image` 接口获取 QQ 图片 URL 或 base64，格式如 `http://127.0.0.1:3000` |
| `[openai]` | `base_url` / `api_key` / `models` | OpenAI 或 OpenAI 兼容服务的基础 URL、密钥与模型列表 |
| `[openai]` | `default_openai_compatibility_mode` | 默认 OpenAI 兼容模式，支持 `auto` / `images_api` / `chat_completions` / `novelai_images_api` |
| `[openai]` | `rewrite_prompt_to_english` | 调用 OpenAI 兼容接口前是否先使用 MaiBot `replyer` 模型改写为英文提示词 |
| `[agnes]` | `base_url` / `api_key` | Agnes AI 服务的基础 URL 和 API 密钥 |
| `[agnes]` | `image_models` | Agnes 图片模型列表，支持文生图与图生图 |
| `[agnes]` | `video_models` | Agnes 视频模型列表，支持文生视频与图生视频 |
| `[agnes]` | `video_request_timeout_seconds` | 视频生成超时时间（秒），建议 300 ~ 1800 |
| `[agnes]` | `default_video_width` / `default_video_height` | 视频默认分辨率 |
| `[agnes]` | `default_video_num_frames` / `default_video_frame_rate` | 视频默认帧数与帧率 |
| `[prompt_review]` | `enabled` / `review_prompt` | 是否启用提示词审核以及审核提示模板（支持 `{user_prompt}` 占位符） |
| `[image_review]` | `enabled` / `review_prompt` | 是否启用生成图片审核以及审核提示模板（支持 `{user_prompt}` 占位符） |

## OpenAI 兼容模式

`openai.default_openai_compatibility_mode` 以及 `/绘图 兼容模式 <模式>` 支持下列取值：

| 模式 | 说明 |
| :--- | :--- |
| `auto` | 由插件根据模型与上游接口能力自动选择，推荐默认使用 |
| `images_api` | 使用 OpenAI 标准的 `/v1/images/generations` 与 `/v1/images/edits` 接口 |
| `chat_completions` | 使用 Chat Completion 接口返回图片，适合部分中转或自部署网关 |
| `novelai_images_api` | 适配 NovelAI 风格的图片生成接口 |

## Agnes 模型

### Agnes Image 2.1 Flash
- 文生图：根据提示词生成高质量图像
- 图生图：基于聊天中的图片进行编辑，保持构图的同时转换风格

### Agnes Video V2.0
- 文生视频：根据提示词生成电影级视频
- 图生视频：将聊天中的图片动画化为视频，支持引用图片或发送图片后执行命令
- 视频参数：可通过配置调整分辨率、帧数、帧率

## 命令

使用 `/绘图` 管理当前会话的绘图模型、兼容模式、额度和任务：

| 命令 | 说明 |
| :--- | :--- |
| `/绘图` | 查看各个子命令用法 |
| `/绘图 模型` | 查看当前使用模型与各提供商可用模型 |
| `/绘图 模型 <模型名>` | 将当前会话切换到指定绘图模型，启用权限管理时仅管理员可用 |
| `/绘图 状态` | 查看当前会话模型、兼容模式、当前任务与用户剩余次数 |
| `/绘图 兼容模式` | 查看 OpenAI 兼容模式说明 |
| `/绘图 兼容模式 <模式>` | 设置 OpenAI 兼容模式，仅对 OpenAI 提供商生效 |
| `/绘图 绘制 <prompt>` | 发起文生图，`prompt` 可包含空格 |
| `/绘图 改图 <prompt>` | 引用图片后执行，使用 Agnes 模型进行图生图编辑 |
| `/绘图 视频 <prompt>` | 发起视频生成，可引用图片作为首帧 |
| `/绘图 添加/减少/设置 用户ID 次数` | 管理员调整用户当前周期剩余次数 |

## LLM 工具

插件向大语言模型暴露以下工具：

| 工具名 | 作用 |
| :--- | :--- |
| `draw` | 根据提示词生成新图片，结果以异步后台任务形式回传到当前聊天流 |
| `edit_image` | 编辑当前聊天中的最近一张图片，或编辑指定 `source_message_id` / `source_image_base64` 对应的图片 |
| `generate_video` | 根据提示词和可选的源图片生成视频，支持引用聊天中的图片作为首帧 |
| `draw_status` | 查询当前会话最近一个后台任务，或按 `task_id` 查询指定任务的状态 |

共通可选参数：

- `model`：本次调用使用的模型名。图片任务不填则跟随默认图片模型；视频任务不填则跟随默认视频模型。
- `user_id` / `group_id` / `platform`：用于在回传结果时定位真实聊天流，默认 `platform = qq`。

## 目录结构

```text
plugins/maimai-drawpic-plugin/
├── _manifest.json
├── plugin.py
├── requirements.txt
├── config.toml
├── assets/
│   └── font.ttf
├── data/
│   ├── session_preferences.json
│   ├── draw_tasks.json
│   └── user_quotas.json
├── core/
│   ├── config.py
│   ├── draw_service.py
│   ├── image_reply.py
│   ├── message_utils.py
│   ├── moderation.py
│   ├── provider_router.py
│   ├── session_preferences.py
│   ├── stream_service.py
│   ├── task_store.py
│   ├── texts.py
│   └── usage_store.py
└── providers/
    ├── openai_platform.py
    └── agnes_platform.py
```

## 许可证

本项目遵循 [AGPL-3.0 许可证](LICENSE) 开源。
