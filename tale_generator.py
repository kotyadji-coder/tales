import os
import uuid
from pathlib import Path

TALES_DIR = Path(__file__).parent / "tales"
TALES_DIR.mkdir(exist_ok=True)


def save_tale(title: str, image_bytes: bytes, story_text: str, server_url: str = "http://72.56.126.111:8000") -> str:
    """
    Сохраняет сказку в HTML и картинку.
    Возвращает tale_id (UUID).
    """
    tale_id = str(uuid.uuid4())[:8]

    # Сохраняем картинку
    image_path = TALES_DIR / f"{tale_id}.png"
    with open(image_path, "wb") as f:
        f.write(image_bytes)

    # Генерируем HTML
    image_url = f"{server_url}/tales/{tale_id}.png"
    html_content = _generate_html(title, image_url, story_text)

    # Сохраняем HTML
    html_path = TALES_DIR / f"{tale_id}.html"
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    return tale_id


def _generate_html(title: str, image_url: str, story_text: str) -> str:
    """Генерирует красивый HTML для сказки."""
    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: 'Georgia', 'Garamond', serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
            color: #333;
        }}

        .container {{
            max-width: 800px;
            margin: 0 auto;
            background: white;
            border-radius: 15px;
            box-shadow: 0 10px 40px rgba(0, 0, 0, 0.3);
            overflow: hidden;
        }}

        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 40px 30px;
            text-align: center;
            color: white;
            border-bottom: 5px solid #ffd700;
        }}

        .header h1 {{
            font-size: 2.5em;
            margin-bottom: 10px;
            text-shadow: 2px 2px 4px rgba(0, 0, 0, 0.2);
            font-weight: normal;
            letter-spacing: 1px;
        }}

        .decoration {{
            font-size: 2em;
            margin: 10px 0;
        }}

        .content {{
            padding: 40px 30px;
        }}

        .image-container {{
            text-align: center;
            margin: 30px 0;
            padding: 20px;
            background: #f8f9fa;
            border-radius: 10px;
            border: 3px solid #667eea;
        }}

        .image-container img {{
            max-width: 100%;
            height: auto;
            border-radius: 10px;
            box-shadow: 0 5px 15px rgba(0, 0, 0, 0.2);
        }}

        .story-text {{
            line-height: 1.8;
            font-size: 1.1em;
            color: #555;
            margin: 30px 0;
            text-align: justify;
            letter-spacing: 0.3px;
        }}

        .story-text p {{
            margin-bottom: 20px;
            text-indent: 2em;
        }}

        .story-text p:first-letter {{
            font-size: 1.3em;
            font-weight: bold;
            color: #667eea;
        }}

        .action-bar {{
            display: flex;
            justify-content: center;
            gap: 15px;
            margin-top: 40px;
            padding-top: 20px;
            border-top: 2px solid #eee;
        }}

        button {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            padding: 12px 30px;
            border-radius: 25px;
            font-size: 1em;
            cursor: pointer;
            transition: transform 0.2s, box-shadow 0.2s;
            font-weight: 500;
        }}

        button:hover {{
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(102, 126, 234, 0.4);
        }}

        button:active {{
            transform: translateY(0);
        }}

        .print-only {{
            display: none;
        }}

        @media print {{
            body {{
                background: white;
                padding: 0;
            }}

            .container {{
                box-shadow: none;
                border-radius: 0;
            }}

            .action-bar {{
                display: none;
            }}

            .header {{
                border-bottom: 2px solid #ccc;
            }}

            button {{
                display: none;
            }}

            @page {{
                margin: 2cm;
            }}
        }}

        @media (max-width: 600px) {{
            .header h1 {{
                font-size: 1.8em;
            }}

            .content {{
                padding: 20px 15px;
            }}

            .story-text {{
                font-size: 1em;
            }}

            .action-bar {{
                flex-direction: column;
            }}

            button {{
                width: 100%;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="decoration">✨ 📖 ✨</div>
            <h1>{title}</h1>
            <div class="decoration">✨ 📖 ✨</div>
        </div>

        <div class="content">
            <div class="image-container">
                <img src="{image_url}" alt="{{title}}" loading="lazy">
            </div>

            <div class="story-text">
                {story_text.replace(chr(10), '</p><p>')}
            </div>

            <div class="action-bar">
                <button onclick="window.print()">🖨️ Распечатать</button>
            </div>
        </div>
    </div>
</body>
</html>"""
