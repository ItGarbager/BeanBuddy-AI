import asyncio
import functools
import json
import logging
import os

from nat.builder.builder import Builder
from nat.builder.function_info import FunctionInfo
from nat.cli.register_workflow import register_function
from nat.data_models.function import FunctionBaseConfig
from pydantic import Field

from ..models import ExtractSubjectInput, ExtractSubjectOutput

# 检查 dashscope 依赖，缺失则提示安装
try:
    from dashscope import MultiModalConversation
except ImportError:
    raise ImportError(
        "ExtractSubjectTool 依赖 'dashscope' 包，请执行安装：\n"
        "pip install dashscope"
    )

# 初始化日志（遵循框架日志规范）
logger = logging.getLogger(__name__)


class ExtractSubjectConfig(FunctionBaseConfig, name="extract_subject"):
    """
    图片主体提取工具配置类（基于阿里云通义千问-图片编辑API）
    核心功能：抠图、移除背景、保留主体细节，生成透明背景PNG
    """

    # 图片处理指令（可自定义，默认满足Q版拼豆主体提取需求）
    text_instruction: str = Field(
        default="将图片转为可爱的Q版风格\n"
                f"1. **识别**: 自动识别图片中的核心形象主体（如人物、动物、物体），排除背景杂物；\n"
                "2.  **风格**：卡通渲染，色彩明亮且区块化，线条简洁清晰，适合作为拼豆设计蓝图。\n"
                "3.  **背景**：**纯白背景**（Pure transparent background）。\n"
                "4.  **细节**：无阴影，无复杂纹理，整体设计易于识别和制作。\n"
                "5.  **画面**：主体居中，完整展现全身或上半身特写。\n"
                "6.  **输出**：请生成PNG格式的图片，以确保背景透明。\n\n"
                "补充：\n"
                "- 完整保留主体轮廓细节（包括毛发、透明材质、细小装饰的边缘），彻底移除所有背景元素\n"
                "- 确保主体无残缺、边缘无白边/杂色，尺寸与原图主体比例一致。",
        description="图片主体提取的具体指令，可根据需求调整（如强调保留特定细节）。"
    )

    # 3. API调用超时时间（单位：秒）
    timeout: int = Field(
        default=30,
        description="Qwen-Image-Edit API调用的超时时间，默认30秒。"
    )


