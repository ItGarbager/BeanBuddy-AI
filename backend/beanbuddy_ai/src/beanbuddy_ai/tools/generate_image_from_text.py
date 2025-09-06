import logging

from pydantic import Field

from nat.builder.builder import Builder
from nat.builder.function_info import FunctionInfo
from nat.cli.register_workflow import register_function
from nat.data_models.function import FunctionBaseConfig

logger = logging.getLogger(__name__)


class GenerateImageFromTextConfig(FunctionBaseConfig, name="generate_image_from_text"):
    """
    A tool for generating images from text descriptions
    """
    # Add your custom configuration parameters here
    parameter: str = Field(default="default_value", description="Notional description for this parameter")


@register_function(config_type=GenerateImageFromTextConfig)
async def generate_image_from_text_function(
    config: GenerateImageFromTextConfig, builder: Builder
):
    # Implement your function logic here
    async def _generate_image_from_text_function(input_message: str) -> str:
        # Process the input_message and generate output
        output_message = f"Hello from generate_image_from_text workflow! You said: {input_message}"
        return output_message

    try:
        yield FunctionInfo.from_fn(
            _generate_image_from_text_function,
            description="Return the image generated from the text description.")
    except GeneratorExit:
        logger.warning("Function exited early!")
    finally:
        logger.info("Cleaning up generate_image_from_text workflow.")
