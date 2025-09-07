import asyncio
import functools
import json
import logging

from dashscope import MultiModalConversation
from nat.builder.builder import Builder
from nat.builder.function_info import FunctionInfo
from nat.cli.register_workflow import register_function
from nat.data_models.function import FunctionBaseConfig

from ..models import GenerateImageFromTextInput, GenerateImageFromTextOutput

logger = logging.getLogger(__name__)


class GenerateImageFromTextConfig(FunctionBaseConfig, name="generate_image_from_text"):
    """
    A tool for generating images from text descriptions
    """
    # Add your custom configuration parameters here
    pass


@register_function(config_type=GenerateImageFromTextConfig)
async def generate_image_from_text_function(
        config: GenerateImageFromTextConfig, builder: Builder
):
    # Implement your function logic here
    async def _generate_image_from_text_function(input_data: GenerateImageFromTextInput) -> GenerateImageFromTextOutput:

        try:

            # 获取默认配置中的api_key
            api_key = builder.get_llm_config("default_llm").__dict__.get("api_key")
            # 调用阿里云通义千问-文生图模型生成图片
            image_url = await _generate_image_from_text(input_data.input_data, api_key)

            return GenerateImageFromTextOutput(input_data=image_url)

        except Exception as e:
            logger.error(f"描述生成文本过程中发生错误: {str(e)}", exc_info=True)
            # 在出现错误时提供一个安全且符合格式的默认输出
            # 默认视为文本描述，由后续工具链处理
            safe_text = str(input_data.input_data) if not isinstance(input_data.input_data,
                                                                     bytes) else "binary_data_input"

            return GenerateImageFromTextOutput(
                input_data=safe_text
            )

    try:
        yield FunctionInfo.from_fn(
            _generate_image_from_text_function,
            description="Return the image generated from the text description.")
    except GeneratorExit:
        logger.warning("Function exited early!")
    finally:
        logger.info("Cleaning up generate_image_from_text workflow.")


async def _generate_image_from_text(prompt: str, api_key: str) -> str:
    messages = [
        {
            "role": "user",
            "content": [
                {
                    "text": prompt
                }
            ]
        }
    ]
    try:

        # 预先绑定参数
        sync_call = functools.partial(
            MultiModalConversation.call,
            api_key=api_key,
            model="qwen-image",
            messages=messages,
            result_format='message',
            stream=False,
            watermark=False,
            prompt_extend=True,
            negative_prompt='',
            size='1328*1328'
        )

        # 使用 asyncio.to_thread 在单独线程中执行同步的API调用
        response = await asyncio.to_thread(sync_call)

        if response.status_code == 200:
            # 提取图片链接的关键代码
            # 注意：response 可能已经是对象，无需再 json.dumps 和 json.loads
            # 根据实际情况调整，如果 response 是对象且支持属性访问，可直接使用 response.output.choices[0]...
            response_data = json.loads(
                json.dumps(response, ensure_ascii=False, default=lambda o: o.__dict__)) if hasattr(response,
                                                                                                   '__dict__') else response
            # 访问嵌套结构：output -> choices -> 第一个元素 -> message -> content -> 第一个元素 -> image
            image_url = response_data['output']['choices'][0]['message']['content'][0]['image']
            return image_url
        else:
            raise Exception(f"HTTP返回码：{response.status_code}\n"
                            f"错误码：{response.code}\n"
                            f"错误信息：{response.message}")
    except KeyError as e:
        raise Exception(f"在解析JSON时出错，未能找到预期的键: {e}")
    except IndexError as e:
        raise Exception(f"在访问列表时出错，可能列表为空: {e}")
    except Exception as e:
        raise Exception(f"发生未知错误: {e}")
