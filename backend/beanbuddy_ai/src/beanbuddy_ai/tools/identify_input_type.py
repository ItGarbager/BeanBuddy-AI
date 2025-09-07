import logging

import aiohttp
from nat.builder.builder import Builder
from nat.builder.framework_enum import LLMFrameworkEnum
from nat.builder.function_info import FunctionInfo
from nat.cli.register_workflow import register_function
from nat.data_models.component_ref import LLMRef
from nat.data_models.function import FunctionBaseConfig
from pydantic import Field

from ..models import InputType, IdentifyInputTypeInput, IdentifyInputTypeOutput

logger = logging.getLogger(__name__)


class IdentifyInputTypeConfig(FunctionBaseConfig, name="identify_input_type"):
    """
    A tool that analyzes user input, intelligently identifies its type (text description, entity name, or image), and returns a type identifier
    """
    # Add your custom configuration parameters here
    enable_advanced_text_analysis: bool = Field(
        default=True,
        description="是否启用高级文本分析（如LLM）来更准确地区分实体名称和文本描述"
    )
    llm_name: LLMRef = Field(description="The LLM to use for generating responses.")


@register_function(config_type=IdentifyInputTypeConfig, framework_wrappers=[LLMFrameworkEnum.LANGCHAIN])
async def identify_input_type_function(
        config: IdentifyInputTypeConfig, builder: Builder
):
    """
    输入识别与路由工具的主要函数
    严格遵循工作流规则：分析用户输入，智能识别其类型（文本描述、实体名称或图片）
    返回类型标识，由ReAct Agent根据结果进行路由决策
    """

    # Implement your function logic here
    async def _identify_input_type_function(input_data: IdentifyInputTypeInput) -> IdentifyInputTypeOutput:
        """
        核心识别逻辑

        Args:
            input_data: 包含用户输入信息

        Returns:
            IdentifyInputTypeOutput: 包含识别结果（input_type）和元数据（metadata）的模型对象
            Agent将根据input_type的值选择后续处理路径：
            - "text_description" -> enhance_description -> generate_image_from_text
            - "entity_name" -> query_knowledge_graph -> generate_image_from_text
            - "image" -> extract_subject -> ...
        """

        # 初始化metadata，合并用户传入的元数据
        raw_input = input_data.input_data

        try:
            if raw_input.startswith("http://") or raw_input.startswith("https://"):
                validate_content_type = await check_image_async(raw_input)
                if validate_content_type:
                    return IdentifyInputTypeOutput(input_data=input_data.input_data, input_type=InputType.IMAGE)

            # 2. 文本输入处理路径（包括字节解码为字符串）
            text_input = _extract_text_from_input(raw_input)

            # 3. 文本分类：区分实体名称 vs. 文本描述
            input_type = await _classify_text_input(
                text_input, config, builder
            )

            return IdentifyInputTypeOutput(
                input_data=text_input,
                input_type=input_type
            )

        except Exception as e:
            safe_text = str(raw_input) if not isinstance(raw_input, bytes) else "binary_data_input"
            logger.error(f"{safe_text}: 输入识别过程中发生错误: {str(e)}", exc_info=True)
            # 在出现错误时提供一个安全且符合格式的默认输出
            # 默认视为文本描述，由后续工具链处理

            return IdentifyInputTypeOutput(
                input_data=safe_text,
                input_type=InputType.TEXT_DESCRIPTION
            )

    try:
        yield FunctionInfo.from_fn(
            _identify_input_type_function,
            description="Return the type identifier recognized based on user input.")
    except GeneratorExit:
        logger.warning("Function exited early!")
    finally:
        logger.info("Cleaning up identify_input_type workflow.")


async def check_image_async(url):
    magic_numbers = {
        b'\xFF\xD8\xFF': 'JPEG',
        b'\x89PNG\r\n\x1a\n': 'PNG',
        b'GIF87a': 'GIF',
        b'GIF89a': 'GIF',
        b'RIFF': 'WEBP',
    }
    async with aiohttp.ClientSession() as session:
        async with session.head(url) as response:
            content_type = response.headers.get('Content-Type')
            if content_type.startswith('image/'):
                return True

            # 第二重校验：魔术数字（异步读取前4字节）
            header = await response.content.read(4)  # 异步读取操作
            for magic, img_type in magic_numbers.items():
                if header.startswith(magic):
                    return True

    return False


