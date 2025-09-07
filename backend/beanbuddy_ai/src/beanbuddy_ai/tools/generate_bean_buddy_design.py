import json
import logging
import math
import os
# 保留统计信息
from collections import Counter
from datetime import datetime
from io import BytesIO
from typing import Dict, Any

import cv2
import numpy as np
import requests
from PIL import Image, ImageDraw, ImageFont
from nat.builder.builder import Builder
from nat.builder.function_info import FunctionInfo
from nat.cli.register_workflow import register_function
from nat.data_models.function import FunctionBaseConfig

from ..models import GenerateBeanBuddyDesignInput, GenerateBeanBuddyDesignOutput

logger = logging.getLogger(__name__)


class GenerateBeanBuddyDesignConfig(FunctionBaseConfig, name="generate_bean_buddy_design"):
    """
    A tool for generating Lego design diagrams and material lists
    """
    # Add your custom configuration parameters here
    pass


@register_function(config_type=GenerateBeanBuddyDesignConfig)
async def generate_bean_buddy_design_function(
        config: GenerateBeanBuddyDesignConfig, builder: Builder
):
    # Implement your function logic here
    async def _generate_bean_buddy_design_function(
            input_data: GenerateBeanBuddyDesignInput) -> GenerateBeanBuddyDesignOutput:
        try:
            # 获取默认配置中的api_key
            result = _generate_bead_design(input_data.input_data)
            logger.info("颜色统计: %s", result['color_statistics'])
            logger.info("总豆子数量: %s", result['total_beads'])

            # 拼接本地链接
            total_beads = result['total_beads']
            color_statistics = result['color_statistics']

            result_str = f"![设计图](http://localhost:3000/{result['image_name']})\n材料清单列表：{color_statistics}\n总数量：{total_beads}"
            return GenerateBeanBuddyDesignOutput(input_data=result_str)
        except Exception as e:
            logger.error(f"生成拼豆设计图及材料列表过程中发生错误: {str(e)}", exc_info=True)
            # 在出现错误时提供一个安全且符合格式的默认输出
            # 默认视为文本描述，由后续工具链处理
            safe_text = str(input_data.input_data) if not isinstance(input_data.input_data,
                                                                     bytes) else "binary_data_input"

            return GenerateBeanBuddyDesignOutput(
                input_data=safe_text
            )

    try:
        yield FunctionInfo.from_fn(
            _generate_bean_buddy_design_function,
            description="Return the generated bean-spelling design diagram and material list.")
    except GeneratorExit:
        logger.warning("Function exited early!")
    finally:
        logger.info("Cleaning up generate_bean_buddy_design workflow.")


def _generate_bead_design(image_url: str, color_card_template: str = "卡卡") -> Dict[str, Any]:
    """
    生成拼豆设计图并统计颜色数量。

    Args:
        image_url (str): 输入图片的URL。

    Returns:
        dict: 包含处理后的图片数据（如Base64编码字符串）和颜色统计结果。
    """

    # 保存结果图片路径
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    image_name = f"bead_design_{timestamp}.png"
    image_output_path = f"../frontend/public/{image_name}"

    # 颜色卡示例（与之前相同）
    color_card_json = json.load(open('beanbuddy_ai/src/beanbuddy_ai/configs/color_cards.json', 'rb'))

    # 处理单张图像
    result = process_large_image_with_color_matching(
        image_url=image_url,
        color_card_json=color_card_json.get(color_card_template),
        image_output_path=image_output_path,
        draw_labels=True
    )

    # 提取所有颜色名称
    color_names = [cell['matched_color']['name'] for cell in result.values()]

    # 统计出现次数
    color_count = Counter(color_names)

    # 输出结果
    color_names = dict(color_count)

    return {
        'image_name': image_name,
        'color_statistics': color_names,
        'total_beads': sum(color_count.values()),
    }


def color_distance(rgb1, rgb2):
    """计算两个RGB颜色之间的欧几里得距离"""
    return math.sqrt(sum((c1 - c2) ** 2 for c1, c2 in zip(rgb1, rgb2)))


def find_closest_color(avg_color, color_card: dict):
    """在颜色卡中找到最接近的颜色"""
    min_distance = float('inf')
    closest_color_name = "Unknown"
    closest_color_hex = "#000000"
    closest_color_rgb = (0, 0, 0)

    for color_name, color_info in color_card.items():
        card_rgb = tuple(color_info['rgb'])
        distance = color_distance(avg_color, card_rgb)

        if distance < min_distance:
            min_distance = distance
            closest_color_name = color_name
            closest_color_hex = color_info['hex']
            closest_color_rgb = card_rgb  # 使用颜色卡中的标准RGB值

    return closest_color_name, closest_color_hex, closest_color_rgb


