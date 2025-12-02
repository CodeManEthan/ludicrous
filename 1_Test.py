from PIL import Image

def get_png_dimensions(file_path):
    """
    Get the dimensions (width, height) of a PNG file.

    Parameters:
    - file_path (str): The path to the PNG file.

    Returns:
    - tuple: A tuple (width, height) representing the dimensions of the image.
    """
    with Image.open(file_path) as img:
        width, height = img.size
    return width, height