async def _analyze_image_input(image_data: bytes) -> str:
    """分析图像输入，返回图像类型、置信度和推理原因"""
    # 实现图像格式检测和简单内容分析
    # TODO 这里可以集成真正的CV模型或API

    # 魔术字节检测 (快速)
    image_signatures = {
        b'\xFF\xD8\xFF': 'JPEG',
        b'\x89PNG\r\n\x1a\n': 'PNG',
        b'GIF87a': 'GIF',
        b'GIF89a': 'GIF',
        b'RIFF': 'WEBP',
    }

    for signature, format_name in image_signatures.items():
        if image_data.startswith(signature):
            return format_name

    # 默认情况下，如果是字节数据但无法识别，仍给予中等置信度
    raise Exception("输入为字节数据，但无法识别具体图像格式")


def _extract_text_from_input(raw_input: str) -> str:
    """从输入数据中提取文本内容"""
    if isinstance(raw_input, bytes):
        try:
            return raw_input.decode('utf-8')
        except UnicodeDecodeError:
            # 如果无法解码为文本，很可能确实是图像数据
            raise ValueError("Input appears to be binary data that cannot be decoded as text")
    return raw_input


async def _classify_text_input(
        text_input: str,
        config: IdentifyInputTypeConfig,
        builder: Builder
) -> InputType:
    """
    对文本输入进行分类，区分实体名称和文本描述
    返回：(类型, 置信度, 推理原因)
    """
    text = text_input.strip()

    if config.enable_advanced_text_analysis:
        is_valid_entity = await _validate_entity(text, config, builder)
        if is_valid_entity:
            return InputType.ENTITY_NAME
        else:
            return InputType.TEXT_DESCRIPTION
    else:
        return InputType.ENTITY_NAME


async def _validate_entity(entity_name: str, config: IdentifyInputTypeConfig, builder: Builder) -> bool:
    """验证文本是否为有效的实体名称"""
    llm = await builder.get_llm(config.llm_name, wrapper_type=LLMFrameworkEnum.LANGCHAIN)
    # 构建精准的提示词
    prompt = f"""
    你是一个Q版拼豆设计顾问，负责判断用户提供的名称是否适合作为拼豆设计的主题。
    你的任务是分析“{entity_name}”这个名称，判断它是否是一个明确的、具象的实体，并且适合转换为可爱的Q版卡通风格拼豆设计。

    ### 判断标准：
    1.  **有效性**：该名称是否指代一个**具体的、众所周知的实体**（如卡通角色、动物、植物、日常物品、食品等）。
        *   ✅ 有效例子：皮卡丘、小猫、圣诞树、咖啡杯、汉堡
        *   ❌ 无效例子：爱情、悲伤、哲学、运行的代码、模糊的概念（过于抽象或非具象）
    2.  **适宜性**：该实体是否**适合制作成可爱、有趣的Q版拼豆造型**。
        *   ✅ 适宜例子：龙、机器人、蛋糕（特征明显，易于表现）
        *   ❌ 不适宜例子：一片模糊的云、一股烟雾（形状不固定，难以用拼豆表现）
    3.  **明确性**：该名称是否**没有严重的歧义**，能够让人立刻联想到一个明确的形象。
        *   ✅ 明确例子："米老鼠"（特指迪士尼角色）
        *   ❌ 歧义例子："苹果"（可能指水果，也可能指公司）

    ### 请根据以上标准进行判断。
    如果该名称是**有效、适宜且明确**的实体，请只回答“是”。
    如果该名称**不符合**上述标准（过于抽象、不适宜制作、歧义严重），请只回答“否”。

    无需解释原因，只需输出“是”或“否”。

    需要判断的名称：{entity_name}
    """
    # 3. 调用LLM并获取响应
    try:
        response = await llm.ainvoke(prompt)
        # 4. 清理和解析响应，去除可能的首尾空格或换行，进行小写比较以确保鲁棒性
        return response.content == "是"
    except Exception as e:
        # 5. 异常处理：如果LLM调用失败，记录错误并默认返回False，避免阻塞主流程
        logger.error(f"在验证实体 '{entity_name}' 时调用LLM失败: {str(e)}")
        return False
