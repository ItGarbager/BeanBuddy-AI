import logging

from pydantic import Field

from nat.builder.builder import Builder
from nat.builder.function_info import FunctionInfo
from nat.cli.register_workflow import register_function
from nat.data_models.function import FunctionBaseConfig

logger = logging.getLogger(__name__)


class ExtractSubjectConfig(FunctionBaseConfig, name="extract_subject"):
    """
    A tool for extracting subjects from images
    """
    # Add your custom configuration parameters here
    parameter: str = Field(default="default_value", description="Notional description for this parameter")


@register_function(config_type=ExtractSubjectConfig)
async def extract_subject_function(
    config: ExtractSubjectConfig, builder: Builder
):
    # Implement your function logic here
    async def _extract_subject_function(input_message: str) -> str:
        # Process the input_message and generate output
        output_message = f"Hello from extract_subject workflow! You said: {input_message}"
        return output_message

    try:
        yield FunctionInfo.from_fn(
            _extract_subject_function,
            description="Return the subject extracted from the image.")
    except GeneratorExit:
        logger.warning("Function exited early!")
    finally:
        logger.info("Cleaning up extract_subject workflow.")