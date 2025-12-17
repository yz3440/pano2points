"""Command-line interface for panorama to point cloud conversion."""

import argparse
import sys
from pathlib import Path

from .pointcloud import panorama_to_pointcloud


def main() -> int:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="pano2points",
        description="Convert panorama to dithered spherical point cloud for laser engraving.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    
    parser.add_argument(
        "input",
        type=str,
        help="Path to input equirectangular panorama image.",
    )
    
    parser.add_argument(
        "-o", "--output",
        type=str,
        default=None,
        help="Output file path (.ply or .xyz). Defaults to input name with .ply extension.",
    )
    
    parser.add_argument(
        "-r", "--radius",
        type=float,
        default=50.0,
        help="Sphere radius in mm.",
    )
    
    parser.add_argument(
        "--max-size",
        type=int,
        default=2000,
        help="Maximum image dimension. Larger = more points but slower.",
    )
    
    parser.add_argument(
        "--invert",
        action="store_true",
        help="Invert: dark areas get points instead of bright areas.",
    )
    
    parser.add_argument(
        "--rotate-x",
        type=float,
        default=0.0,
        help="Rotation around X axis in degrees (applied before height filter).",
    )
    
    parser.add_argument(
        "--rotate-y",
        type=float,
        default=0.0,
        help="Rotation around Y axis in degrees (applied before height filter).",
    )
    
    parser.add_argument(
        "--rotate-z",
        type=float,
        default=0.0,
        help="Rotation around Z axis in degrees (applied before height filter).",
    )
    
    parser.add_argument(
        "--height-min",
        type=float,
        default=0.0,
        help="Minimum height as fraction (0=bottom, 1=top). Use to slice the sphere.",
    )
    
    parser.add_argument(
        "--height-max",
        type=float,
        default=1.0,
        help="Maximum height as fraction (0=bottom, 1=top). Use to slice the sphere.",
    )
    
    parser.add_argument(
        "--brightness-min",
        type=float,
        default=0.0,
        help="Minimum original brightness to include (0-1). Filter by source pixel brightness.",
    )
    
    parser.add_argument(
        "--brightness-max",
        type=float,
        default=1.0,
        help="Maximum original brightness to include (0-1). Filter by source pixel brightness.",
    )
    
    parser.add_argument(
        "--preview",
        action="store_true",
        help="Generate dithered image preview.",
    )
    
    parser.add_argument(
        "--preview-dither",
        type=str,
        default=None,
        help="Custom path for dithered preview PNG.",
    )
    
    args = parser.parse_args()
    
    # Validate input
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: Input file not found: {args.input}", file=sys.stderr)
        return 1
    
    # Determine output path
    if args.output:
        output_path = args.output
    else:
        output_path = str(input_path.with_suffix(".ply"))
    
    # Handle preview
    preview_dither = args.preview_dither
    if args.preview and not preview_dither:
        base = Path(output_path).stem
        parent = Path(output_path).parent
        preview_dither = str(parent / f"{base}_dithered.png")
    
    print(f"Loading panorama: {args.input}")
    print(f"Parameters: radius={args.radius}mm, max_size={args.max_size}px")
    if args.invert:
        print("Mode: Inverted (dark areas → points)")
    else:
        print("Mode: Normal (bright areas → points)")
    
    if args.rotate_x != 0.0 or args.rotate_y != 0.0 or args.rotate_z != 0.0:
        print(f"Rotation: X={args.rotate_x}°, Y={args.rotate_y}°, Z={args.rotate_z}°")
    
    if args.height_min > 0.0 or args.height_max < 1.0:
        print(f"Height range: {args.height_min:.0%} - {args.height_max:.0%}")
    
    if args.brightness_min > 0.0 or args.brightness_max < 1.0:
        print(f"Brightness range: {args.brightness_min:.0%} - {args.brightness_max:.0%}")
    
    try:
        points = panorama_to_pointcloud(
            input_image=args.input,
            output_path=output_path,
            radius=args.radius,
            max_size=args.max_size,
            invert=args.invert,
            rotate_x=args.rotate_x,
            rotate_y=args.rotate_y,
            rotate_z=args.rotate_z,
            height_min=args.height_min,
            height_max=args.height_max,
            brightness_min=args.brightness_min,
            brightness_max=args.brightness_max,
            preview_dither=preview_dither,
        )
    except Exception as e:
        print(f"Error during conversion: {e}", file=sys.stderr)
        return 1
    
    print(f"Generated {len(points):,} points")
    print(f"Point cloud saved to: {output_path}")
    
    if preview_dither:
        print(f"Dither preview saved to: {preview_dither}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

