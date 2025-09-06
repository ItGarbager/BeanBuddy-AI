import logging

from pydantic import Field

from nat.builder.builder import Builder
from nat.builder.function_info import FunctionInfo
from nat.cli.register_workflow import register_function
from nat.data_models.function import FunctionBaseConfig

logger = logging.getLogger(__name__)


class QueryKnowledgeGraphConfig(FunctionBaseConfig, name="query_knowledge_graph"):
    """
    A tool for querying the knowledge graph to obtain entity features
    """
    # Add your custom configuration parameters here
    parameter: str = Field(default="default_value", description="Notional description for this parameter")


@register_function(config_type=QueryKnowledgeGraphConfig)
async def query_knowledge_graph_function(
    config: QueryKnowledgeGraphConfig, builder: Builder
):
    # Implement your function logic here
    async def _query_knowledge_graph_function(input_message: str) -> str:
        # Process the input_message and generate output
        output_message = f"Hello from query_knowledge_graph workflow! You said: {input_message}"
        return output_message

    try:
        yield FunctionInfo.from_fn(
            _query_knowledge_graph_function,
            description="Return the entity features obtained from querying the knowledge graph.")
    except GeneratorExit:
        logger.warning("Function exited early!")
    finally:
        logger.info("Cleaning up query_knowledge_graph workflow.")
