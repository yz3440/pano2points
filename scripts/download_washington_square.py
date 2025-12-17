#!/usr/bin/env python3
"""Download a Google Street View panorama from Washington Square Park.

Usage:
    uv run scripts/download_washington_square.py [output_path] [--no-level] [--zoom LEVEL]

This script uses the streetlevel library to download a specific
panorama from Washington Square Park, NYC (near the arch).
Auto-levels the panorama to correct pitch and roll.
"""

import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from streetlevel import streetview

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from pano2points.converter import level_panorama


# Specific panorama ID from Google Maps URL
PANORAMA_ID = "eKHNUWxhdsVMzC9kQyaNuQ"

# Zoom levels: 0=512x256, 1=1024x512, 2=2048x1024, 3=4096x2048, 4=8192x4096, 5=16384x8192
DEFAULT_ZOOM = 3  # 4096x2048 for faster testing


def download_panorama(
    pano_id: str, output_path: Path, auto_level: bool = True, zoom: int = DEFAULT_ZOOM
) -> bool:
    """Download a specific Street View panorama by ID.

    Args:
        pano_id: Google Street View panorama ID.
        output_path: Path to save the panorama image.
        auto_level: If True, correct pitch and roll.
        zoom: Resolution level 0-5 (0=512x256, 5=16384x8192).

    Returns:
        True if successful, False otherwise.
    """
    print(f"Fetching panorama: {pano_id}")

    pano = streetview.find_panorama_by_id(pano_id)

    if pano is None:
        print("Panorama not found.")
        return False

    print(f"Found panorama: {pano.id}")
    print(f"  Date: {pano.date}")
    print(f"  Location: ({pano.lat}, {pano.lon})")
    print(f"  Pitch: {pano.pitch:.4f} rad ({np.degrees(pano.pitch):.2f}°)")
    print(f"  Roll: {pano.roll:.4f} rad ({np.degrees(pano.roll):.2f}°)")
    print(f"  Heading: {pano.heading:.4f} rad ({np.degrees(pano.heading):.2f}°)")

    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Downloading panorama (zoom level {zoom})...")
    image = streetview.get_panorama(pano, zoom=zoom)

    if auto_level:
        # Normalize roll to [-pi, pi] range
        roll = pano.roll
        if roll > np.pi:
            roll = roll - 2 * np.pi

        print(
            f"Leveling panorama (correcting pitch={np.degrees(pano.pitch):.2f}°, roll={np.degrees(roll):.2f}°)..."
        )

        # Convert to numpy array for processing
        img_array = np.array(image)

        # Apply leveling correction
        leveled = level_panorama(
            img_array,
            pitch=pano.pitch,
            roll=roll,
            heading=0,  # Don't correct heading, keep original orientation
        )

        # Convert back to PIL Image
        image = Image.fromarray(leveled)
        print("  Panorama leveled!")

    # Save image
    image.save(output_path, quality=95)
    print(f"Panorama saved: {output_path}")
    print(f"  Size: {image.width}x{image.height}")

    # Save metadata
    metadata_path = output_path.with_suffix(".json")
    metadata = {
        "id": pano.id,
        "date": str(pano.date),
        "lat": pano.lat,
        "lon": pano.lon,
        "pitch": pano.pitch,
        "roll": pano.roll,
        "heading": pano.heading,
        "elevation": pano.elevation,
        "auto_leveled": auto_level,
    }
    with open(metadata_path, "w") as f:
        json.dump(metadata, f, indent=2)
    print(f"Metadata saved: {metadata_path}")

    return True


def main() -> int:
    """Main entry point."""
    # Parse arguments
    args = sys.argv[1:]
    auto_level = "--no-level" not in args
    args = [a for a in args if a != "--no-level"]

    # Parse --zoom argument
    zoom = DEFAULT_ZOOM
    for i, arg in enumerate(args):
        if arg == "--zoom" and i + 1 < len(args):
            zoom = int(args[i + 1])
            args = args[:i] + args[i + 2 :]
            break

    if args:
        output_path = Path(args[0])
    else:
        output_path = Path("data/washington_square.jpg")

    success = download_panorama(
        PANORAMA_ID, output_path, auto_level=auto_level, zoom=zoom
    )

    if success:
        print("\nYou can now convert this to a point cloud:")
        print(f"  uv run pano2points {output_path} --preview")

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