@register_function(config_type=ExtractSubjectConfig)
async def extract_subject_function(
        config: ExtractSubjectConfig, builder: Builder
):
    """
    图片主体提取工具实现（nemo-agent函数注册入口）
    功能：接收图片URL，调用通义千问API提取主体，返回处理后的透明背景图片URL
    """
    logger.info("开始初始化 ExtractSubject 工具（基于Qwen-Image-Edit）")

    # --------------------------
    # 1. 初始化配置（API密钥校验）
    # --------------------------
    # 优先级：工具配置内的api_key > 环境变量DASHSCOPE_API_KEY
    dashscope_api_key = builder.get_llm_config("default_llm").__dict__.get("api_key") or os.getenv("DASHSCOPE_API_KEY")
    if not dashscope_api_key:
        error_msg = (
            "ExtractSubject工具初始化失败：未找到DashScope API密钥！\n"
            "解决方案：\n"
            "1. 在config.yml的 'default_llm' 函数配置中添加 'api_key' 字段；\n"
            "2. 或设置系统环境变量 'DASHSCOPE_API_KEY'。"
        )
        logger.error(error_msg)
        raise ValueError(error_msg)

    # 提取配置参数
    extraction_instruction = config.text_instruction
    api_timeout = config.timeout
    logger.debug(f"工具配置完成：\n"
                 f"- 超时时间：{api_timeout}秒\n"
                 f"- 处理指令：{extraction_instruction[:80]}...")  # 截断日志避免过长

    # --------------------------
    # 2. 核心工具函数（异步实现）
    # --------------------------
    async def _extract_subject(input_data: ExtractSubjectInput) -> ExtractSubjectOutput:
        """
        工具核心逻辑（nemo-agent实际调用的函数）
        Args:
            input_data: 用户的原始输入内容：文本字符串
        Returns:
            成功：处理后的主体图片URL（透明背景PNG）
            失败：带错误信息的字符串（便于agent后续处理）
        """

        try:
            image_url = input_data.input_data
            logger.info(f"开始处理图片：{image_url}")

            # 第一步：校验输入URL合法性
            if not image_url.startswith(("http://", "https://")):
                e = f"无效图片URL：{image_url}（必须是公网HTTP/HTTPS链接）"
                raise Exception(e)

            # 第二步：构建通义千问API请求
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"image": image_url},  # 原始图片URL
                        {"text": extraction_instruction}  # 处理指令
                    ]
                }
            ]
            # 第三步：异步调用API（用线程避免阻塞事件循环）
            logger.debug("正在调用Qwen-Image-Edit API...")
            # 预先绑定参数
            sync_call = functools.partial(
                MultiModalConversation.call,
                api_key=dashscope_api_key,
                model="qwen-image-edit",  # 固定使用图片编辑模型
                messages=messages,
                result_format="message",  # 结构化返回格式
                stream=False,  # 非流式返回
                watermark=False,  # 启用水印（可选关闭）
                negative_prompt="背景残留、主体残缺、边缘白边、非PNG格式",  # 负向提示
                timeout=api_timeout  # 超时控制
            )

            # 用asyncio.to_thread包装同步API调用，避免阻塞agent事件循环
            response = await asyncio.to_thread(sync_call)

        # 捕获API调用异常（网络错误、超时等）
        except asyncio.TimeoutError:
            e = f"API调用超时（超过{api_timeout}秒），请检查图片URL有效性或延长超时时间"

            logger.exception(e)
            return ExtractSubjectOutput(input_data=e)
        except Exception as e:
            e = f"API调用异常：{str(e)}（请检查API密钥有效性或网络连接）"
            logger.exception(e)
            return ExtractSubjectOutput(input_data=e)

        # 第四步：解析API响应（提取处理后的图片URL）
        try:
            # 将DashScope响应对象转为JSON可解析格式
            response_data = json.loads(json.dumps(response, ensure_ascii=False))

            # 按API返回结构提取图片URL（通义千问标准格式）
            output_content = response_data.get("output", {}).get("choices", [{}])[0]
            message_content = output_content.get("message", {}).get("content", [])

            # 遍历内容找到图片URL
            processed_url = None
            for item in message_content:
                if isinstance(item, dict) and "image" in item:
                    processed_url = item["image"]
                    break

            # 校验提取结果
            if not processed_url:
                e = "API响应解析失败：未找到处理后的图片URL（响应结构异常）"
                logger.error(f"{e}\n原始响应：{json.dumps(response_data, indent=2)}")
                return ExtractSubjectOutput(input_data=e)

            # 成功返回URL
            logger.info(f"图片主体提取成功！处理后URL：{processed_url}")
            return ExtractSubjectOutput(input_data=processed_url)

        except Exception as e:
            e = f"响应解析异常：{str(e)}"
            logger.exception(f"{e}\n原始响应：{json.dumps(response, indent=2)}")
            return ExtractSubjectOutput(input_data=e)

    # --------------------------
    # 3. 注册工具到Nemo-Agent
    # --------------------------
    try:
        yield FunctionInfo.from_fn(
            _extract_subject,
            description=(
                "【图片主体提取工具】适用于BeanBuddy-AI的图片输入路径：\n"
                "1. 输入：公网可访问的原始图片HTTP/HTTPS URL（如用户上传图片的临时链接）；\n"
                "2. 处理：调用Qwen-Image-Edit API自动抠图、移除背景、保留主体细节；\n"
                "3. 输出：处理后的图片URL（PNG-24格式，含透明背景，可直接用于后续Q版风格化）。\n"
                "⚠️  必须在用户输入为图片时优先调用（遵循 workflow 中 '图片输入路径' 规则）。"
            ),
        )
    except GeneratorExit:
        logger.warning("ExtractSubject工具生成器提前退出，正在清理资源...")
    finally:
        logger.info("ExtractSubject工具初始化流程结束（或已完成资源清理）")
