import json
import logging
import math
# 保留统计信息
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime
from functools import lru_cache
from io import BytesIO
from operator import itemgetter
from typing import Dict, Any, List, Tuple

import cv2
import numpy as np
import requests
from PIL import Image, ImageDraw, ImageFont
from nat.builder.builder import Builder
from nat.builder.function_info import FunctionInfo
from nat.cli.register_workflow import register_function
from nat.data_models.function import FunctionBaseConfig
from pydantic import Field
from rembg import new_session, remove
from rembg.sessions import BaseSession

from ..models import GenerateBeanBuddyDesignInput, GenerateBeanBuddyDesignOutput

logger = logging.getLogger(__name__)

# 全局会话缓存
_session_cache = {}
_color_card_cache = {}


class GenerateBeanBuddyDesignConfig(FunctionBaseConfig, name="generate_bean_buddy_design"):
    """
    A tool for generating Lego design diagrams and material lists
    """
    # Add your custom configuration parameters here
    color_card_template: str = Field(
        default="卡卡",
        description="用户生成拼豆设计图的色卡模版，默认“卡卡”"
    )

    rembg_model_name: str = Field(
        default="卡卡",
        description="rembg模型名称，默认“isnet-general-use”"
    )


@register_function(config_type=GenerateBeanBuddyDesignConfig)
async def generate_bean_buddy_design_function(
        config: GenerateBeanBuddyDesignConfig, builder: Builder
):
    """
            model_name: 模型名称，可选值包括:
            - "u2net" (通用模型)
            - "u2netp" (轻量版)
            - "u2net_human_seg" (人像专用)
            - "isnet-general-use" (通用高质量，推荐默认)
            - "silueta" (最快速度)
            - "birefnet-general" (商业级质量)
            """
    # 全局会话对象，避免重复加载模型
    session: BaseSession = get_session(config.rembg_model_name)
    # Implement your function logic here
    async def _generate_bean_buddy_design_function(
            input_data: GenerateBeanBuddyDesignInput) -> GenerateBeanBuddyDesignOutput:
        try:
            result = _generate_bead_design(input_data.input_data, session, config.color_card_template)
            color_statistics = []
            for color, statistic in result['color_statistics'].items():
                color_name, hex_str = color.split("_")
                temp_color_statistic = f'| {color_name} | {statistic} | <span style="color: {hex_str};">■</span> |'
                color_statistics.append(temp_color_statistic)

            # 拼接本地链接
            total_beads = result['total_beads']
            output_markdown = (
                "### Q版拼豆设计图\n"
                f"![Q版拼豆设计图]({result['image_name']})\n"
                "### 材料清单\n"
                f"#### 色卡: {config.color_card_template}\n"
                "| 珠子编号 | 数量 | 颜色预览 |\n"
                f"| --- | --- | --- |\n{'\n'.join(color_statistics)}\n"
                f"### 总数量\n{total_beads}"
            )

            return GenerateBeanBuddyDesignOutput(input_data=output_markdown)
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


def _generate_bead_design(image_url: str, session: BaseSession, color_template: str = "卡卡") -> Dict[str, Any]:
    """
    生成拼豆设计图并统计颜色数量。

    Args:
        image_url (str): 输入图片的URL。
        session (BaseSession): rembg模型。
        color_template (str): 色卡模板名称。

    Returns:
        dict: 包含处理后的图片数据（如Base64编码字符串）和颜色统计结果。
    """

    # 保存结果图片路径
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    image_name = f"bead_design_{timestamp}.png"
    image_output_path = f"../frontend/public/{image_name}"

    # 处理单张图像
    result = process_large_image_optimized(
        image_url=image_url,
        session=session,
        image_output_path=image_output_path,
        draw_labels=True,
        max_workers=3,  # 根据CPU核心数调整
        color_template=color_template
    )

    return {
        'image_name': image_name,
        **result
    }


def get_cached_color_card(color_card_json, card_name="卡卡"):
    """缓存颜色卡数据，避免重复解析"""
    cache_key = f"{hash(str(color_card_json))}_{card_name}"
    if cache_key not in _color_card_cache:
        if isinstance(color_card_json, str):
            color_data = json.loads(color_card_json)
        else:
            color_data = color_card_json
        _color_card_cache[cache_key] = color_data.get(card_name, {})
    return _color_card_cache[cache_key]


def get_session(model_name: str = "birefnet-general") -> BaseSession:
    """获取或创建模型会话（使用缓存避免重复加载模型）"""
    if model_name not in _session_cache:
        try:
            _session_cache[model_name] = new_session(model_name)
            logger.info(f"已加载模型: {model_name}")
        except Exception as e:
            logger.error(f"加载模型 {model_name} 失败: {e}")
            # 回退到默认模型
            _session_cache[model_name] = new_session("isnet-general-use")
    return _session_cache[model_name]


