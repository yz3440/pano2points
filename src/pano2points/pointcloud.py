"""Convert panorama to dithered spherical point cloud for laser engraving."""

import numpy as np
from PIL import Image


def load_and_resize(image_path: str, max_size: int = 2000) -> np.ndarray:
    """Load image as grayscale and resize if needed.
    
    Args:
        image_path: Path to input image.
        max_size: Maximum dimension (width or height).
    
    Returns:
        2D numpy array with values in [0, 255] as uint8.
    """
    img = Image.open(image_path).convert("L")
    
    # Resize if too large
    if max(img.size) > max_size:
        ratio = max_size / max(img.size)
        new_size = (int(img.width * ratio), int(img.height * ratio))
        img = img.resize(new_size, Image.Resampling.LANCZOS)
    
    return np.array(img, dtype=np.uint8)


def floyd_steinberg_dither(image: np.ndarray) -> np.ndarray:
    """Apply Floyd-Steinberg dithering to convert grayscale to binary.
    
    Args:
        image: 2D uint8 array (0-255).
    
    Returns:
        2D boolean array where True = white (point), False = black (no point).
    """
    # Work with float for error diffusion
    img = image.astype(np.float32)
    height, width = img.shape
    
    for y in range(height):
        for x in range(width):
            old_pixel = img[y, x]
            new_pixel = 255.0 if old_pixel > 127 else 0.0
            img[y, x] = new_pixel
            error = old_pixel - new_pixel
            
            # Distribute error to neighbors
            if x + 1 < width:
                img[y, x + 1] += error * 7 / 16
            if y + 1 < height:
                if x > 0:
                    img[y + 1, x - 1] += error * 3 / 16
                img[y + 1, x] += error * 5 / 16
                if x + 1 < width:
                    img[y + 1, x + 1] += error * 1 / 16
    
    return img > 127


def dither_to_points_spherical(
    dithered: np.ndarray,
    radius: float = 50.0,
    invert: bool = False,
    rotate_x: float = 0.0,
    rotate_y: float = 0.0,
    rotate_z: float = 0.0,
    height_min: float = 0.0,
    height_max: float = 1.0,
    brightness_min: float = 0.0,
    brightness_max: float = 1.0,
    original_image: np.ndarray | None = None,
) -> np.ndarray:
    """Convert dithered image to spherical point cloud.
    
    Args:
        dithered: 2D boolean array from dithering.
        radius: Sphere radius.
        invert: If True, black pixels become points instead of white.
        rotate_x: Rotation around X axis in degrees (applied before filtering).
        rotate_y: Rotation around Y axis in degrees (applied before filtering).
        rotate_z: Rotation around Z axis in degrees (applied before filtering).
        height_min: Minimum height as fraction (0=bottom, 1=top). Default 0.
        height_max: Maximum height as fraction (0=bottom, 1=top). Default 1.
        brightness_min: Minimum original brightness to include (0-1). Default 0.
        brightness_max: Maximum original brightness to include (0-1). Default 1.
        original_image: Original grayscale image (uint8) for brightness filtering.
    
    Returns:
        Nx3 array of (x, y, z) point coordinates.
    """
    height, width = dithered.shape
    
    # Get pixel coordinates where we want points
    if invert:
        ys, xs = np.where(~dithered)  # Black pixels
    else:
        ys, xs = np.where(dithered)   # White pixels
    
    # Filter by original brightness if specified
    if original_image is not None and (brightness_min > 0.0 or brightness_max < 1.0):
        brightness = original_image[ys, xs] / 255.0
        mask = (brightness >= brightness_min) & (brightness <= brightness_max)
        ys, xs = ys[mask], xs[mask]
    
    # Convert pixel coords to spherical angles
    # theta: 0 to pi (top to bottom)
    # phi: 0 to 2*pi (left to right)
    theta = (ys / (height - 1)) * np.pi
    phi = (xs / (width - 1)) * 2 * np.pi
    
    # Convert to Cartesian (Y-up convention)
    x = radius * np.sin(theta) * np.cos(phi)
    y = radius * np.cos(theta)  # Y is vertical
    z = radius * np.sin(theta) * np.sin(phi)
    
    points = np.column_stack([x, y, z])
    
    # Apply rotations (before height filtering)
    if rotate_x != 0.0 or rotate_y != 0.0 or rotate_z != 0.0:
        # Convert to radians
        rx, ry, rz = np.radians(rotate_x), np.radians(rotate_y), np.radians(rotate_z)
        
        # Rotation matrices
        # Rx (around X axis)
        cx, sx = np.cos(rx), np.sin(rx)
        Rx = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]])
        
        # Ry (around Y axis)
        cy, sy = np.cos(ry), np.sin(ry)
        Ry = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
        
        # Rz (around Z axis)
        cz, sz = np.cos(rz), np.sin(rz)
        Rz = np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]])
        
        # Combined rotation: first X, then Y, then Z
        R = Rz @ Ry @ Rx
        points = points @ R.T
    
    # Filter by height (Y coordinate)
    # Y ranges from -radius (bottom) to +radius (top)
    # Map height_min/max [0,1] to Y range [-radius, +radius]
    y_min = -radius + height_min * 2 * radius  # 0 -> -radius, 1 -> +radius
    y_max = -radius + height_max * 2 * radius
    
    if height_min > 0.0 or height_max < 1.0:
        mask = (points[:, 1] >= y_min) & (points[:, 1] <= y_max)
        points = points[mask]
    
    return points


