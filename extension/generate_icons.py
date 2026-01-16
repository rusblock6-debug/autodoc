#!/usr/bin/env python3
"""
Генератор иконок для Chrome Extension
Создаёт простые PNG иконки с буквой "A"
"""

from PIL import Image, ImageDraw, ImageFont
import os

def create_icon(size, output_path):
    """Создаёт иконку заданного размера"""
    # Создаём изображение с фоном
    img = Image.new('RGB', (size, size), color='#4F46E5')
    draw = ImageDraw.Draw(img)
    
    # Рисуем белую букву "A"
    try:
        # Пытаемся использовать системный шрифт
        font_size = int(size * 0.6)
        font = ImageFont.truetype("arial.ttf", font_size)
    except:
        # Если не получилось, используем дефолтный
        font = ImageFont.load_default()
    
    # Центрируем текст
    text = "A"
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    
    x = (size - text_width) // 2
    y = (size - text_height) // 2
    
    draw.text((x, y), text, fill='white', font=font)
    
    # Сохраняем
    img.save(output_path, 'PNG')
    print(f"✓ Создана иконка: {output_path}")

def main():
    """Создаёт все необходимые иконки"""
    icons_dir = os.path.join(os.path.dirname(__file__), 'icons')
    os.makedirs(icons_dir, exist_ok=True)
    
    sizes = [16, 48, 128]
    
    for size in sizes:
        output_path = os.path.join(icons_dir, f'icon{size}.png')
        create_icon(size, output_path)
    
    print("\n✅ Все иконки созданы успешно!")
    print(f"📁 Расположение: {icons_dir}")

if __name__ == '__main__':
    try:
        main()
    except ImportError:
        print("❌ Ошибка: требуется библиотека Pillow")
        print("Установите: pip install Pillow")
    except Exception as e:
        print(f"❌ Ошибка: {e}")
