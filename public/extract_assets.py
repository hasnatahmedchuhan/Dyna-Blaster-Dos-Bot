import os
import sys
import zipfile
import shutil
import json
import argparse
from PIL import Image
from tqdm import tqdm

class AssetExtractionError(Exception):
    pass

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

def extract_assets(zip_path, output_dir, convert_images=True, organize_files=True):
    try:
        print(f"🔧 Starting asset extraction from {zip_path}")
        
        # Validate paths
        if not os.path.exists(zip_path):
            raise FileNotFoundError(f"ZIP file not found: {zip_path}")
        
        os.makedirs(output_dir, exist_ok=True)
        
        # Setup directories
        dirs = {
            "sprites": os.path.join(output_dir, "sprites"),
            "tiles": os.path.join(output_dir, "tiles"),
            "sounds": os.path.join(output_dir, "sounds"),
            "other": os.path.join(output_dir, "other")
        }
        
        if organize_files:
            for d in dirs.values():
                os.makedirs(d, exist_ok=True)
        
        # Extract archive
        extracted_files = []
        print(f"📦 Extracting archive...")
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                for file in tqdm(zip_ref.namelist(), desc="Extracting"):
                    zip_ref.extract(file, output_dir)
                    extracted_files.append(os.path.join(output_dir, file))
        except zipfile.BadZipFile:
            raise AssetExtractionError("Invalid ZIP file format")

        print(f"✅ Extracted {len(extracted_files)} files")

        # Process files
        asset_index = []
        conversion_stats = {"converted": 0, "skipped": 0, "failed": 0}
        
        print("🔄 Processing assets...")
        for file_path in tqdm(extracted_files, desc="Processing"):
            if not os.path.isfile(file_path):
                continue
                
            filename = os.path.basename(file_path)
            dest_dir = dirs["other"]
            file_ext = os.path.splitext(filename)[1].lower()
            original_path = file_path
            
            # Image conversion
            if file_ext in ('.pcx', '.bmp', '.img', '.gif') and convert_images:
                try:
                    if file_ext != '.png':
                        with Image.open(file_path) as img:
                            new_path = os.path.splitext(file_path)[0] + '.png'
                            if img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info):
                                img = img.convert('RGBA')
                            else:
                                img = img.convert('RGB')
                            img.save(new_path)
                            os.remove(file_path)
                            file_path = new_path
                            filename = os.path.basename(new_path)
                            conversion_stats["converted"] += 1
                        file_ext = '.png'
                    else:
                        conversion_stats["skipped"] += 1
                except Exception as e:
                    conversion_stats["failed"] += 1
                    print(f"⚠️ Conversion failed for {filename}: {str(e)}")
            
            # File organization
            if organize_files:
                if file_ext in ('.png', '.jpg', '.jpeg', '.gif'):
                    if "sprite" in filename.lower():
                        dest_dir = dirs["sprites"]
                    elif "tile" in filename.lower() or "background" in filename.lower():
                        dest_dir = dirs["tiles"]
                    else:
                        try:
                            with Image.open(file_path) as img:
                                w, h = img.size
                                if w <= 64 and h <= 64:
                                    dest_dir = dirs["sprites"]
                                elif w >= 128 or h >= 128:
                                    dest_dir = dirs["tiles"]
                        except Exception:
                            pass
                elif file_ext in ('.voc', '.wav', '.aud', '.mp3', '.ogg'):
                    dest_dir = dirs["sounds"]
                
                # Handle filename conflicts
                dest_path = os.path.join(dest_dir, filename)
                if file_path != dest_path:
                    file_path = safe_move(file_path, dest_path)

            # Add to manifest
            asset_type = "other"
            for t, path in dirs.items():
                if path == os.path.dirname(file_path):
                    asset_type = t
                    break
                    
            asset_index.append({
                "type": asset_type,
                "path": os.path.relpath(file_path, output_dir),
                "filename": filename,
                "original_path": os.path.relpath(original_path, output_dir),
                "format": file_ext[1:] if file_ext else ""
            })
        
        # Cleanup empty directories
        for root, dirs, files in os.walk(output_dir, topdown=False):
            for name in dirs:
                dir_path = os.path.join(root, name)
                if not os.listdir(dir_path):
                    os.rmdir(dir_path)
        
        # Create manifest
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
            
        print(f"🎉 Success! Assets organized in {output_dir}")
        print(f"📄 Manifest: {manifest_path}")
        return True
        
    except Exception as e:
        raise AssetExtractionError(f"Extraction failed: {str(e)}")

def main():
    parser = argparse.ArgumentParser(description='Game Asset Extractor')
    parser.add_argument('zip_path', help='Path to game archive (ZIP)')
    parser.add_argument('output_dir', help='Output directory')
    parser.add_argument('--no-convert', action='store_false', dest='convert_images',
                        help='Disable image conversion')
    parser.add_argument('--no-organize', action='store_false', dest='organize_files',
                        help='Disable file organization')
    
    args = parser.parse_args()
    
    try:
        extract_assets(
            args.zip_path, 
            args.output_dir,
            convert_images=args.convert_images,
            organize_files=args.organize_files
        )
    except AssetExtractionError as e:
        print(f"❌ {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
