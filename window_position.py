def center_window(root, window, width, height):
    # Update root dimensions to ensure accuracy
    root.update_idletasks() 

    # Get root window dimensions
    root_width = root.winfo_width()
    root_height = root.winfo_height()
    root_x = root.winfo_x()
    root_y = root.winfo_y()

    # Calculate position to center the window
    x = root_x + (root_width - width) // 2
    y = root_y + (root_height - height) // 2

    # Set dimensions and position
    window.geometry(f"{width}x{height}+{x}+{y}")

def center_window_to_display(window, width, height):
    # Get the screen width and height
    # Subtract 80 from height for taskbar
    screen_width = window.winfo_screenwidth()
    screen_height = window.winfo_screenheight() - 80

    # Calculate the position
    x_offset = (screen_width - width) // 2
    y_offset = (screen_height - height) // 2

    # Set the geometry
    window.geometry(f"{width}x{height}+{x_offset}+{y_offset}")

def set_window_to_display_size(window):
        # Get the screen width and height
    screen_width = window.winfo_screenwidth()
    screen_height = window.winfo_screenheight()

    # Set the geometry
    window.geometry(f"{screen_width}x{screen_height}")

def update_child_position_centered(root, child):
    if child.winfo_exists():
        # Get the root window's current position
        root_x = root.winfo_x()
        root_y = root.winfo_y()

        # Get the size of the root and child windows
        root_width = root.winfo_width()
        root_height = root.winfo_height()
        child_width = child.winfo_width()
        child_height = child.winfo_height()

        # Calculate the new position to keep the child centered relative to the root
        child_x = root_x + (root_width - child_width) // 2  # Center child horizontally
        child_y = root_y + (root_height - child_height) // 2  # Center child vertically

        # Optionally, you can add an offset
        child_x += 50  # Offset to avoid overlap, if desired
        child_y += 50  # Offset to avoid overlap, if desired

        # Set the child window's position
        child.geometry(f"+{child_x}+{child_y}")