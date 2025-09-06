from enum import Enum
from typing import Union, Optional, Dict, Any

from pydantic import Field, BaseModel


class InputType(str, Enum):
    """定义输入类型的枚举，与提示词中的路由决策完全对应"""
    TEXT_DESCRIPTION = "text_description"
    ENTITY_NAME = "entity_name"
    IMAGE = "image"


class IdentifyInputTypeInput(BaseModel):
    """
    输入识别工具的输入模型
    支持文本字符串或图像数据（base64编码或字节）
    """
    input_data: Union[str, bytes] = Field(
        ...,
        description="用户的原始输入内容，可以是文本字符串或图像数据（base64编码或字节）"
    )

    metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="可选的元数据信息"
    )


class IdentifyInputTypeOutput(BaseModel):
    """
    输入识别工具的输出模型
    严格遵循工作流要求：返回识别出的输入类型和初步处理后的数据
    Agent将根据input_type字段的值进行路由决策
    """
    """
        输入识别工具的输出模型
        严格遵循工作流要求，只返回两个字段：
        - input_type: 用于路由决策
        - metadata: 用于携带辅助后续处理的额外信息
        """
    input_type: InputType = Field(
        ...,
        description="识别出的输入类型，必须是 'text_description'（文本描述）, 'entity_name'（实体名称） 或 'image'（图片）。此字段直接决定后续工具链的路由选择。"
    )

    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="包含辅助后续工具处理的元数据，如置信度、推理原因、处理后的数据、图像格式、文本长度等。"
    )
