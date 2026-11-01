# Randis UDS. Copyright (C) 2026 Randy Moore. GPLv3 with additional terms: every copy, clone or derivative must attribute this work first and conspicuously. See LICENSE and NOTICE.md. Original: https://github.com/RandyWilliamMoore/randis-uds
# Run: python packaging/make_finish_image.py   (needs Pillow; only when the logo changes. The result, finish_side.bmp, is committed.)
"""The side picture on setup's Finish page: the app's logo on its own dark, instead of NSIS's stock art. NSIS wants a 164x314 BMP."""
import os
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
logo = Image.open(os.path.join(os.path.dirname(HERE), "ui", "logo", "uds-base-app-icon.png")).convert("RGBA")
logo = logo.resize((116, 116), Image.LANCZOS)
side = Image.new("RGB", (164, 314), (24, 26, 31))
side.paste(logo, (24, 40), logo)
side.save(os.path.join(HERE, "finish_side.bmp"))