def remove_background_rembg_optimized(image_url: str,
                                      session: BaseSession,
                                      enable_alpha_matting: bool = True) -> Image.Image:
    """
    使用rembg库进行高质量背景移除（优化版）

    参数:
    image_url: 图片链接
    session: rembg模型会话
    enable_alpha_matting: 是否启用Alpha Matting精细边缘处理

    返回:
    PIL Image对象（RGBA模式，背景透明）
    """
    try:
        # 下载图像（使用流式下载减少内存使用）
        response = requests.get(image_url, timeout=10, stream=True)
        response.raise_for_status()

        # 使用BytesIO进行流式处理
        content = BytesIO()
        for chunk in response.iter_content(chunk_size=8192):
            content.write(chunk)
        content.seek(0)

        input_image = Image.open(content).convert("RGBA")
        logger.info(f"图像下载成功，尺寸: {input_image.size}")

        # 移除背景
        output_image = remove(
            input_image,
            session=session,
            alpha_matting=enable_alpha_matting,
            alpha_matting_foreground_threshold=240,
            alpha_matting_background_threshold=10,
            alpha_matting_erode_size=5,
            post_process_mask=True
        )

        return output_image

    except Exception as e:
        logger.error(f"背景移除处理失败: {e}")
        raise


@lru_cache(maxsize=None)
def color_distance(rgb1, rgb2):
    """计算两个RGB颜色之间的欧几里得距离（使用缓存）"""
    return math.sqrt(sum((c1 - c2) ** 2 for c1, c2 in zip(rgb1, rgb2)))


def find_closest_color(avg_color, color_card):
    """在颜色卡中找到最接近的颜色（优化版）"""

    min_distance = float('inf')
    closest_color_name = "Unknown"
    closest_color_hex = "#000000"
    closest_color_rgb = (0, 0, 0)

    # 预计算颜色卡RGB值
    color_rgbs = [(name, info['rgb']) for name, info in color_card.items()]

    for color_name, card_rgb in color_rgbs:
        distance = color_distance(tuple(avg_color), tuple(card_rgb))
        if distance < min_distance:
            min_distance = distance
            closest_color_name = color_name
            closest_color_hex = color_card[color_name]['hex']
            closest_color_rgb = card_rgb
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


def optimized_resize(image: Image.Image, target_size: Tuple[int, int]) -> Image.Image:
    """
    优化图像缩放函数，减少格式转换开销
    """
    # 直接使用PIL进行缩放，减少格式转换
    return image.resize(target_size, Image.Resampling.LANCZOS)


def process_grid_cell_batch(grid_data: List[Tuple]) -> List[Dict]:
    """
    批量处理网格单元 - 适用于多进程
    """
    results = []
    for x, y, grid_size, width, height, final_image, alpha_resized, color_card in grid_data:
        # 计算当前网格区域
        box = (x, y, min(x + grid_size, width), min(y + grid_size, height))
        box_width = box[2] - box[0]
        box_height = box[3] - box[1]

        # 检查透明度
        alpha_box = (x, y, box[2], box[3])
        alpha_tile = alpha_resized[alpha_box[1]:alpha_box[3], alpha_box[0]:alpha_box[2]]

        if np.all(alpha_tile == 0):
            results.append(None)
            continue

        # 提取图像块并处理
        tile_np = final_image[box[1]:box[3], box[0]:box[2]]

        # 颜色匹配
        color_name, color_hex, avg_color, matched_rgb = process_tile_color_matching(
            tile_np, color_card
        )

        results.append({
            'cell_id': f"{x}_{y}",
            'position': {'x': x, 'y': y},
            'size': {'width': box_width, 'height': box_height},
            'avg_color': avg_color,
            'matched_color': {
                'name': color_name,
                'hex': color_hex,
                'rgb': matched_rgb
            }
        })

    return results


def resize_image_pil(image, scale_factor, interpolation=cv2.INTER_NEAREST):
    """使用PIL进行图像缩放（内存中操作）"""
    width, height = image.size
    new_size = (int(width * scale_factor), int(height * scale_factor))
    return image.resize(new_size, interpolation)


