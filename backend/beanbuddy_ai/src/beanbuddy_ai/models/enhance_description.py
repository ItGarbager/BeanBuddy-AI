from pydantic import Field, BaseModel


class EnhanceDescriptionInput(BaseModel):
    """
    根据简短文本生成丰富的拼豆设计描述工具的输入模型
    """
    input_data: str = Field(
        ...,
        description="用户的原始输入内容：文本字符串"
    )


class EnhanceDescriptionOutput(BaseModel):
    """
    根据简短文本生成丰富的拼豆设计描述工具的输入模型
    严格遵循工作流要求，只返回两个字段：
    - input_data: 用于实现文生图的描述
    """
    input_data: str = Field(
        ...,
        description="用户的原始输入内容：文本字符串"
    )
