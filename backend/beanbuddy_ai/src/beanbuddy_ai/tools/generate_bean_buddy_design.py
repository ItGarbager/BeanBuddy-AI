import logging

from pydantic import Field

from nat.builder.builder import Builder
from nat.builder.function_info import FunctionInfo
from nat.cli.register_workflow import register_function
from nat.data_models.function import FunctionBaseConfig

logger = logging.getLogger(__name__)


class GenerateBeanBuddyDesignConfig(FunctionBaseConfig, name="generate_bean_buddy_design"):
    """
    A tool for generating Lego design diagrams and material lists
    """
    # Add your custom configuration parameters here
    parameter: str = Field(default="default_value", description="Notional description for this parameter")


@register_function(config_type=GenerateBeanBuddyDesignConfig)
async def generate_bean_buddy_design_function(
    config: GenerateBeanBuddyDesignConfig, builder: Builder
):
    # Implement your function logic here
    async def _generate_bean_buddy_design_function(input_message: str) -> str:
        # Process the input_message and generate output
        output_message = f"Hello from generate_bean_buddy_design workflow! You said: {input_message}"
        return output_message

    try:
        yield FunctionInfo.from_fn(
            _generate_bean_buddy_design_function,
            description="Return the generated bean-spelling design diagram and material list.")
    except GeneratorExit:
        logger.warning("Function exited early!")
    finally:
        logger.info("Cleaning up generate_bean_buddy_design workflow.")
