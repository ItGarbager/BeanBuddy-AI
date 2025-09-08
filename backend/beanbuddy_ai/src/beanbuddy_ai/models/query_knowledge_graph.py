from pydantic import Field, BaseModel


class QueryKnowledgeGraphInput(BaseModel):
    """
    查询知识图谱获取实体特征工具的输入模型
    """
    input_data: str = Field(
        ...,
        description="用户的原始输入内容：文本字符串"
    )


class QueryKnowledgeGraphOutput(BaseModel):
    """
    查询知识图谱获取实体特征工具的输出模型
    严格遵循工作流要求，只返回两个字段：
    - input_data: 用于实现文生图的描述
    """
    input_data: str = Field(
        ...,
        description="用户的原始输入内容：文本字符串"
    )