def add_coordinates_and_statistics(canvas, width, height, grid_size, sorted_dict, color_mapping, color_template):
    """
    添加坐标网格和颜色统计信息

    参数:
    canvas: 画布对象
    draw: ImageDraw对象
    width: 画布宽度
    height: 画布高度
    grid_size: 网格大小
    sorted_dict: 排序后的颜色次数字典
    color_mapping: 颜色映射数据
    color_template: 颜色模板名称
    """

    # 设置坐标区域高度（底部和右侧各留50像素用于坐标和统计信息）
    # 计算颜色块尺寸
    bar_height = 140
    # 每个颜色块的固定宽度（等宽）
    color_width = grid_size * 12
    # 坐标字体大小
    coordinates_font_size = 20
    # 统计条字体大小
    statistics_font_size = 80
    max_rows = sorted_dict.__len__() * color_width // width + 1
    coordinate_area_height = bar_height * (max_rows + 2) + coordinates_font_size
    coordinate_area_width = 50

    # 调整画布大小以容纳坐标和统计信息
    new_width = width + coordinate_area_width
    new_height = height + coordinate_area_height
    new_canvas = Image.new('RGB', (new_width, new_height), (255, 255, 255))
    new_canvas.paste(canvas, (0, bar_height * 2))

    # 创建新的draw对象
    new_draw = ImageDraw.Draw(new_canvas)

    # 绘制色卡系列
    new_draw.text(
        (coordinates_font_size, coordinates_font_size),
        f"COLOR TEMPLATE: {color_template}",
        fill='black',
        font=ImageFont.truetype("arial.ttf", 160)
    )

    # 1. 添加坐标网格
    try:
        coordinate_font = ImageFont.truetype("arial.ttf", coordinates_font_size)
        statistics_font = ImageFont.truetype("arial.ttf", statistics_font_size)
    except:
        coordinate_font = ImageFont.load_default()
        statistics_font = ImageFont.load_default()
    # 添加X轴坐标
    new_draw.line([(0, height + bar_height * 2), (width, height + bar_height * 2)], fill='black', width=1)
    for x in range(0, width, grid_size):
        if x % grid_size == 0 or x == width - grid_size:  # 每5个网格标记一次
            new_draw.text((x + 5, height + bar_height * 2), str(x // grid_size + 1), fill='black',
                          font=coordinate_font)

    # 添加Y轴坐标
    new_draw.line([(width, 0), (width, height + bar_height * 2)], fill='black', width=1)
    for y in range(0, height, grid_size):
        if y % grid_size == 0 or y == height - grid_size:  # 每5个网格标记一次
            new_draw.text((width, y + 5 + bar_height * 2), str(y // grid_size + 1), fill='black',
                          font=coordinate_font)

    # 2. 添加颜色统计条
    # 绘制颜色统计条
    row = 0
    current_x = 0

    for color_name, count in sorted_dict.items():
        color, _ = color_name.split('_')
        # 获取颜色信息
        color_info = next(cell for cell in color_mapping.values()
                          if cell['matched_color']['name'] == color and cell["matched_color"]["hex"] == _)
        color_rgb = tuple(color_info['matched_color']['rgb'])

        # 如果当前行放不下，换到下一行
        if current_x + color_width > width and row < max_rows - 1:
            row += 1
            current_x = 0

        # 绘制颜色块
        if row < max_rows:
            y_start = height + coordinates_font_size + row * bar_height
            new_draw.rectangle(
                [current_x, y_start + bar_height * 2, current_x + color_width, y_start + bar_height + bar_height * 2],
                fill=color_rgb, outline='white', width=10)

            # 添加颜色标签（根据亮度选择文字颜色）
            brightness = (color_rgb[0] * 299 + color_rgb[1] * 587 + color_rgb[2] * 114) // 1000
            text_color = 'black' if brightness > 128 else 'white'

            new_draw.text((current_x + color_width // 2, y_start + bar_height // 2 + bar_height * 2),
                          f"{color} ({count})", fill=text_color, font=statistics_font, anchor='mm')

            current_x += color_width

    return new_canvas


def process_large_image_optimized(image_url: str, session: Any,
                                  grid_base_size: int = 10,
                                  image_output_path: str = None,
                                  draw_labels: bool = False,
                                  replace_colors: bool = True,
                                  max_workers: int = None,
                                  color_template: str = "卡卡") -> Dict[str, Any]:
    """
    优化版的大图像处理函数
    """
    # 解析颜色卡
    color_card_data = json.load(open('beanbuddy_ai/src/beanbuddy_ai/configs/color_cards.json', 'rb'))
    color_card = get_cached_color_card(color_card_data, color_template)

    # 1. 移除背景
    transparent_result = remove_background_rembg_optimized(
        image_url=image_url,
        session=session,
        enable_alpha_matting=True
    )
    # transparent_result = Image.open("temp.png").convert("RGBA")

    # 2. 转换为RGB并调整大小（全部在内存中完成）
    # 使用PIL直接缩放, scale_factor 缩放系数，1 默认不缩放，越大质量越高，但处理越慢
    resized_img = resize_image_pil(transparent_result, 1, interpolation=cv2.INTER_NEAREST)

    # 3. 放大图像（使用OpenCV但在内存中处理）
    magnification = 5
    width, height = resized_img.size
    new_size = (width * magnification, height * magnification)

    # 将PIL图像转换为numpy数组供OpenCV使用
    resized_np = np.array(resized_img)
    # 转换为BGR格式（OpenCV默认格式）
    resized_np = cv2.cvtColor(resized_np, cv2.COLOR_RGB2BGR)
    # 使用OpenCV放大（内存中操作）
    resized_image = cv2.resize(resized_np, new_size, interpolation=cv2.INTER_NEAREST)
    final_image_np = cv2.cvtColor(resized_image, cv2.COLOR_BGR2RGB)
    # 将OpenCV图像（BGR格式）转换回PIL图像（RGB格式）
    final_image = Image.fromarray(final_image_np)

    # 同时处理透明通道的放大
    alpha_channel = np.array(transparent_result.split()[-1])  # 提取alpha通道
    alpha_resized = cv2.resize(alpha_channel, new_size, interpolation=cv2.INTER_NEAREST)
    width, height = final_image.size
    grid_size = grid_base_size * magnification

    # 4. 创建画布
    canvas = Image.new('RGB', (width, height), (255, 255, 255))
    draw = ImageDraw.Draw(canvas)

    # 5. 预计算所有网格坐标
    grid_coords = []
    for y in range(0, height, grid_size):
        for x in range(0, width, grid_size):
            grid_coords.append((x, y))

    # 6. 使用多进程并行处理
    color_mapping = {}

    # 确定最佳工作进程数
    if max_workers is None:
        max_workers = max(1, min(len(grid_coords), 4))  # 限制最大进程数

    # 将网格数据分批次处理，减少进程间通信开销
    batch_size = max(10, len(grid_coords) // (max_workers * 2))
    grid_batches = []

    for i in range(0, len(grid_coords), batch_size):
        batch_coords = grid_coords[i:i + batch_size]
        batch_data = []

        for x, y in batch_coords:
            batch_data.append((x, y, grid_size, width, height,
                               final_image_np, alpha_resized, color_card))

        grid_batches.append(batch_data)

    # 使用多进程处理批次
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(process_grid_cell_batch, batch_data)
            for batch_data in grid_batches
        ]

        for future in as_completed(futures):
            batch_results = future.result()
            for result in batch_results:
                if result is None:
                    continue

                cell_id = result['cell_id']
                color_mapping[cell_id] = result

                # 应用颜色替换和标签绘制
                x, y = result['position']['x'], result['position']['y']
                box_width = result['size']['width']
                box_height = result['size']['height']
                matched_rgb = tuple(result['matched_color']['rgb'])

                if replace_colors:
                    color_block = Image.new('RGB', (box_width, box_height), matched_rgb)
                    canvas.paste(color_block, (x, y))

                if draw_labels:
                    center_x = x + box_width // 2
                    center_y = y + box_height // 2

                    brightness = (matched_rgb[0] * 299 + matched_rgb[1] * 587 + matched_rgb[2] * 114) // 1000
                    text_color = 'black' if brightness > 128 else 'white'

                    try:
                        font = ImageFont.truetype("arial.ttf", 3 * magnification)
                    except:
                        font = ImageFont.load_default()

                    draw.text((center_x, center_y), result['matched_color']['name'],
                              fill=text_color, font=font, anchor='mm')

    # 7. 绘制网格线
    for x in range(0, width, grid_size):
        draw.line([(x, 0), (x, height)], fill='black', width=1)
    for y in range(0, height, grid_size):
        draw.line([(0, y), (width, y)], fill='black', width=1)

    # 提取所有颜色名称
    color_names = [r['matched_color']['name'] + "_" + r['matched_color']['hex'] for r in color_mapping.values()]

    # 统计出现次数
    color_count = Counter(color_names)

    # 输出结果
    color_names_dict = dict(color_count)

    # 按值排序
    sorted_dict = dict(sorted(color_names_dict.items(), key=itemgetter(1), reverse=True))

    # 8. 添加坐标和统计信息
    canvas = add_coordinates_and_statistics(canvas, width, height, grid_size, sorted_dict, color_mapping,
                                            color_template)

    # 9. 保存结果
    if image_output_path:
        canvas.save(image_output_path, optimize=True, quality=95)

    return {
        'color_statistics': sorted_dict,
        'total_beads': sum(color_count.values()),
    }
