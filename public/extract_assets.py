import os
import sys
import zipfile
import shutil
import json
import argparse
from PIL import Image
from tqdm import tqdm  # For progress bars
import traceback

# Error handling class
class AssetExtractionError(Exception):
    pass

# Safe move function to handle filename conflicts
def safe_move(src, dst):
    """Move file with conflict resolution"""
    if not os.path.exists(dst):
        shutil.move(src, dst)
        return dst
        
    base, ext = os.path.splitext(os.path.basename(src))
    counter = 1
    while True:
        new_name = f"{base}_{counter}{ext}"
        new_path = os.path.join(os.path.dirname(dst), new_name)
        if not os.path.exists(new_path):
            shutil.move(src, new_path)
            return new_path
        counter += 1

# Check for safe extraction paths to prevent path traversal
def is_safe_path(basedir, path):
    basedir = os.path.abspath(basedir)
    path = os.path.abspath(path)
    return path.startswith(basedir)

def extract_assets(zip_path, output_dir, convert_images=True, organize_files=True):
    """Extract and organize assets from game archive"""
    try:
        print(f"🔧 Starting asset extraction from {zip_path}")
        
        # Validate paths
        if not os.path.exists(zip_path):
            raise FileNotFoundError(f"ZIP file not found: {zip_path}")
        
        # Create output directories
        os.makedirs(output_dir, exist_ok=True)
        sprite_dir = os.path.join(output_dir, "sprites")
        tile_dir = os.path.join(output_dir, "tiles")
        sound_dir = os.path.join(output_dir, "sounds")
        other_dir = os.path.join(output_dir, "other")
        
        if organize_files:
            os.makedirs(sprite_dir, exist_ok=True)
            os.makedirs(tile_dir, exist_ok=True)
            os.makedirs(sound_dir, exist_ok=True)
            os.makedirs(other_dir, exist_ok=True)
        
        # Extract ZIP contents with progress bar
        extracted_files = []
        print(f"📦 Extracting archive contents...")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            file_list = zip_ref.namelist()
            for file in tqdm(file_list, desc="Extracting"):
                # Prevent path traversal by ensuring the extracted file is within output_dir
                dest_path = os.path.join(output_dir, file)
                if not is_safe_path(output_dir, dest_path):
                    print(f"⛔ Blocked unsafe extraction: {file}")
                    continue
                    
                zip_ref.extract(file, output_dir)
                extracted_files.append(dest_path)
        
        print(f"✅ Extracted {len(extracted_files)} files")

        # Process files
        asset_index = []
        conversion_stats = {"converted": 0, "skipped": 0, "failed": 0}
        MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10 MB
        
        print("🔄 Processing assets...")
        for file_path in tqdm(extracted_files, desc="Processing"):
            if not os.path.isfile(file_path):
                continue
                
            filename = os.path.basename(file_path)
            dest_dir = other_dir
            file_ext = os.path.splitext(filename)[1].lower()
            original_path = file_path  # Keep track of original path for manifest
            
            # Skip large images to avoid memory issues
            if file_ext in ('.pcx', '.bmp', '.img', '.gif', '.png') and convert_images:
                if os.path.getsize(file_path) > MAX_IMAGE_SIZE:
                    print(f"⛔ Skipping large image: {filename} ({os.path.getsize(file_path)/1024/1024:.2f}MB)")
                    conversion_stats["skipped"] += 1
                    continue
                
            # Process images
            if file_ext in ('.pcx', '.bmp', '.img', '.gif') and convert_images:
                try:
                    # Convert to PNG
                    if file_ext != '.png':
                        with Image.open(file_path) as img:
                            new_path = os.path.splitext(file_path)[0] + '.png'
                            
                            # Preserve transparency if available
                            if img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info):
                                img = img.convert('RGBA')
                            else:
                                img = img.convert('RGB')
                                
                            img.save(new_path)
                            os.remove(file_path)
                            file_path = new_path
                            filename = os.path.basename(new_path)
                            conversion_stats["converted"] += 1
                        # Update extension after conversion
                        file_ext = '.png'
                    else:
                        conversion_stats["skipped"] += 1
                except Exception as e:
                    conversion_stats["failed"] += 1
                    print(f"⚠️ Couldn't convert {filename}: {str(e)}")
                    # Print traceback for debugging
                    traceback.print_exc()
            
            # Organize files
            if organize_files:
                if file_ext in ('.png', '.jpg', '.jpeg', '.gif'):
                    if "sprite" in filename.lower():
                        dest_dir = sprite_dir
                    elif "tile" in filename.lower() or "background" in filename.lower():
                        dest_dir = tile_dir
                    else:
                        # Try to auto-classify by dimensions
                        try:
                            with Image.open(file_path) as img:
                                w, h = img.size
                                if w <= 64 and h <= 64:  # Likely sprite
                                    dest_dir = sprite_dir
                                elif w >= 128 or h >= 128:  # Likely background/tile
                                    dest_dir = tile_dir
                        except:
                            pass
                elif file_ext in ('.voc', '.wav', '.aud', '.mp3', '.ogg'):
                    dest_dir = sound_dir
                
                # Move to organized directory if not already there
                dest_path = os.path.join(dest_dir, filename)
                if file_path != dest_path:
                    file_path = safe_move(file_path, dest_path)
            
            # Add to manifest
            asset_type = "other"
            if file_path.startswith(sprite_dir):
                asset_type = "sprite"
            elif file_path.startswith(tile_dir):
                asset_type = "tile"
            elif file_path.startswith(sound_dir):
                asset_type = "sound"
                
            asset_index.append({
                "type": asset_type,
                "path": os.path.relpath(file_path, output_dir),
                "filename": filename,
                "original_path": os.path.relpath(original_path, output_dir),  # original path might be different
                "format": file_ext[1:] if file_ext else ""  # Remove dot if exists
            })
        
        # Clean up empty directories
        print("🧹 Cleaning up empty directories...")
        for root, dirs, files in os.walk(output_dir, topdown=False):
            for dir in dirs:
                dir_path = os.path.join(root, dir)
                if not os.listdir(dir_path):
                    os.rmdir(dir_path)
        
        # Create asset manifest
        manifest_path = os.path.join(output_dir, "manifest.json")
        with open(manifest_path, 'w') as f:
            json.dump({
                "assets": asset_index,
                "stats": {
                    "total_files": len(extracted_files),
                    "images_converted": conversion_stats["converted"],
                    "images_failed": conversion_stats["failed"],
                    "images_skipped": conversion_stats["skipped"]
                }
            }, f, indent=2)
            
        print(f"🎉 Assets successfully organized in {output_dir}")
        print(f"📄 Manifest created at {manifest_path}")
        print(f"📊 Conversion stats: {conversion_stats}")
        return True
        
    except Exception as e:
        # Print the traceback for debugging
        traceback.print_exc()
        raise AssetExtractionError(f"Critical error: {str(e)}")

def main():
    parser = argparse.ArgumentParser(description='Extract and organize game assets')
    parser.add_argument('zip_path', help='Path to game archive (ZIP file)')
    parser.add_argument('output_dir', help='Output directory for extracted assets')
    parser.add_argument('--no-convert', action='store_false', dest='convert_images',
                        help='Skip image conversion to PNG')
    parser.add_argument('--no-organize', action='store_false', dest='organize_files',
                        help='Skip file organization')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.zip_path):
        print(f"❌ Error: File not found - {args.zip_path}")
        sys.exit(1)
        
    try:
        success = extract_assets(
            args.zip_path, 
            args.output_dir,
            convert_images=args.convert_images,
            organize_files=args.organize_files
        )
        sys.exit(0 if success else 1)
    except AssetExtractionError as e:
        print(f"❌ {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
