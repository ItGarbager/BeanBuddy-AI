from typing import Union

from pydantic import Field, BaseModel


class GenerateImageFromTextInput(BaseModel):
    """
    根据描述文本生成图片工具的输入模型
    """
    input_data: str = Field(
        ...,
        description="用户的原始输入内容：文本字符串"
    )


class GenerateImageFromTextOutput(BaseModel):
    """
    根据描述文本生成图片工具的输入模型
    严格遵循工作流要求，只返回两个字段：
    - input_data: 用于实现文生图的描述
    """
    input_data: str = Field(
        ...,
        description="用户的原始输入内容：文本字符串"
    )
