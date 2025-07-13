import os
import sys
import zipfile
import shutil
import json
from PIL import Image

def extract_assets(zip_path, output_dir):
    """Extract and organize assets from dyna.zip"""
    try:
        # Create output directories
        os.makedirs(output_dir, exist_ok=True)
        sprite_dir = os.path.join(output_dir, "sprites")
        tile_dir = os.path.join(output_dir, "tiles")
        sound_dir = os.path.join(output_dir, "sounds")
        os.makedirs(sprite_dir, exist_ok=True)
        os.makedirs(tile_dir, exist_ok=True)
        os.makedirs(sound_dir, exist_ok=True)
        
        # Extract ZIP contents
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(output_dir)
            print(f"Extracted {len(zip_ref.namelist())} files")
        
        # Process files
        asset_index = []
        for root, dirs, files in os.walk(output_dir):
            for file in files:
                file_path = os.path.join(root, file)
                dest_dir = None
                
                # Organize by file type
                if file.endswith(('.pcx', '.bmp', '.img', '.gif')):
                    dest_dir = sprite_dir if "sprite" in file.lower() else tile_dir
                    # Convert to PNG
                    if not file.lower().endswith('.png'):
                        try:
                            img = Image.open(file_path)
                            new_path = os.path.splitext(file_path)[0] + '.png'
                            img.save(new_path)
                            os.remove(file_path)
                            file_path = new_path
                            file = os.path.basename(new_path)
                        except Exception as e:
                            print(f"Couldn't convert {file}: {str(e)}")
                elif file.endswith(('.voc', '.wav', '.aud')):
                    dest_dir = sound_dir
                
                # Move to organized directory
                if dest_dir:
                    new_path = os.path.join(dest_dir, file)
                    shutil.move(file_path, new_path)
                    asset_index.append({
                        "type": os.path.basename(dest_dir)[:-1],
                        "path": os.path.relpath(new_path, output_dir)
                    })
        
        # Create asset manifest
        with open(os.path.join(output_dir, "manifest.json"), 'w') as f:
            json.dump(asset_index, f, indent=2)
            
        print(f"Assets organized in {output_dir}")
        return True
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return False

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python extract_assets.py <zip_path> <output_dir>")
        sys.exit(1)
        
    zip_path = sys.argv[1]
    output_dir = sys.argv[2]
    
    if not os.path.exists(zip_path):
        print(f"Error: File not found - {zip_path}")
        sys.exit(1)
        
    success = extract_assets(zip_path, output_dir)
    sys.exit(0 if success else 1)
