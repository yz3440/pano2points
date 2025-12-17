"""Panorama leveling utilities."""

import numpy as np


def level_panorama(
    image: np.ndarray,
    pitch: float = 0.0,
    roll: float = 0.0,
    heading: float = 0.0,
) -> np.ndarray:
    """Correct pitch, roll, and heading of an equirectangular panorama.

    Applies rotation to level the horizon and optionally correct heading.

    Args:
        image: 2D grayscale array (or 3D color array).
        pitch: Camera pitch in radians (positive = looking up).
        roll: Camera roll in radians (positive = tilted clockwise when looking forward).
        heading: Camera heading in radians (rotation around vertical axis).

    Returns:
        Corrected equirectangular image.
    """
    if abs(pitch) < 0.001 and abs(roll) < 0.001 and abs(heading) < 0.001:
        return image  # No correction needed

    height, width = image.shape[:2]
    is_color = len(image.shape) == 3

    # Create output coordinate grid
    v, u = np.meshgrid(np.arange(height), np.arange(width), indexing="ij")

    # Convert output pixel coords to spherical angles
    # theta: 0 at top (north pole), pi at bottom (south pole)
    # phi: 0 at left, 2*pi at right
    theta_out = (v / (height - 1)) * np.pi
    phi_out = (u / (width - 1)) * 2 * np.pi

    # Convert to 3D Cartesian (Y-up, phi=0 -> +X, center phi=pi -> -X)
    x = np.sin(theta_out) * np.cos(phi_out)
    y = np.cos(theta_out)
    z = np.sin(theta_out) * np.sin(phi_out)

    # To find where in the INPUT image to sample, we apply the INVERSE of
    # the camera's rotation. For each corrected output direction, we find
    # where that point appeared in the original tilted view.

    # Use negative angles to invert the rotations
    # Heading rotation (around Y axis)
    ch, sh = np.cos(-heading), np.sin(-heading)
    # Pitch rotation (around Z axis in our coords)
    cp, sp = np.cos(-pitch), np.sin(-pitch)
    # Roll rotation (around X axis)
    cr, sr = np.cos(roll), np.sin(roll)

    # Apply heading (around Y): rotates X toward Z
    x1 = ch * x + sh * z
    y1 = y
    z1 = -sh * x + ch * z

    # Apply pitch (around Z): rotates X toward Y (looking up moves horizon down)
    x2 = cp * x1 - sp * y1
    y2 = sp * x1 + cp * y1
    z2 = z1

    # Apply roll (around X): rotates Y toward Z
    x3 = x2
    y3 = cr * y2 - sr * z2
    z3 = sr * y2 + cr * z2

    # Convert back to spherical coordinates
    theta_in = np.arccos(np.clip(y3, -1, 1))
    phi_in = np.arctan2(z3, x3)
    phi_in = np.mod(phi_in, 2 * np.pi)  # Ensure [0, 2*pi]

    # Convert to input pixel coordinates
    v_in = theta_in / np.pi * (height - 1)
    u_in = phi_in / (2 * np.pi) * (width - 1)

    # Bilinear interpolation
    v0 = np.floor(v_in).astype(int)
    v1 = np.minimum(v0 + 1, height - 1)
    u0 = np.floor(u_in).astype(int)
    u1 = np.mod(u0 + 1, width)  # Wrap horizontally

    wv = v_in - v0
    wu = u_in - u0

    if is_color:
        wv = wv[:, :, np.newaxis]
        wu = wu[:, :, np.newaxis]
        result = (
            image[v0, u0] * (1 - wu) * (1 - wv)
            + image[v0, u1] * wu * (1 - wv)
            + image[v1, u0] * (1 - wu) * wv
            + image[v1, u1] * wu * wv
        )
    else:
        result = (
            image[v0, u0] * (1 - wu) * (1 - wv)
            + image[v0, u1] * wu * (1 - wv)
            + image[v1, u0] * (1 - wu) * wv
            + image[v1, u1] * wu * wv
        )

    return result.astype(image.dtype)
