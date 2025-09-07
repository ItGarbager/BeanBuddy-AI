from typing import Union

from pydantic import Field, BaseModel


class ExtractSubjectInput(BaseModel):
    """
    生成最终的设计图和材料清单工具的输入模型
    """
    input_data: str = Field(
        ...,
        description="用户的原始输入内容：文本字符串"
    )


class ExtractSubjectOutput(BaseModel):
    """
    生成最终的设计图和材料清单工具的输入模型
    严格遵循工作流要求，只返回两个字段：
    - input_data: 用于实现文生图的描述
    """
    input_data: str = Field(
        ...,
        description="用户的原始输入内容：文本字符串"
    )
