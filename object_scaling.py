from debug_output import debug_print

def get_scaled_object_size(display_width, display_height, object_width, object_height):
    """
    Returns scaled width and height for an object based on the display size.
    
    Parameters:
        display_width (int): The width of the current display.
        display_height (int): The height of the current display.
        object_width (int): The original width of the object.
        object_height (int): The original height of the object.
    
    Returns:
        tuple: (scaled_width, scaled_height)
    """
    width_ratio = display_width / 1200  # Default base width
    height_ratio = display_height / 1160  # Default base height
    
    # Use the minimum ratio to maintain aspect ratio
    scaling_factor = min(width_ratio, height_ratio)

    scaled_width = int(object_width * scaling_factor)
    scaled_height = int(object_height * scaling_factor)
    
    return scaled_width, scaled_height

def get_scaled_object_size_for_horizontal_fit(num_objects, object_width, object_height, spacing, external_spacing, window_width):
    """
    Calculate the adjusted width and height for objects to fit in a single row within the window,
    considering both internal spacing between objects and external spacing around the objects.
    
    Args:
        num_objects (int): Number of objects in the row.
        object_width (int): Initial width of the objects.
        object_height (int): Initial height of the objects.
        spacing (int): Spacing between objects.
        external_spacing (int): Spacing outside the row of objects.
        window_width (int): Width of the window.
    
    Returns:
        tuple: Adjusted width and height of the objects to fit within the window.
    """
    total_spacing = (num_objects - 1) * spacing  # Total internal spacing between objects
    
    available_width = window_width - total_spacing - external_spacing  # Width left for the objects
    adjusted_width = available_width // num_objects  # Calculate width per object
    
    # Calculate the aspect ratio
    aspect_ratio = object_height / object_width
    
    # Calculate adjusted width based on the new width
    final_width = min(adjusted_width, object_width)  # Ensure the adjusted width does not exceed the initial object width
    
    # Adjust the height accordingly based on the new width
    final_height = int(final_width * aspect_ratio)

    return final_width, final_height

def get_scaled_object_height_for_vertical_fit(num_objects, object_height, spacing, external_spacing, window_height):
    """
    Calculate the adjusted width and height for objects to fit in a single row within the window,
    considering both internal spacing between objects and external spacing around the objects.
    
    Args:
        num_objects (int): Number of objects in the row.
        object_width (int): Initial width of the objects.
        object_height (int): Initial height of the objects.
        spacing (int): Spacing between objects.
        external_spacing (int): Spacing outside the row of objects.
        window_width (int): Width of the window.
    
    Returns:
        tuple: Adjusted width and height of the objects to fit within the window.
    """
    total_spacing = (num_objects - 1) * spacing  # Total internal spacing between objects
    
    available_height = window_height - total_spacing - external_spacing  # Height left for the objects
    adjusted_height = available_height // num_objects  # Calculate height per object
    
    # Calculate adjusted height based on the new width
    final_height = min(adjusted_height, object_height)  # Ensure the adjusted height does not exceed the initial object height

    return final_height

def get_frame_size_for_objects_fit(num_columns, num_rows, object_height, object_width, spacing, external_spacing):
    """
    Calculate the width and height of the frame to fit objects of the same size.

    Args:
        num_rows (int): Number of rows of smaller frames.
        num_columns (int): Number of columns of smaller frames.
        object_width (int): Width of each object.
        object_height (int): Height of each object.
        spacing (int): Spacing between adjacent objects.

    Returns:
        tuple: Width and height of the frame.
    """
    # Total width: frames + internal spacing + external spacing
    total_width = (
        num_columns * object_width
        + (num_columns - 1) * spacing
        + 2 * external_spacing
    )
    
    # Total height: frames + internal spacing + external spacing
    total_height = (
        num_rows * object_height
        + (num_rows - 1) * spacing
        + 2 * external_spacing
    )
    
    return total_width, total_height

def get_adjusted_font_size(display_width, display_height, base_font_size, base_width=1920, base_height=1000):
    """
    Calculate an adjusted font size based on display dimensions.

    Parameters:
    - display_width (int): The width of the display in pixels.
    - display_height (int): The height of the display in pixels.
    - base_font_size (int): The font size to scale based on the base dimensions.
    - base_width (int): The reference width for scaling (default is 1920).
    - base_height (int): The reference height for scaling (default is 1000) (Subtract 80 from 1080 to account for taskbar).

    Returns:
    - int: The adjusted font size.
    """
    # Calculate scaling factors for width and height
    width_scale = display_width / base_width
    height_scale = display_height / base_height

    # Use the smaller scaling factor to maintain proportionality
    scaling_factor = min(width_scale, height_scale)

    # Adjust the font size and return as an integer
    adjusted_font_size = int(base_font_size * scaling_factor)
    return adjusted_font_size

def get_distance_from_object_to_window_top(window, object):
    # Get the object's y-coordinate relative to the screen (top of the object)
    object_y_screen = object.winfo_rooty()
    
    # Get the object's height
    object_height = object.winfo_height()

    # Calculate the distance from the bottom of the object to the top of the window
    distance = (object_y_screen + object_height) 
    
    # Note: debug_print needs a game object, so we can't use it here directly
    # The print statement was likely for debugging during development
    # print(f"Distance from the bottom of the object to the top of the window: {distance} pixels")

    return distance