def process_tile_color_matching(tile_np, color_card):
    """处理图像块的颜色匹配"""
    # 计算图像块的平均颜色
    if len(tile_np.shape) == 3:
        avg_color = np.mean(tile_np, axis=(0, 1)).astype(int)
        # 找到最接近的颜色
        color_name, color_hex, matched_rgb = find_closest_color(avg_color, color_card)
        return color_name, color_hex, avg_color.tolist(), matched_rgb
    return "Unknown", "#000000", [0, 0, 0], (0, 0, 0)


def process_large_image_with_color_matching(image_url, color_card_json,
                                            image_output_path=None,
                                            draw_labels=False,
                                            replace_colors=True) -> Dict[str, Any]:
    """
    分块处理大图像并进行颜色匹配和替换

    参数:
    image_url: 输入图像链接
    color_card_json: 颜色卡JSON
    image_output_path: 输出图像路径（可选）
    draw_labels: 是否在图像上绘制颜色标签
    replace_colors: 是否将网格替换为匹配的颜色

    返回:
    color_mapping: 每个网格的颜色匹配结果字典
    """
    # 解析颜色卡
    if isinstance(color_card_json, str):
        color_card = json.loads(color_card_json)
    else:
        color_card = color_card_json

    # 存储颜色匹配结果
    color_mapping = {}

    response = requests.get(image_url)
    original_img = Image.open(BytesIO(response.content))
    original_img = Image.fromarray(np.uint8(original_img)).convert('RGB')
    height, width = original_img.size
    original_img = original_img.resize([height // 2, width // 2], cv2.INTER_NEAREST)
    original_img.save('temp.png')

    # 读取图像
    image = cv2.imread('temp.png')
    # 放大倍数
    magnification = 5
    # 指定新尺寸
    height, width = image.shape[:2]
    height *= magnification
    width *= magnification
    grid_size = 10 * magnification

    resized_image = cv2.resize(image, (width, height), interpolation=cv2.INTER_NEAREST)
    # 保存
    cv2.imwrite('temp.png', resized_image)

    with Image.open('temp.png') as original_img:
        # 创建空白画布（与原图尺寸相同，白色背景）
        canvas = Image.new('RGB', original_img.size, (255, 255, 255))
        draw = ImageDraw.Draw(canvas)

        # 处理每个网格
        for y in range(0, height, grid_size):
            for x in range(0, width, grid_size):
                # 计算当前网格区域
                box = (x, y, min(x + grid_size, width), min(y + grid_size, height))
                box_width = box[2] - box[0]
                box_height = box[3] - box[1]

                # 提取图像块
                tile = original_img.crop(box)
                tile_np = np.array(tile)

                # 颜色匹配
                color_name, color_hex, avg_color, matched_rgb = process_tile_color_matching(tile_np, color_card)
                matched_rgb = tuple(np.clip(matched_rgb, 0, 255).astype(int))

                # 存储结果
                cell_id = f"{x}_{y}"
                color_mapping[cell_id] = {
                    'position': {'x': x, 'y': y},
                    'size': {'width': box_width, 'height': box_height},
                    'avg_color': avg_color,
                    'matched_color': {
                        'name': color_name,
                        'hex': color_hex,
                        'rgb': matched_rgb
                    }
                }

                # 替换网格颜色为匹配的颜色
                if replace_colors:
                    # 创建纯色块
                    color_block = Image.new('RGB', (box_width, box_height), tuple(matched_rgb))

                    # 将纯色块粘贴到输出图像
                    canvas.paste(color_block, (x, y))

                # 在图像上绘制标签
                if draw_labels:
                    # 计算网格中心
                    center_x = x + box_width // 2
                    center_y = y + box_height // 2

                    # 根据背景颜色亮度选择文本颜色
                    brightness = (matched_rgb[0] * 299 + matched_rgb[1] * 587 + matched_rgb[2] * 114) // 1000
                    text_color = 'black' if brightness > 128 else 'white'

                    # 绘制标签
                    font = ImageFont.load_default(size=3 * magnification)

                    if font:
                        draw.text((center_x, center_y), color_name, fill=text_color, font=font, anchor='mm')
                    else:
                        draw.text((center_x, center_y), color_name, fill=text_color, anchor='mm')

            # 绘制网格线
            for x in range(grid_size, width, grid_size):
                draw.line([(x, grid_size), (x, height)], fill='white', width=1)
            for y in range(grid_size, height, grid_size):
                draw.line([(grid_size, y), (width, y)], fill='white', width=1)
        # 保存输出图像
        if image_output_path and (draw_labels or replace_colors):
            canvas.save(image_output_path)

    os.remove("temp.png")

    return color_mapping
