import logging

from nat.builder.builder import Builder
from nat.builder.framework_enum import LLMFrameworkEnum
from nat.builder.function_info import FunctionInfo
from nat.cli.register_workflow import register_function
from nat.data_models.component_ref import LLMRef
from nat.data_models.function import FunctionBaseConfig
from pydantic import Field

from ..models import QueryKnowledgeGraphInput, QueryKnowledgeGraphOutput

logger = logging.getLogger(__name__)


class QueryKnowledgeGraphConfig(FunctionBaseConfig, name="query_knowledge_graph"):
    """
    A tool for querying the knowledge graph to obtain entity features
    """
    # Add your custom configuration parameters here
    llm_name: LLMRef = Field(description="The LLM to use for generating responses.")


@register_function(config_type=QueryKnowledgeGraphConfig, framework_wrappers=[LLMFrameworkEnum.LANGCHAIN])
async def query_knowledge_graph_function(
        config: QueryKnowledgeGraphConfig, builder: Builder
):
    """
    查询知识图谱获取文生图描述文本的主要函数
    严格遵循工作流规则：根据用户输入的主体名称，返回文本增强后的主体特征
    返回类型标识，由ReAct Agent根据结果进行路由决策
    """

    async def _query_knowledge_graph_function(input_data: QueryKnowledgeGraphInput) -> QueryKnowledgeGraphOutput:

        try:
            subject_name = input_data.input_data.strip()
            # 根据主体名称获取的增强后的主体特征
            entity_features = await _generate_entity_features(subject_name, config, builder)
            processed_text = ("一个可爱的Q版{%s}形象\n"
                              f"1.  **主体**：{entity_features.replace('\n', '; ')}，排除背景杂物。\n"
                              "2.  **风格**：卡通渲染，色彩明亮且区块化，线条简洁清晰，适合作为拼豆设计蓝图。\n"
                              "3.  **背景**：**纯白背景**（Pure transparent background），颜色为#FFFFFF。\n"
                              "4.  **细节**：无阴影，无复杂纹理，整体设计易于识别和制作。\n"
                              "5.  **画面**：主体居中，完整展现全身或上半身特写。\n"
                              "6.  **输出**：请生成PNG格式的图片。\n"
                              "补充：\n"
                              "- 完整保留主体轮廓细节（包括毛发、透明材质、细小装饰的边缘），彻底移除所有背景元素\n"
                              "- 确保主体无残缺、边缘无白边/杂色，尺寸与原图主体比例一致。")
            return QueryKnowledgeGraphOutput(input_data=processed_text)

        except Exception as e:
            logger.error(f"描述增强过程中发生错误: {str(e)}", exc_info=True)
            # 在出现错误时提供一个安全且符合格式的默认输出
            # 默认视为文本描述，由后续工具链处理
            safe_text = str(input_data.input_data) if not isinstance(input_data.input_data,
                                                                     bytes) else "binary_data_input"

            return QueryKnowledgeGraphOutput(
                input_data=safe_text
            )

    try:
        yield FunctionInfo.from_fn(
            _query_knowledge_graph_function,
            description="Return the entity features obtained from querying the knowledge graph.")
    except GeneratorExit:
        logger.warning("Function exited early!")
    finally:
        logger.info("Cleaning up query_knowledge_graph workflow.")


async def _generate_entity_features(subject_name: str, config: QueryKnowledgeGraphConfig, builder: Builder) -> str:
    prompt = f"""
    你是一个专业的角色形象设计助手，擅长根据简单的主体名称，生成丰富、具体且富有表现力的特征描述。

    # 任务定义
    请根据用户提供的主体名称，自动扩展其详细的特征描述。描述需涵盖外观、表情、姿态、服饰等关键方面，并遵循指定的格式要求。

    # 输出格式要求
    你必须严格按照以下格式输出扩展后的特征描述，确保内容清晰、具体，且包含生动的细节：
    [详细描述主体的外观、表情、姿态、服饰等，例如：圆脸，大眼睛，开心的笑容，穿着[具体服饰]，做着[某个动作]]

    # 指令与约束
    1.  **描述具体化**：避免使用模糊词汇。使用具体的颜色、形状、材质、光影进行描述，例如用“亮红色的丝绸长裙”代替“漂亮的衣服”[6](@ref)。
    2.  **细节丰富**：尽可能添加生动的细节，如“扎着双马尾，发梢微微卷曲”、“腰间别着一把精致的短剑”。
    3.  **符合逻辑**：确保描述的特征与主体名称的身份、常见设定或文化背景相符。
    4.  **语言简洁**：在保证细节的前提下，语言应简洁明了，避免冗长和不必要的重复。
    5.  **仅输出要求内容**：不要输出任何任务定义、指令或格式要求本身，仅生成符合上述格式的特征描述文本。

    # 示例参考 (用于引导模型)
    *   **输入主体名称**： `皮卡丘`
    *   **期望输出**： `[电气鼠宝可梦，圆润的脸颊上有两个红色的电气袋，亮黄色皮毛，黑色尖耳朵，炯炯有神的大眼睛带着好奇和友善的表情，短小的四肢，经常站立着，尾巴呈闪电形状，身体偶尔会迸发出细小的电火花]`
    *   **输入主体名称**： `武林高手`
    *   **期望输出**： `[身形矫健，目光如炬，沉稳内敛的表情，身着藏青色粗布武服，腰束黑色缎带，脚踩千层底布鞋，手持一柄古朴长剑，正在晨雾中练习剑法，动作行云流水]`

    # 处理流程
    现在，请根据用户输入的主体名称，生成相应的详细特征描述。
    用户输入：“{subject_name}”
    """
    # 3. 调用LLM并获取响应
    try:
        llm = await builder.get_llm(config.llm_name, wrapper_type=LLMFrameworkEnum.LANGCHAIN)
        response = await llm.ainvoke(prompt)
        # 4. 清理和解析响应，去除可能的首尾空格或换行，进行小写比较以确保鲁棒性
        return response.content
    except Exception as e:
        # 5. 异常处理：如果LLM调用失败，记录错误并默认返回False，避免阻塞主流程
        logger.error(f"在验证实体 '{subject_name}' 时调用LLM失败: {str(e)}")
        return subject_name
