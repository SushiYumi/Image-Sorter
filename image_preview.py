from PIL import Image, ImageOps


def load_preview(path):
    # Close the source before any later rename or move.
    with Image.open(path) as image:
        image.seek(0)
        size = image.size
        image.draft('RGB', (2400, 2400))
        preview = ImageOps.exif_transpose(image)
        preview.thumbnail((2400, 2400), Image.Resampling.LANCZOS)
        return preview.convert('RGBA'), size