def save_ply(points: np.ndarray, output_path: str) -> None:
    """Save point cloud as PLY file.
    
    Args:
        points: Nx3 array of (x, y, z) coordinates.
        output_path: Output file path.
    """
    header = f"""ply
format ascii 1.0
element vertex {len(points)}
property float x
property float y
property float z
end_header
"""
    with open(output_path, "w") as f:
        f.write(header)
        for p in points:
            f.write(f"{p[0]:.6f} {p[1]:.6f} {p[2]:.6f}\n")


def save_xyz(points: np.ndarray, output_path: str) -> None:
    """Save point cloud as simple XYZ file.
    
    Args:
        points: Nx3 array of (x, y, z) coordinates.
        output_path: Output file path.
    """
    np.savetxt(output_path, points, fmt="%.6f", delimiter=" ")


def generate_dither_preview(dithered: np.ndarray, output_path: str) -> None:
    """Save the dithered image as a PNG preview.
    
    Args:
        dithered: 2D boolean array.
        output_path: Output PNG path.
    """
    img = Image.fromarray((dithered * 255).astype(np.uint8), mode="L")
    img.save(output_path)


def panorama_to_pointcloud(
    input_image: str,
    output_path: str,
    radius: float = 50.0,
    max_size: int = 2000,
    invert: bool = False,
    rotate_x: float = 0.0,
    rotate_y: float = 0.0,
    rotate_z: float = 0.0,
    height_min: float = 0.0,
    height_max: float = 1.0,
    brightness_min: float = 0.0,
    brightness_max: float = 1.0,
    preview_dither: str | None = None,
) -> np.ndarray:
    """Full pipeline: load panorama, dither, create spherical point cloud.
    
    Args:
        input_image: Path to equirectangular panorama.
        output_path: Output file path (.ply or .xyz).
        radius: Sphere radius.
        max_size: Maximum image dimension for processing.
        invert: If True, dark areas get points instead of bright.
        rotate_x: Rotation around X axis in degrees.
        rotate_y: Rotation around Y axis in degrees.
        rotate_z: Rotation around Z axis in degrees.
        height_min: Minimum height fraction (0=bottom, 1=top).
        height_max: Maximum height fraction (0=bottom, 1=top).
        brightness_min: Minimum original brightness to include (0-1).
        brightness_max: Maximum original brightness to include (0-1).
        preview_dither: Optional path to save dithered preview PNG.
    
    Returns:
        The generated point cloud as Nx3 array.
    """
    # Load and resize image
    image = load_and_resize(input_image, max_size)
    
    # Apply Floyd-Steinberg dithering
    dithered = floyd_steinberg_dither(image)
    
    # Save dither preview if requested
    if preview_dither:
        generate_dither_preview(dithered, preview_dither)
    
    # Convert to spherical point cloud
    points = dither_to_points_spherical(
        dithered,
        radius=radius,
        invert=invert,
        rotate_x=rotate_x,
        rotate_y=rotate_y,
        rotate_z=rotate_z,
        height_min=height_min,
        height_max=height_max,
        brightness_min=brightness_min,
        brightness_max=brightness_max,
        original_image=image,
    )
    
    # Save based on file extension
    if output_path.lower().endswith(".xyz"):
        save_xyz(points, output_path)
    else:
        save_ply(points, output_path)
    
    return points

