from pathlib import Path

from PIL import Image, ImageDraw


source = Path(r"C:\Users\11600\AppData\Local\Temp\codex-clipboard-901eaf6d-d811-402b-b976-5d6a9254a91f.png")
output = Path(__file__).with_name("05_04_ablation_titles_only.png")

image = Image.open(source).convert("RGB")
draw = ImageDraw.Draw(image)

# Remove only the run ID / frame / timestamp lines; retain the action titles.
draw.rectangle((0, 55, image.width, 96), fill=(0, 0, 0))
draw.rectangle((0, 755, image.width, 796), fill=(0, 0, 0))

image.save(output, optimize=True)
print(output)
