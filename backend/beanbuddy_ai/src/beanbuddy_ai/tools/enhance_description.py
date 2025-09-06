import logging

from pydantic import Field

from nat.builder.builder import Builder
from nat.builder.function_info import FunctionInfo
from nat.cli.register_workflow import register_function
from nat.data_models.function import FunctionBaseConfig

logger = logging.getLogger(__name__)


class EnhanceDescriptionConfig(FunctionBaseConfig, name="enhance_description"):
    """
    A tool for generating a rich description of the bean-spelling design based on a short text
    """
    # Add your custom configuration parameters here
    parameter: str = Field(default="default_value", description="Notional description for this parameter")


@register_function(config_type=EnhanceDescriptionConfig)
async def enhance_description_function(
    config: EnhanceDescriptionConfig, builder: Builder
):
    # Implement your function logic here
    async def _enhance_description_function(input_message: str) -> str:
        # Process the input_message and generate output
        output_message = f"Hello from enhance_description workflow! You said: {input_message}"
        return output_message

    try:
        yield FunctionInfo.from_fn(
            _enhance_description_function,
            description="Return rich descriptions of bean-matching designs.")
    except GeneratorExit:
        logger.warning("Function exited early!")
    finally:
        logger.info("Cleaning up enhance_description workflow.")
