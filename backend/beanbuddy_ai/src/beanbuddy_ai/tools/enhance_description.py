import logging

from nat.builder.builder import Builder
from nat.builder.framework_enum import LLMFrameworkEnum
from nat.builder.function_info import FunctionInfo
from nat.cli.register_workflow import register_function
from nat.data_models.component_ref import LLMRef
from nat.data_models.function import FunctionBaseConfig
from pydantic import Field

from ..models import EnhanceDescriptionInput, EnhanceDescriptionOutput

logger = logging.getLogger(__name__)


class EnhanceDescriptionConfig(FunctionBaseConfig, name="enhance_description"):
    """
    A tool for generating a rich description of the bean-spelling design based on a short text
    """
    # Add your custom configuration parameters here
    llm_name: LLMRef = Field(description="The LLM to use for generating responses.")


@register_function(config_type=EnhanceDescriptionConfig, framework_wrappers=[LLMFrameworkEnum.LANGCHAIN])
async def enhance_description_function(
        config: EnhanceDescriptionConfig, builder: Builder
):
    # Implement your function logic here
    async def _enhance_description_function(input_data: EnhanceDescriptionInput) -> EnhanceDescriptionOutput:
        try:
            description = input_data.input_data.strip()
            # 根据主体名称获取的增强后的主体特征
            description = await _enhance_description(description, config, builder)

            return EnhanceDescriptionOutput(input_data=(f"• 描述信息：{description}。\n"
                                                        "• 风格：卡通渲染，色彩明亮且区块化，线条简洁清晰，适合作为拼豆设计蓝图。\n"
                                                        "• 背景：纯白背景（Pure transparent background），颜色为#FFFFFF。\n"
                                                        "• 细节：无阴影，无复杂纹理，整体设计易于识别和制作。\n"))
        except Exception as e:
            logger.error(f"根据简短文本生成丰富的拼豆设计描述过程中发生错误: {str(e)}", exc_info=True)
            # 在出现错误时提供一个安全且符合格式的默认输出
            # 默认视为文本描述，由后续工具链处理
            safe_text = str(input_data.input_data) if not isinstance(input_data.input_data,
                                                                     bytes) else "binary_data_input"

            return EnhanceDescriptionOutput(
                input_data=safe_text
            )

    try:
        yield FunctionInfo.from_fn(
            _enhance_description_function,
            description="Return rich descriptions of bean-matching designs.")
    except GeneratorExit:
        logger.warning("Function exited early!")
    finally:
        logger.info("Cleaning up enhance_description workflow.")


async def _enhance_description(description: str, config: EnhanceDescriptionConfig, builder: Builder) -> str:
    prompt = f"""角色设定：  
你是一名资深的风光摄影师兼场景概念设计师，擅长将简洁的场景主题转化为极具画面感、细节饱满的文本描述，用于AI绘画生成。你的描述需涵盖环境、光影、色彩、构图、氛围及细节纹理，确保内容层次分明且易于视觉化。

核心任务：  
根据用户提供的简短风景或场景主题，扩展为一段丰富、具体且符合自然逻辑的详细描述，突出视觉元素和艺术质感。

输入格式：  
用户提供单一主题（如“雪山日出”“雨林秘境”“黄昏小镇”），或简单场景（如“海边灯塔”“竹林茶室”）。

输出要求：  
1. 结构化描述（按以下顺序组织内容，但需融为连贯段落）：  
   • 环境与主体：明确核心场景、地理特征、主要物体。  

   • 时间与光影：指定时刻（如黎明、正午、黄昏）、光线方向（侧光、逆光）、强度（柔和、强烈）及光影效果（丁达尔效应、剪影）。  

   • 天气与氛围：描述气候（晴朗、雾雨、雪）、大气效果（云海、彩虹、雾霭）及情绪氛围（宁静、壮丽、神秘）。  

   • 构图与视角：设定镜头焦距（广角、长焦）、视角（鸟瞰、平视、低角度）、构图法则（三分法、引导线、框架构图）。  

   • 色彩与纹理：定义主色调、辅助色、饱和度（鲜艳、柔和），以及材质细节（岩石纹理、树叶形态、水面反光）。  

   • 风格与质感：指定艺术风格（写实、油画、水彩、赛博朋克）及技术参数（8K分辨率、超高清细节）。  

2. 语言要求：  
   • 使用具体名词和生动形容词（如“皑皑积雪的峰顶”而非“很多雪”）。  

   • 避免抽象词汇，优先感官描述（视觉、触觉、氛围感）。  

   • 保持段落紧凑，无需编号或分点，纯文本连续输出。

示例参考（用户输入主题）：
• 输入：雪山日出  

  输出：黎明时分，金色阳光穿透薄雾，洒在巍峨的雪山之巅，峰顶皑皑积雪染上暖橘色，山脊投下深邃的蓝色阴影。山脚下蜿蜒的冰川湖倒映着天空，水面泛起粼粼波光。广角镜头（16mm）捕捉全景，小光圈（f/16）确保前景的岩石纹理与远处峰峦均清晰可见。冷色调的雪地与暖色天空形成对比，超写实风格，8K分辨率，营造出壮丽而宁静的圣洁氛围。

• 输入：雨林秘境  

  输出：热带雨林深处，参天古木缠绕着藤蔓，露珠悬挂在蕨类植物的羽状叶尖。阳光透过浓密树冠，形成斑驳的丁达尔光束，照亮地上厚厚的腐殖层和鲜艳的兰花。微距视角（100mm）聚焦于苔藓覆盖的树根，大光圈（f/2.8）营造浅景深，背景虚化为朦胧的绿色迷雾。高饱和度色彩，强调翡翠绿的植被与猩红兰花对比，弥漫着潮湿、生机勃勃的神秘气息。

约束规则：  
• 仅输出描述文本，不加额外解释。  

• 禁止虚构与主题无关的元素（如“雪山”中加入海洋）。  

• 优先采用常见摄影与绘画术语（如“黄金时刻光线”“油画质感”）。

处理流程：
    现在，请根据用户输入的文本，生成相应的详细描述。
    用户输入：“{description}”"""
    # 3. 调用LLM并获取响应
    try:
        llm = await builder.get_llm(config.llm_name, wrapper_type=LLMFrameworkEnum.LANGCHAIN)
        response = await llm.ainvoke(prompt)
        # 4. 清理和解析响应，去除可能的首尾空格或换行，进行小写比较以确保鲁棒性
        return response.content
    except Exception as e:
        # 5. 异常处理：如果LLM调用失败，记录错误并默认返回False，避免阻塞主流程
        logger.error(f"在增强描述 '{description}' 时调用LLM失败: {str(e)}")
        return description
