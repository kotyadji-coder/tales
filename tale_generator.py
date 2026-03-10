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
    paragraphs = "".join(
        f"<p>{p.strip()}</p>" for p in story_text.split("\n") if p.strip()
    )
    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;700&family=Lora:ital,wght@0,400;0,500;1,400&display=swap" rel="stylesheet">
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: 'Lora', Georgia, serif;
            background-color: #F5F0E8;
            min-height: 100vh;
            padding: 40px 20px;
            color: #3D405B;
        }}

        .container {{
            max-width: 780px;
            margin: 0 auto;
            background: #ffffff;
            border-radius: 20px;
            box-shadow: 0 8px 32px rgba(61, 64, 91, 0.10), 0 2px 8px rgba(61, 64, 91, 0.06);
            overflow: hidden;
        }}

        .header {{
            padding: 48px 48px 32px;
            text-align: center;
            background: #ffffff;
        }}

        .header h1 {{
            font-family: 'Playfair Display', Georgia, serif;
            font-size: 2.2em;
            font-weight: 700;
            color: #E07A5F;
            line-height: 1.3;
            letter-spacing: 0.2px;
        }}

        .divider {{
            width: 60px;
            height: 3px;
            background: #E07A5F;
            border-radius: 2px;
            margin: 18px auto 0;
            opacity: 0.5;
        }}

        .content {{
            padding: 32px 48px 48px;
        }}

        .image-container {{
            text-align: center;
            margin: 0 0 36px;
        }}

        .image-container img {{
            max-width: 100%;
            height: auto;
            border-radius: 16px;
            box-shadow: 0 4px 20px rgba(61, 64, 91, 0.12);
            display: block;
            margin: 0 auto;
        }}

        .story-text {{
            line-height: 1.7;
            font-size: 1.08em;
            color: #3D405B;
        }}

        .story-text p {{
            margin-bottom: 1.2em;
        }}

        .story-text p:last-child {{
            margin-bottom: 0;
        }}

        .action-bar {{
            display: flex;
            justify-content: center;
            gap: 12px;
            margin-top: 40px;
            padding-top: 28px;
            border-top: 1px solid #EDE8DF;
        }}

        button {{
            background: #F2E8E4;
            color: #E07A5F;
            border: none;
            padding: 12px 28px;
            border-radius: 50px;
            font-size: 0.95em;
            font-family: 'Lora', Georgia, serif;
            cursor: pointer;
            transition: background 0.2s, transform 0.15s;
            font-weight: 500;
        }}

        button:hover {{
            background: #E8D8D2;
            transform: translateY(-1px);
        }}

        button:active {{
            transform: translateY(0);
        }}

        @media print {{
            body {{
                background: white;
                padding: 0;
            }}

            .container {{
                box-shadow: none;
                border-radius: 0;
                max-width: 100%;
            }}

            .header {{
                padding: 24px 24px 16px;
            }}

            .content {{
                padding: 16px 24px 24px;
            }}

            .action-bar {{
                display: none;
            }}

            .divider {{
                display: none;
            }}

            @page {{
                margin: 1.5cm;
            }}
        }}

        @media (max-width: 600px) {{
            body {{
                padding: 16px 12px;
            }}

            .header {{
                padding: 32px 24px 20px;
            }}

            .header h1 {{
                font-size: 1.6em;
            }}

            .content {{
                padding: 20px 24px 32px;
            }}

            .story-text {{
                font-size: 1em;
            }}

            .action-bar {{
                flex-direction: column;
                align-items: center;
            }}

            button {{
                width: 100%;
                max-width: 280px;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>{title}</h1>
            <div class="divider"></div>
        </div>

        <div class="content">
            <div class="image-container">
                <img src="{image_url}" alt="{title}" loading="lazy">
            </div>

            <div class="story-text">
                {paragraphs}
            </div>

            <div class="action-bar">
                <button onclick="window.print()">Распечатать</button>
            </div>
        </div>
    </div>
</body>
</html>"""
