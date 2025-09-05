import logging

from pydantic import Field

from nat.builder.builder import Builder
from nat.builder.function_info import FunctionInfo
from nat.cli.register_workflow import register_function
from nat.data_models.function import FunctionBaseConfig

logger = logging.getLogger(__name__)


class ApplyQStyleConfig(FunctionBaseConfig, name="apply_q_style"):
    """
    A tool for converting images into a chibi cartoon style
    """
    # Add your custom configuration parameters here
    parameter: str = Field(default="default_value", description="Notional description for this parameter")


@register_function(config_type=ApplyQStyleConfig)
async def apply_q_style_function(
    config: ApplyQStyleConfig, builder: Builder
):
    # Implement your function logic here
    async def _apply_q_style_function(input_message: str) -> str:
        # Process the input_message and generate output
        output_message = f"Hello from apply_q_style workflow! You said: {input_message}"
        return output_message

    try:
        yield FunctionInfo.from_fn(
            _apply_q_style_function,
            description="Returns Q-version cartoon style images.")
    except GeneratorExit:
        logger.warning("Function exited early!")
    finally:
        logger.info("Cleaning up apply_q_style workflow.")