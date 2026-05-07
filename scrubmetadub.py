import argparse
import os
import sys
import subprocess
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk
import threading
import zipfile
from datetime import datetime
import json
import urllib.request
import webbrowser
import random

# Dependency Management
HAS_PILLOW = False
HAS_PIKEPDF = False
HAS_TKINTERDND2 = False
HAS_REPORTLAB = False

try:
    import winreg
except ImportError:
    winreg = None

try:
    from PIL import Image, ExifTags, ImageOps, ImageDraw, ImageFont, ImageTk
    HAS_PILLOW = True
except ImportError:
    Image = None

try:
    import pikepdf
    HAS_PIKEPDF = True
except ImportError:
    pikepdf = None

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    HAS_TKINTERDND2 = True
except ImportError:
    TkinterDnD = None

try:
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter
    HAS_REPORTLAB = True
except ImportError:
    pass

CONFIG_FILE = "scrub_config.json"
VERSION = "1.1.0"
UPDATE_URL = "https://raw.githubusercontent.com/hakthegeek/scrubmetadub/main/version.txt"

def get_exif_data(img):
    """Extracts readable metadata from the image."""
    meta_dict = {}
    
    # Basic EXIF data
    exif = img.getexif()
    if exif:
        for tag_id, value in exif.items():
            tag = ExifTags.TAGS.get(tag_id, tag_id)
            # Truncate long binary data for display
            val_str = str(value)
            if len(val_str) > 50: val_str = val_str[:50] + "..."
            meta_dict[tag] = val_str
    
    # Additional metadata (like PNG info)
    for k, v in img.info.items():
        if k != 'exif': # Avoid duplicating raw exif bytes
            val_str = str(v)
            if len(val_str) > 50: val_str = val_str[:50] + "..."
            meta_dict[k] = val_str
            
    return meta_dict

def get_hex_dump(filepath, length=512):
    try:
        with open(filepath, 'rb') as f:
            data = f.read(length)
        
        lines = []
        for i in range(0, len(data), 16):
            chunk = data[i:i+16]
            hex_part = ' '.join(f"{b:02X}" for b in chunk)
            text_part = ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)
            lines.append(f"{i:08X}  {hex_part:<47}  {text_part}")
            
        return "\n".join(lines)
    except Exception as e:
        return f"Error reading file: {e}"

def generate_default_icon():
    if os.path.exists("icon.ico") or not HAS_PILLOW: return
    try:
        # Create a 256x256 icon
        img = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        
        # Draw background (File/Data)
        draw.rectangle([30, 30, 226, 226], fill=(40, 40, 40, 255), outline=(100, 100, 100, 255), width=4)
        
        # Draw Binary Text
        try:
            font = ImageFont.truetype("arial.ttf", 50)
        except IOError:
            font = ImageFont.load_default()
            
        draw.text((50, 50), "10110", fill=(0, 255, 0, 255), font=font)
        draw.text((50, 110), "01001", fill=(0, 255, 0, 255), font=font)
        draw.text((50, 170), "11100", fill=(0, 255, 0, 255), font=font)
        
        # Draw Sponge (Wiping bottom right)
        draw.rectangle([120, 120, 256, 256], fill=(255, 220, 0, 255), outline=(200, 180, 0, 255), width=3)
        
        # Sponge Pores
        for _ in range(20):
            x = random.randint(130, 240)
            y = random.randint(130, 240)
            s = random.randint(5, 15)
            draw.ellipse([x, y, x+s, y+s], fill=(200, 180, 0, 255))
            
        # Bubbles
        for _ in range(5):
            x = random.randint(100, 250)
            y = random.randint(100, 150)
            s = random.randint(10, 25)
            draw.ellipse([x, y, x+s, y+s], fill=(200, 230, 255, 200))

        img.save("icon.ico", format="ICO", sizes=[(256, 256)])
    except Exception as e:
        print(f"[-] Icon generation failed: {e}")

def generate_pdf_report(filename, session_data):
    if not HAS_REPORTLAB:
        print("ReportLab not installed. Cannot generate PDF report.")
        return
    
    try:
        c = canvas.Canvas(filename, pagesize=letter)
        width, height = letter
        y = height - 50
        
        c.setFont("Helvetica-Bold", 16)
        c.drawString(50, y, "ScrubMetaDub Session Report")
        y -= 30
        c.setFont("Helvetica", 10)
        c.drawString(50, y, f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        y -= 20
        
        c.line(50, y, width - 50, y)
        y -= 20
        
        for item in session_data:
            if y < 50:
                c.showPage()
                y = height - 50
                
            status = item['status']
            file_name = os.path.basename(item['file'])
            details = item['details']
            
            color = (0, 0.5, 0) if status == "Success" else (0.8, 0, 0)
            c.setFillColorRGB(*color)
            c.setFont("Helvetica-Bold", 10)
            c.drawString(50, y, f"[{status}] {file_name}")
            c.setFillColorRGB(0, 0, 0)
            c.setFont("Helvetica", 9)
            c.drawString(200, y, details[:80] + ("..." if len(details) > 80 else ""))
            y -= 15
        c.save()
    except Exception as e:
        print(f"Error generating PDF report: {e}")

def perform_backup(filepath, backup_zip, log_func=print):
    try:
        with zipfile.ZipFile(backup_zip, 'a', zipfile.ZIP_DEFLATED) as zf:
            zf.write(filepath, arcname=os.path.basename(filepath))
        log_func(f"    [+] Backed up to: {os.path.basename(backup_zip)}")
    except Exception as e:
        log_func(f"    [!] Backup failed: {e}")

def apply_watermark(image, text):
    # Convert to RGBA to support transparency for the watermark
    base = image.convert("RGBA")
    txt_layer = Image.new("RGBA", base.size, (255, 255, 255, 0))
    
    try:
        # Calculate font size based on image height (5%)
        font_size = int(min(base.size) * 0.05)
        if font_size < 10: font_size = 10
        font = ImageFont.truetype("arial.ttf", font_size)
    except IOError:
        font = ImageFont.load_default()
        
    draw = ImageDraw.Draw(txt_layer)
    bbox = draw.textbbox((0, 0), text, font=font)
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]
        
    # Position bottom-right with padding
    x = base.width - w - 20
    y = base.height - h - 20
    
    # Draw white text with 50% opacity
    draw.text((x, y), text, font=font, fill=(255, 255, 255, 128))
    
    return Image.alpha_composite(base, txt_layer)

def scrub_pdf(filepath, overwrite=False, log_func=print, output_dir=None, prefix="", suffix="", delete_original=False, backup_zip=None, preserve_timestamp=False, remove_tags=None, verify=False, watermark_text=None, resize=None, convert_to=None, export_metadata=False, report_data=None):
    if not pikepdf:
        log_func(f"[!] pikepdf not installed. Cannot process PDF: {filepath}")
        log_func("    Run: pip install pikepdf")
        return (0, 1)

    try:
        file_stats = os.stat(filepath)
        original_size = file_stats.st_size
        if backup_zip: perform_backup(filepath, backup_zip, log_func)
        
        if remove_tags:
            log_func("    [!] Selective scrubbing not supported for PDF. Performing full scrub.")

        if watermark_text:
            log_func("    [!] Watermarking not supported for PDF files.")
            
        if resize or convert_to:
            log_func("    [!] Resize/Convert not supported for PDF files.")
            
        log_func(f"[*] Processing PDF: {filepath}")
        pdf = pikepdf.open(filepath)
        
        if export_metadata:
            directory = output_dir if output_dir else os.path.dirname(filepath)
            if not os.path.exists(directory):
                os.makedirs(directory, exist_ok=True)
            
            filename = os.path.basename(filepath)
            base_name = os.path.splitext(filename)[0]
            
            if overwrite:
                 meta_out_path = os.path.join(directory, f"{base_name}_metadata.txt")
            else:
                 is_same_dir = os.path.abspath(directory) == os.path.abspath(os.path.dirname(filepath))
                 eff_suffix = suffix if suffix else ("_scrubbed" if is_same_dir and not prefix else "")
                 meta_out_path = os.path.join(directory, f"{prefix}{base_name}{eff_suffix}_metadata.txt")

            try:
                with open(meta_out_path, "w", encoding="utf-8") as f:
                    if pdf.docinfo:
                        for k, v in pdf.docinfo.items():
                            f.write(f"{k}: {v}\n")
                    else:
                        f.write("No metadata found.")
                log_func(f"    [+] Metadata exported: {os.path.basename(meta_out_path)}")
            except Exception as e:
                log_func(f"    [!] Metadata export failed: {e}")

        # Check metadata
        if pdf.docinfo:
            log_func(f"    [!] Metadata detected ({len(pdf.docinfo)} items):")
            for k, v in list(pdf.docinfo.items())[:5]:
                log_func(f"        - {k}: {v}")
        
        # Scrubbing: Remove XMP and DocInfo
        if '/Metadata' in pdf.root:
            del pdf.root['/Metadata']
        if '/Info' in pdf.trailer:
            del pdf.trailer['/Info']

        # Save
        if overwrite:
            out_path = filepath
        else:
            directory = output_dir if output_dir else os.path.dirname(filepath)
            if not os.path.exists(directory):
                os.makedirs(directory, exist_ok=True)
                
            filename = os.path.basename(filepath)
            base, ext = os.path.splitext(filepath)
            
            is_same_dir = os.path.abspath(directory) == os.path.abspath(os.path.dirname(filepath))
            eff_suffix = suffix if suffix else ("_scrubbed" if is_same_dir and not prefix else "")
            
            out_path = os.path.join(directory, f"{prefix}{base}{eff_suffix}{ext}")
        
        pdf.save(out_path)
        log_func(f"    [+] Scrubbed PDF saved to: {out_path}")

        if verify:
            try:
                v_pdf = pikepdf.open(out_path)
                has_meta = False
                if v_pdf.docinfo: has_meta = True
                if '/Metadata' in v_pdf.root: has_meta = True
                
                if has_meta:
                    log_func("    [!] Verification Failed: Metadata still detected.")
                else:
                    log_func("    [+] Verification Successful: No metadata found.")
            except Exception as e:
                log_func(f"    [!] Verification Error: {e}")
        
        new_size = os.path.getsize(out_path)
        log_func(f"    [i] Size: {original_size:,} -> {new_size:,} bytes (Saved {original_size - new_size:,} bytes)")

        if preserve_timestamp:
            os.utime(out_path, (file_stats.st_atime, file_stats.st_mtime))
            log_func("    [i] Timestamps preserved.")
        
        if delete_original and os.path.abspath(filepath) != os.path.abspath(out_path):
            try:
                os.remove(filepath)
                log_func(f"    [+] Deleted original file: {filepath}")
            except Exception as e:
                log_func(f"    [!] Failed to delete original: {e}")
                
        log_func("-" * 40)
        if report_data is not None:
            report_data.append({"file": filepath, "status": "Success", "details": f"Saved to {os.path.basename(out_path)}"})
        return (1, 0)
    except Exception as e:
        log_func(f"[!] Error processing PDF {filepath}: {e}")
        if report_data is not None:
            report_data.append({"file": filepath, "status": "Failed", "details": str(e)})
        return (0, 1)

def scrub_file(filepath, overwrite=False, log_func=print, output_dir=None, prefix="", suffix="", delete_original=False, backup_zip=None, preserve_timestamp=False, remove_tags=None, verify=False, watermark_text=None, resize=None, convert_to=None, export_metadata=False, report_data=None):
    if os.path.isdir(filepath):
        return scrub_folder(filepath, overwrite, log_func, output_dir, prefix, suffix, delete_original, backup_zip, preserve_timestamp, remove_tags, verify, watermark_text, resize, convert_to, export_metadata, report_data)

    if filepath.lower().endswith('.pdf'):
        return scrub_pdf(filepath, overwrite, log_func, output_dir, prefix, suffix, delete_original, backup_zip, preserve_timestamp, remove_tags, verify, watermark_text, resize, convert_to, export_metadata, report_data)

    if not HAS_PILLOW:
        log_func(f"[!] Pillow library missing. Cannot process image: {filepath}")
        return (0, 1)

    try:
        file_stats = os.stat(filepath)
        original_size = file_stats.st_size
        if backup_zip: perform_backup(filepath, backup_zip, log_func)
        log_func(f"[*] Processing: {filepath}")
        original_img = Image.open(filepath)
        
        # 1. Check & Print Metadata
        meta = get_exif_data(original_img)
        if meta:
            log_func(f"    [!] Metadata detected ({len(meta)} items):")
            for k, v in list(meta.items())[:5]: # Show first 5 items
                log_func(f"        - {k}: {v}")
            if len(meta) > 5:
                log_func(f"        - ... and {len(meta)-5} more.")
        else:
            log_func("    [-] No significant metadata found.")

        if export_metadata:
            directory = output_dir if output_dir else os.path.dirname(filepath)
            if not os.path.exists(directory):
                os.makedirs(directory, exist_ok=True)
            
            filename = os.path.basename(filepath)
            base_name = os.path.splitext(filename)[0]
            
            if overwrite:
                 meta_out_path = os.path.join(directory, f"{base_name}_metadata.txt")
            else:
                 is_same_dir = os.path.abspath(directory) == os.path.abspath(os.path.dirname(filepath))
                 eff_suffix = suffix if suffix else ("_scrubbed" if is_same_dir and not prefix and not convert_to else "")
                 meta_out_path = os.path.join(directory, f"{prefix}{base_name}{eff_suffix}_metadata.txt")

            try:
                with open(meta_out_path, "w", encoding="utf-8") as f:
                    if meta:
                        for k, v in meta.items():
                            f.write(f"{k}: {v}\n")
                    else:
                        f.write("No metadata found.")
                log_func(f"    [+] Metadata exported: {os.path.basename(meta_out_path)}")
            except Exception as e:
                log_func(f"    [!] Metadata export failed: {e}")

        if original_img.format == 'PNG':
            log_func("    [*] PNG detected. Scrubbing ancillary chunks (tEXt, zTXt, iTXt)...")

        # 2. Handle Orientation
        # This "bakes" the rotation into the pixels so we can safely remove the EXIF tag
        clean_img = ImageOps.exif_transpose(original_img)
        
        # 3. Scrub Metadata (Selective or Full)
        if remove_tags:
            log_func(f"    [*] Selective scrubbing: Removing {', '.join(remove_tags)}")
            exif = original_img.getexif()
            
            # Map tag names to IDs
            name_map = {v: k for k, v in ExifTags.TAGS.items()}
            name_map['GPS'] = 34853 # Common alias for GPSInfo
            
            for tag in remove_tags:
                tag = tag.strip()
                tag_id = None
                
                # Find tag ID case-insensitively
                for name, tid in name_map.items():
                    if name.lower() == tag.lower():
                        tag_id = tid
                        break
                
                if tag_id and tag_id in exif:
                    del exif[tag_id]
                    log_func(f"        - Removed {tag}")
            
            # Remove Orientation tag since it's baked into pixels
            if 274 in exif: del exif[274]
            
        else:
            # Full Scrub
            clean_img.info = {}
        
        # 4. Apply Watermark
        if watermark_text:
            clean_img = apply_watermark(clean_img, watermark_text)
            # If original was not RGBA (e.g. JPEG), convert back to RGB to allow saving as JPEG
            if original_img.mode != 'RGBA':
                clean_img = clean_img.convert('RGB')
            log_func(f"    [+] Watermark applied: '{watermark_text}'")

        # 5. Resize
        if resize:
            w, h = resize
            if w or h:
                orig_w, orig_h = clean_img.size
                if w and h:
                    new_size = (w, h)
                elif w:
                    ratio = w / float(orig_w)
                    new_size = (w, int(orig_h * ratio))
                elif h:
                    ratio = h / float(orig_h)
                    new_size = (int(orig_w * ratio), h)
                
                clean_img = clean_img.resize(new_size, Image.Resampling.LANCZOS)
                log_func(f"    [i] Resized to: {new_size[0]}x{new_size[1]}")

        # Determine extension (Handle Conversion)
        base, original_ext = os.path.splitext(filepath)
        ext = original_ext
        
        if convert_to:
            ext = f".{convert_to.lower().strip('.')}"
            # Handle RGBA -> RGB for JPEG
            if ext in ['.jpg', '.jpeg'] and clean_img.mode in ('RGBA', 'P'):
                clean_img = clean_img.convert('RGB')
            log_func(f"    [i] Converting to {ext}")

        # 6. Save
        if overwrite and not convert_to:
            out_path = filepath
        else:
            directory = output_dir if output_dir else os.path.dirname(filepath)
            if not os.path.exists(directory):
                os.makedirs(directory, exist_ok=True)
                
            filename = os.path.basename(filepath)
            base_name = os.path.splitext(filename)[0]
            
            is_same_dir = os.path.abspath(directory) == os.path.abspath(os.path.dirname(filepath))
            # If converting format, we don't strictly need a suffix to avoid conflict, but we keep logic consistent
            eff_suffix = suffix if suffix else ("_scrubbed" if is_same_dir and not prefix and not convert_to else "")
            
            out_path = os.path.join(directory, f"{prefix}{base_name}{eff_suffix}{ext}")
        
        if remove_tags:
            clean_img.save(out_path, quality=100, exif=exif)
        else:
            clean_img.save(out_path, quality=100)
            
        log_func(f"    [+] Scrubbed image saved to: {out_path}")

        if verify:
            try:
                v_img = Image.open(out_path)
                v_meta = get_exif_data(v_img)
                
                if remove_tags:
                    failed_tags = []
                    v_keys_lower = [k.lower() for k in v_meta.keys()]
                    for tag in remove_tags:
                        if tag.lower() in v_keys_lower:
                            failed_tags.append(tag)
                    if failed_tags:
                        log_func(f"    [!] Verification Failed: Tags still present: {', '.join(failed_tags)}")
                    else:
                        log_func("    [+] Verification Successful: Selected tags removed.")
                else:
                    if v_meta:
                        log_func(f"    [!] Verification Warning: {len(v_meta)} metadata items found.")
                    else:
                        log_func("    [+] Verification Successful: No metadata found.")
            except Exception as e:
                log_func(f"    [!] Verification Error: {e}")

        new_size = os.path.getsize(out_path)
        log_func(f"    [i] Size: {original_size:,} -> {new_size:,} bytes (Saved {original_size - new_size:,} bytes)")
        
        if preserve_timestamp:
            os.utime(out_path, (file_stats.st_atime, file_stats.st_mtime))
            log_func("    [i] Timestamps preserved.")
        
        if delete_original and os.path.abspath(filepath) != os.path.abspath(out_path):
            try:
                os.remove(filepath)
                log_func(f"    [+] Deleted original file: {filepath}")
            except Exception as e:
                log_func(f"    [!] Failed to delete original: {e}")
                
        log_func("-" * 40)
        if report_data is not None:
            report_data.append({"file": filepath, "status": "Success", "details": f"Saved to {os.path.basename(out_path)}"})
        return (1, 0)
        
    except Exception as e:
        log_func(f"[!] Error processing {filepath}: {e}")
        if report_data is not None:
            report_data.append({"file": filepath, "status": "Failed", "details": str(e)})
        return (0, 1)

def scrub_folder(folder_path, overwrite=False, log_func=print, output_dir=None, prefix="", suffix="", delete_original=False, backup_zip=None, preserve_timestamp=False, remove_tags=None, verify=False, watermark_text=None, resize=None, convert_to=None, export_metadata=False, report_data=None):
    log_func(f"[*] Scanning folder: {folder_path}")
    s_total = 0
    f_total = 0
    for root, dirs, files in os.walk(folder_path):
        for file in files:
            if file.lower().endswith(('.jpg', '.jpeg', '.png', '.pdf', '.tiff', '.webp')):
                full_path = os.path.join(root, file)
                s, f = scrub_file(full_path, overwrite, log_func, output_dir, prefix, suffix, delete_original, backup_zip, preserve_timestamp, remove_tags, verify, watermark_text, resize, convert_to, export_metadata, report_data)
                s_total += s
                f_total += f
    return (s_total, f_total)

def open_folder(path):
    try:
        if os.path.isfile(path):
            path = os.path.dirname(path)
        if os.name == 'nt':
            os.startfile(path)
        elif sys.platform == 'darwin':
            subprocess.call(['open', path])
        else:
            subprocess.call(['xdg-open', path])
    except Exception as e:
        print(f"[-] Could not open folder: {e}")

class DependencyInstaller:
    def __init__(self, root):
        self.root = root
        self.root.title("Install Dependencies")
        self.root.geometry("400x250")
        
        tk.Label(root, text="Dependency Manager", font=("Arial", 12, "bold")).pack(pady=10)
        tk.Label(root, text="Some features require additional libraries.", font=("Arial", 10)).pack(pady=5)
        
        self.status_frame = tk.Frame(root)
        self.status_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        self.refresh_status()
        
        tk.Button(root, text="Close", command=self.root.destroy).pack(pady=10)

    def get_status(self, installed):
        return ("Installed", "green") if installed else ("Missing", "red")

    def refresh_status(self):
        for widget in self.status_frame.winfo_children():
            widget.destroy()
            
        deps = [
            ("Pillow (Required)", HAS_PILLOW, "Pillow"),
            ("pikepdf (PDF Support)", HAS_PIKEPDF, "pikepdf"),
            ("tkinterdnd2 (Drag & Drop)", HAS_TKINTERDND2, "tkinterdnd2"),
            ("reportlab (PDF Reports)", HAS_REPORTLAB, "reportlab")
        ]
        
        for label, installed, pkg in deps:
            frame = tk.Frame(self.status_frame)
            frame.pack(fill=tk.X, pady=5)
            
            tk.Label(frame, text=label, width=25, anchor="w").pack(side=tk.LEFT)
            status_text, color = self.get_status(installed)
            tk.Label(frame, text=status_text, fg=color, width=10).pack(side=tk.LEFT)
            
            if not installed:
                tk.Button(frame, text="Install", command=lambda p=pkg: self.install(p)).pack(side=tk.RIGHT)

    def install(self, package):
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", package])
            messagebox.showinfo("Success", f"Installed {package}.\nPlease restart the application.")
            self.root.destroy()
            sys.exit() # Force restart to load new libs
        except Exception as e:
            messagebox.showerror("Error", f"Failed to install {package}:\n{e}")

class ScrubApp:
    def __init__(self, root, initial_files=None):
        self.root = root
        self.root.title("ScrubMetaDub")
        self.root.geometry("700x650")
        self.files = []
        self.dark_mode = False
        
        if os.path.exists("icon.ico"):
            try:
                self.root.iconbitmap("icon.ico")
            except Exception:
                pass
        
        # Menu
        menubar = tk.Menu(root)
        
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Save Settings", command=self.save_config)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=root.quit)
        menubar.add_cascade(label="File", menu=file_menu)
        
        view_menu = tk.Menu(menubar, tearoff=0)
        view_menu.add_command(label="Toggle Dark Mode", command=self.toggle_theme)
        menubar.add_cascade(label="View", menu=view_menu)
        
        tools_menu = tk.Menu(menubar, tearoff=0)
        tools_menu.add_command(label="Install Dependencies", command=self.open_dep_installer)
        if winreg:
            tools_menu.add_command(label="Add to Context Menu", command=self.add_context_menu)
            tools_menu.add_command(label="Remove Context Menu", command=self.remove_context_menu)
        menubar.add_cascade(label="Tools", menu=tools_menu)
        
        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="Check for Updates", command=self.check_updates)
        help_menu.add_command(label="About", command=self.show_about)
        menubar.add_cascade(label="Help", menu=help_menu)
        root.config(menu=menubar)

        # --- Layout ---
        # Top: File List and Buttons
        top_frame = tk.Frame(root)
        top_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=10, pady=5)

        btn_frame = tk.Frame(top_frame)
        btn_frame.pack(side=tk.TOP, fill=tk.X, pady=5)
        
        tk.Button(btn_frame, text="Add Files", command=self.add_files).pack(side=tk.LEFT, padx=2)
        tk.Button(btn_frame, text="Add Folder", command=self.add_folder).pack(side=tk.LEFT, padx=2)
        tk.Button(btn_frame, text="Clear List", command=self.clear_list).pack(side=tk.LEFT, padx=2)
        tk.Button(btn_frame, text="Preview", command=self.preview_metadata).pack(side=tk.LEFT, padx=2)
        tk.Button(btn_frame, text="Compare", command=self.compare_images).pack(side=tk.LEFT, padx=2)
        tk.Button(btn_frame, text="Hex Dump", command=self.view_hex_dump).pack(side=tk.LEFT, padx=2)
        
        self.listbox = tk.Listbox(top_frame, height=10)
        self.listbox.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        
        if TkinterDnD:
            self.listbox.drop_target_register(DND_FILES)
            self.listbox.dnd_bind('<<Drop>>', self.drop_files)
        
        # Middle: Tabs
        self.notebook = ttk.Notebook(root)
        self.notebook.pack(side=tk.TOP, fill=tk.X, padx=10, pady=5)

        # Tab 1: General Options
        tab_general = tk.Frame(self.notebook)
        self.notebook.add(tab_general, text="General Options")

        self.overwrite_var = tk.BooleanVar()
        tk.Checkbutton(tab_general, text="Overwrite Original Files", variable=self.overwrite_var).grid(row=0, column=0, sticky="w", padx=5, pady=2)
        
        self.delete_original_var = tk.BooleanVar()
        tk.Checkbutton(tab_general, text="Delete Original Files", variable=self.delete_original_var).grid(row=0, column=1, sticky="w", padx=5, pady=2)
        
        self.backup_var = tk.BooleanVar()
        tk.Checkbutton(tab_general, text="Backup Originals to Zip", variable=self.backup_var).grid(row=1, column=0, sticky="w", padx=5, pady=2)
        
        self.preserve_time_var = tk.BooleanVar()
        tk.Checkbutton(tab_general, text="Preserve Timestamps", variable=self.preserve_time_var).grid(row=1, column=1, sticky="w", padx=5, pady=2)
        
        self.open_folder_var = tk.BooleanVar()
        tk.Checkbutton(tab_general, text="Open Output Folder When Done", variable=self.open_folder_var).grid(row=2, column=0, sticky="w", padx=5, pady=2)

        self.verify_var = tk.BooleanVar()
        tk.Checkbutton(tab_general, text="Verify Scrub (Re-scan)", variable=self.verify_var).grid(row=2, column=1, sticky="w", padx=5, pady=2)
        
        self.export_meta_var = tk.BooleanVar()
        tk.Checkbutton(tab_general, text="Export Metadata to .txt", variable=self.export_meta_var).grid(row=3, column=0, sticky="w", padx=5, pady=2)
        
        self.pdf_report_var = tk.BooleanVar()
        tk.Checkbutton(tab_general, text="Generate PDF Report", variable=self.pdf_report_var).grid(row=3, column=1, sticky="w", padx=5, pady=2)
        
        # Tab 2: Output & Naming
        tab_output = tk.Frame(self.notebook)
        self.notebook.add(tab_output, text="Output & Naming")
        
        tk.Label(tab_output, text="Output Directory (Optional):").pack(anchor="w", padx=5, pady=2)
        frame_out_inner = tk.Frame(tab_output)
        frame_out_inner.pack(fill=tk.X, padx=5)
        self.output_dir_var = tk.StringVar()
        tk.Entry(frame_out_inner, textvariable=self.output_dir_var).pack(side=tk.LEFT, fill=tk.X, expand=True)
        tk.Button(frame_out_inner, text="Browse...", command=self.browse_output).pack(side=tk.LEFT, padx=5)
        
        frame_naming = tk.Frame(tab_output)
        frame_naming.pack(fill=tk.X, padx=5, pady=5)
        tk.Label(frame_naming, text="Prefix:").pack(side=tk.LEFT)
        self.prefix_var = tk.StringVar()
        tk.Entry(frame_naming, textvariable=self.prefix_var, width=15).pack(side=tk.LEFT, padx=5)
        tk.Label(frame_naming, text="Suffix:").pack(side=tk.LEFT)
        self.suffix_var = tk.StringVar()
        tk.Entry(frame_naming, textvariable=self.suffix_var, width=15).pack(side=tk.LEFT, padx=5)

        # Tab 3: Advanced Processing
        tab_advanced = tk.Frame(self.notebook)
        self.notebook.add(tab_advanced, text="Advanced Processing")
        
        frame_tags = tk.Frame(tab_advanced)
        frame_tags.pack(fill=tk.X, padx=5, pady=5)
        tk.Label(frame_tags, text="Remove Specific Tags (comma-sep):").pack(side=tk.LEFT)
        self.remove_tags_var = tk.StringVar()
        tk.Entry(frame_tags, textvariable=self.remove_tags_var).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        frame_wm = tk.Frame(tab_advanced)
        frame_wm.pack(fill=tk.X, padx=5, pady=5)
        tk.Label(frame_wm, text="Watermark Text:").pack(side=tk.LEFT)
        self.watermark_var = tk.StringVar()
        tk.Entry(frame_wm, textvariable=self.watermark_var).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        frame_trans = tk.Frame(tab_advanced)
        frame_trans.pack(fill=tk.X, padx=5, pady=5)
        tk.Label(frame_trans, text="Resize (WxH):").pack(side=tk.LEFT)
        self.resize_w_var = tk.StringVar()
        tk.Entry(frame_trans, textvariable=self.resize_w_var, width=6).pack(side=tk.LEFT)
        tk.Label(frame_trans, text="x").pack(side=tk.LEFT)
        self.resize_h_var = tk.StringVar()
        tk.Entry(frame_trans, textvariable=self.resize_h_var, width=6).pack(side=tk.LEFT)
        tk.Label(frame_trans, text="  Convert to:").pack(side=tk.LEFT, padx=(10, 0))
        self.convert_var = ttk.Combobox(frame_trans, values=["", "jpg", "png", "webp", "bmp", "tiff"], width=8)
        self.convert_var.pack(side=tk.LEFT)

        # --- Bottom Section ---
        bottom_frame = tk.Frame(root)
        bottom_frame.pack(side=tk.BOTTOM, fill=tk.BOTH, expand=False, padx=10, pady=5)

        self.progress = ttk.Progressbar(bottom_frame, orient=tk.HORIZONTAL, mode='determinate')
        self.progress.pack(fill=tk.X, pady=5)
        
        tk.Button(bottom_frame, text="Start Scrubbing", command=self.start_scrubbing, bg="#dddddd", height=2).pack(fill=tk.X, pady=5)
        
        self.log_area = scrolledtext.ScrolledText(bottom_frame, height=8, state='disabled')
        self.log_area.pack(fill=tk.BOTH, expand=True)

        self.load_config()
        self.apply_theme()
        
        if initial_files:
            for f in initial_files:
                if os.path.exists(f):
                    self.files.append(f)
                    if os.path.isdir(f):
                        self.listbox.insert(tk.END, f"[FOLDER] {f}")
                    else:
                        self.listbox.insert(tk.END, f)
        
    def log(self, msg):
        self.log_area.config(state='normal')
        self.log_area.insert(tk.END, msg + "\n")
        self.log_area.see(tk.END)
        self.log_area.config(state='disabled')

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    data = json.load(f)
                    self.overwrite_var.set(data.get("overwrite", False))
                    self.delete_original_var.set(data.get("delete_original", False))
                    self.backup_var.set(data.get("backup", False))
                    self.preserve_time_var.set(data.get("preserve_time", False))
                    self.open_folder_var.set(data.get("open_folder", False))
                    self.verify_var.set(data.get("verify", False))
                    self.export_meta_var.set(data.get("export_metadata", False))
                    self.pdf_report_var.set(data.get("pdf_report", False))
                    self.output_dir_var.set(data.get("output_dir", ""))
                    self.prefix_var.set(data.get("prefix", ""))
                    self.suffix_var.set(data.get("suffix", ""))
                    self.remove_tags_var.set(data.get("remove_tags", ""))
                    self.watermark_var.set(data.get("watermark", ""))
                    self.resize_w_var.set(data.get("resize_w", ""))
                    self.resize_h_var.set(data.get("resize_h", ""))
                    self.convert_var.set(data.get("convert", ""))
                    self.dark_mode = data.get("dark_mode", False)
            except Exception as e:
                print(f"Error loading config: {e}")

    def save_config(self):
        data = {
            "overwrite": self.overwrite_var.get(),
            "delete_original": self.delete_original_var.get(),
            "backup": self.backup_var.get(),
            "preserve_time": self.preserve_time_var.get(),
            "open_folder": self.open_folder_var.get(),
            "verify": self.verify_var.get(),
            "export_metadata": self.export_meta_var.get(),
            "pdf_report": self.pdf_report_var.get(),
            "output_dir": self.output_dir_var.get(),
            "prefix": self.prefix_var.get(),
            "suffix": self.suffix_var.get(),
            "remove_tags": self.remove_tags_var.get(),
            "watermark": self.watermark_var.get(),
            "resize_w": self.resize_w_var.get(),
            "resize_h": self.resize_h_var.get(),
            "convert": self.convert_var.get(),
            "dark_mode": self.dark_mode
        }
        try:
            with open(CONFIG_FILE, 'w') as f:
                json.dump(data, f, indent=4)
            messagebox.showinfo("Settings Saved", f"Configuration saved to {CONFIG_FILE}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save config: {e}")

    def toggle_theme(self):
        self.dark_mode = not self.dark_mode
        self.apply_theme()

    def apply_theme(self):
        if self.dark_mode:
            bg_color = "#2e2e2e"
            fg_color = "#ffffff"
            entry_bg = "#404040"
            entry_fg = "#ffffff"
            select_bg = "#505050"
        else:
            bg_color = "#f0f0f0"
            fg_color = "#000000"
            entry_bg = "#ffffff"
            entry_fg = "#000000"
            select_bg = "#0078d7"

        style = ttk.Style()
        style.theme_use('default')
        style.configure("TProgressbar", background=select_bg)
        style.configure("TCombobox", fieldbackground=entry_bg, background=bg_color, foreground=entry_fg)
        style.map('TCombobox', fieldbackground=[('readonly', entry_bg)], selectbackground=[('readonly', select_bg)], selectforeground=[('readonly', entry_fg)])
        
        self.root.configure(bg=bg_color)
        
        def update_widget(widget):
            try:
                widget_type = widget.winfo_class()
                if widget_type in ('Frame', 'Labelframe', 'Toplevel'):
                    widget.configure(bg=bg_color)
                elif widget_type in ('Label', 'Checkbutton', 'Radiobutton'):
                    widget.configure(bg=bg_color, fg=fg_color, selectcolor=bg_color, activebackground=bg_color, activeforeground=fg_color)
                elif widget_type == 'Button':
                    widget.configure(bg=entry_bg, fg=fg_color, activebackground=select_bg, activeforeground=fg_color)
                elif widget_type in ('Entry', 'Listbox', 'Text'):
                    widget.configure(bg=entry_bg, fg=entry_fg, insertbackground=fg_color, selectbackground=select_bg)
            except: pass
            
            for child in widget.winfo_children():
                update_widget(child)

        update_widget(self.root)
        
    def open_dep_installer(self):
        top = tk.Toplevel(self.root)
        DependencyInstaller(top)
        
    def get_output_path(self, filepath):
        overwrite = self.overwrite_var.get()
        output_dir = self.output_dir_var.get().strip() or None
        prefix = self.prefix_var.get().strip()
        suffix = self.suffix_var.get().strip()
        convert_to = self.convert_var.get().strip() or None
        
        if overwrite and not convert_to:
            return filepath
            
        directory = output_dir if output_dir else os.path.dirname(filepath)
        filename = os.path.basename(filepath)
        base_name, original_ext = os.path.splitext(filename)
        
        ext = original_ext
        if convert_to:
            ext = f".{convert_to.lower().strip('.')}"
            
        is_same_dir = os.path.abspath(directory) == os.path.abspath(os.path.dirname(filepath))
        eff_suffix = suffix if suffix else ("_scrubbed" if is_same_dir and not prefix and not convert_to else "")
        
        return os.path.join(directory, f"{prefix}{base_name}{eff_suffix}{ext}")

    def compare_images(self):
        selection = self.listbox.curselection()
        if not selection:
            messagebox.showwarning("No Selection", "Select a file to compare.")
            return
        
        input_path = self.files[selection[0]]
        if os.path.isdir(input_path):
            messagebox.showinfo("Info", "Cannot compare folders.")
            return
            
        output_path = self.get_output_path(input_path)
        
        if not os.path.exists(output_path):
            messagebox.showerror("Error", f"Output file not found:\n{output_path}\n\nDid you scrub it yet?")
            return
            
        if os.path.abspath(input_path) == os.path.abspath(output_path):
             messagebox.showinfo("Info", "Input and Output paths are identical (Overwritten). Cannot compare.")
             return

        top = tk.Toplevel(self.root)
        top.title("Compare Images")
        
        try:
            img_in = Image.open(input_path)
            img_out = Image.open(output_path)
            
            # Resize for display (max 400x400)
            img_in.thumbnail((400, 400))
            img_out.thumbnail((400, 400))
            
            photo_in = ImageTk.PhotoImage(img_in)
            photo_out = ImageTk.PhotoImage(img_out)
            
            f_in = tk.Frame(top)
            f_in.pack(side=tk.LEFT, padx=10, pady=10)
            tk.Label(f_in, text="Original").pack()
            l_in = tk.Label(f_in, image=photo_in)
            l_in.image = photo_in 
            l_in.pack()
            
            f_out = tk.Frame(top)
            f_out.pack(side=tk.LEFT, padx=10, pady=10)
            tk.Label(f_out, text="Scrubbed").pack()
            l_out = tk.Label(f_out, image=photo_out)
            l_out.image = photo_out
            l_out.pack()
            
            # Add metadata summary text below?
            # For now, visual comparison is the main goal.
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load images: {e}")
            top.destroy()

    def check_updates(self):
        try:
            # Placeholder logic for update checking
            # In a real app, fetch version string from UPDATE_URL and compare with VERSION
            # with urllib.request.urlopen(UPDATE_URL, timeout=3) as response:
            #    latest = response.read().decode().strip()
            
            messagebox.showinfo("Check for Updates", f"Current Version: {VERSION}\n\nNo updates found (Update server not configured).")
        except Exception as e:
            messagebox.showerror("Error", f"Update check failed: {e}")

    def show_about(self):
        messagebox.showinfo("About", f"ScrubMetaDub v{VERSION}\n\nA metadata scrubbing tool for images and PDFs.\n\nCreated by Cipherspride360.")

    def view_hex_dump(self):
        selection = self.listbox.curselection()
        if not selection:
            messagebox.showwarning("No Selection", "Select a file to view hex dump.")
            return
        
        filepath = self.files[selection[0]]
        if os.path.isdir(filepath):
            messagebox.showinfo("Info", "Cannot view hex dump of a folder.")
            return
            
        hex_data = get_hex_dump(filepath)
        
        top = tk.Toplevel(self.root)
        top.title(f"Hex Dump (First 512 bytes): {os.path.basename(filepath)}")
        top.geometry("700x500")
        
        txt = scrolledtext.ScrolledText(top, font=("Courier", 10))
        txt.pack(fill=tk.BOTH, expand=True)
        txt.insert(tk.END, hex_data)
        txt.config(state='disabled')

    def add_context_menu(self):
        if not winreg: return
        try:
            script_path = os.path.abspath(sys.argv[0])
            python_exe = sys.executable
            
            if getattr(sys, 'frozen', False):
                cmd = f'"{python_exe}" "%1" --gui'
            else:
                cmd = f'"{python_exe}" "{script_path}" "%1" --gui'
            
            key_path = r"Software\Classes\Directory\shell\ScrubMetaDub"
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path) as key:
                winreg.SetValue(key, "", winreg.REG_SZ, "Scrub with ScrubMetaDub")
                winreg.SetValueEx(key, "Icon", 0, winreg.REG_SZ, python_exe)
                
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, f"{key_path}\\command") as key:
                winreg.SetValue(key, "", winreg.REG_SZ, cmd)
                
            messagebox.showinfo("Success", "Context menu added! Right-click a folder to test.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to add context menu: {e}")

    def remove_context_menu(self):
        if not winreg: return
        try:
            key_path = r"Software\Classes\Directory\shell\ScrubMetaDub"
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, f"{key_path}\\command")
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, key_path)
            messagebox.showinfo("Success", "Context menu removed.")
        except FileNotFoundError:
             messagebox.showinfo("Info", "Context menu not found.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to remove context menu: {e}")

    def drop_files(self, event):
        files = self.root.tk.splitlist(event.data)
        for f in files:
            if os.path.isdir(f):
                self.files.append(f)
                self.listbox.insert(tk.END, f"[FOLDER] {f}")
            elif os.path.exists(f):
                self.files.append(f)
                self.listbox.insert(tk.END, f)

    def add_files(self):
        files = filedialog.askopenfilenames(filetypes=[("Images/PDF", "*.jpg *.jpeg *.png *.pdf *.tiff *.webp")])
        for f in files:
            self.files.append(f)
            self.listbox.insert(tk.END, f)
            
    def add_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.files.append(folder)
            self.listbox.insert(tk.END, f"[FOLDER] {folder}")
            
    def clear_list(self):
        self.files = []
        self.listbox.delete(0, tk.END)

    def browse_output(self):
        d = filedialog.askdirectory()
        if d:
            self.output_dir_var.set(d)

    def preview_metadata(self):
        selection = self.listbox.curselection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a file to preview.")
            return
        
        # self.files matches listbox index
        filepath = self.files[selection[0]]
        
        if os.path.isdir(filepath):
            messagebox.showinfo("Info", "Cannot preview metadata for a folder.")
            return
            
        meta_text = ""
        try:
            if filepath.lower().endswith('.pdf'):
                if not pikepdf:
                    meta_text = "pikepdf not installed."
                else:
                    pdf = pikepdf.open(filepath)
                    if pdf.docinfo:
                        for k, v in pdf.docinfo.items():
                            meta_text += f"{k}: {v}\n"
                    else:
                        meta_text = "No metadata found in PDF."
            else:
                img = Image.open(filepath)
                meta = get_exif_data(img)
                if meta:
                    for k, v in meta.items():
                        meta_text += f"{k}: {v}\n"
                else:
                    meta_text = "No metadata found."
        except Exception as e:
            meta_text = f"Error reading metadata: {e}"
            
        top = tk.Toplevel(self.root)
        top.title(f"Metadata: {os.path.basename(filepath)}")
        top.geometry("400x300")
        txt = scrolledtext.ScrolledText(top)
        txt.pack(fill=tk.BOTH, expand=True)
        txt.insert(tk.END, meta_text)
        txt.config(state='disabled')
        
    def start_scrubbing(self):
        if not self.files:
            messagebox.showwarning("No Files", "Please add files or folders first.")
            return
        overwrite = self.overwrite_var.get()
        output_dir = self.output_dir_var.get().strip() or None
        prefix = self.prefix_var.get().strip()
        suffix = self.suffix_var.get().strip()
        delete_original = self.delete_original_var.get()
        backup_enabled = self.backup_var.get()
        preserve_timestamp = self.preserve_time_var.get()
        open_when_done = self.open_folder_var.get()
        verify = self.verify_var.get()
        export_metadata = self.export_meta_var.get()
        generate_report = self.pdf_report_var.get()
        watermark_text = self.watermark_var.get().strip() or None
        
        rw = self.resize_w_var.get().strip()
        rh = self.resize_h_var.get().strip()
        resize = (int(rw) if rw else None, int(rh) if rh else None)
        if resize == (None, None): resize = None
        convert_to = self.convert_var.get().strip() or None
        
        tags_str = self.remove_tags_var.get().strip()
        remove_tags = [t.strip() for t in tags_str.split(',')] if tags_str else None
        
        backup_zip = None
        if backup_enabled:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_zip = f"backup_{timestamp}.zip"
        
        # Expand folders to get total count for progress bar
        all_files = []
        for item in self.files:
            if os.path.isdir(item):
                for root, dirs, files in os.walk(item):
                    for file in files:
                        if file.lower().endswith(('.jpg', '.jpeg', '.png', '.pdf', '.tiff', '.webp')):
                            all_files.append(os.path.join(root, file))
            elif os.path.exists(item):
                all_files.append(item)
        
        self.progress['maximum'] = len(all_files)
        self.progress['value'] = 0
        
        def run():
            session_report = [] if generate_report else None
            
            self.log(f"--- Starting Scrub ({len(all_files)} files) ---")
            success_count = 0
            fail_count = 0
            last_path = None
            for i, item in enumerate(all_files):
                s, f = scrub_file(item, overwrite, self.log, output_dir, prefix, suffix, delete_original, backup_zip, preserve_timestamp, remove_tags, verify, watermark_text, resize, convert_to, export_metadata, session_report)
                success_count += s
                fail_count += f
                last_path = item
                self.root.after(0, lambda v=i+1: self.progress.configure(value=v))
            self.log("--- Finished ---")
            self.log(f"Summary: {success_count} successful, {fail_count} failed.")
            
            if session_report and HAS_REPORTLAB:
                report_path = f"ScrubReport_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
                generate_pdf_report(report_path, session_report)
                self.log(f"Report generated: {report_path}")
            
            if open_when_done:
                target_dir = output_dir if output_dir else (os.path.dirname(last_path) if last_path else None)
                if target_dir:
                    open_folder(target_dir)
            
            self.root.after(0, lambda: messagebox.showinfo("Done", f"Scrubbing Complete!\nSuccessful: {success_count}\nFailed: {fail_count}"))
            
        threading.Thread(target=run, daemon=True).start()

def launch_gui(initial_files=None):
    if not HAS_PILLOW:
        root = tk.Tk()
        DependencyInstaller(root)
        root.mainloop()
        return

    if TkinterDnD:
        root = TkinterDnD.Tk()
    else:
        root = tk.Tk()
        
    # Splash Screen
    root.withdraw()
    splash = tk.Toplevel(root)
    splash.overrideredirect(True)
    splash.geometry("300x150+{}+{}".format(
        int(root.winfo_screenwidth()/2 - 150),
        int(root.winfo_screenheight()/2 - 75)
    ))
    splash.configure(bg="#2e2e2e")
    
    tk.Label(splash, text="ScrubMetaDub", font=("Arial", 20, "bold"), bg="#2e2e2e", fg="white").pack(pady=(40, 10))
    tk.Label(splash, text=f"v{VERSION} - Loading...", font=("Arial", 10), bg="#2e2e2e", fg="#cccccc").pack()
    splash.update()

    app = ScrubApp(root, initial_files)
    
    # Close splash after 1.5 seconds
    root.after(1500, lambda: (splash.destroy(), root.deiconify()))
    root.mainloop()

def main():
    parser = argparse.ArgumentParser(description="ScrubMetaDub - Image Metadata Scrubber")
    parser.add_argument("files", nargs='*', help="Image files or folders to scrub")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite original files instead of creating a copy")
    parser.add_argument("--gui", action="store_true", help="Launch GUI")
    parser.add_argument("-o", "--output", help="Output directory for scrubbed files")
    parser.add_argument("--prefix", default="", help="Prefix for scrubbed filenames")
    parser.add_argument("--suffix", default="", help="Suffix for scrubbed filenames")
    parser.add_argument("--delete", action="store_true", help="Delete original files after scrubbing")
    parser.add_argument("--backup", action="store_true", help="Backup original files to a zip archive before scrubbing")
    parser.add_argument("--preserve-time", action="store_true", help="Preserve original file timestamps")
    parser.add_argument("--open", action="store_true", help="Open output folder after processing")
    parser.add_argument("--remove-tags", help="Comma-separated list of EXIF tags to remove (e.g., 'GPS,Model'). If omitted, all metadata is removed.")
    parser.add_argument("--verify", action="store_true", help="Verify metadata removal by re-scanning the output file")
    parser.add_argument("--watermark", help="Text to watermark images with")
    parser.add_argument("--resize", help="Resize image (e.g. '800x600', '800x', 'x600')")
    parser.add_argument("--convert", help="Convert image format (e.g. 'png', 'jpg')")
    parser.add_argument("--export-metadata", action="store_true", help="Export metadata to a text file before scrubbing")
    parser.add_argument("--report", action="store_true", help="Generate PDF report of the session")
    
    args = parser.parse_args()
    
    generate_default_icon()
    
    if args.gui or not args.files:
        launch_gui(args.files)
        return

    total_success = 0
    total_fail = 0
    
    backup_zip = None
    if args.backup:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_zip = f"backup_{timestamp}.zip"
        
    remove_tags = [t.strip() for t in args.remove_tags.split(',')] if args.remove_tags else None
    last_file_path = None
    
    resize = None
    if args.resize:
        parts = args.resize.lower().split('x')
        if len(parts) == 2:
            w = int(parts[0]) if parts[0] else None
            h = int(parts[1]) if parts[1] else None
            resize = (w, h)
            
    session_report = [] if args.report else None

    for f in args.files:
        if os.path.exists(f):
            s, f_count = scrub_file(f, args.overwrite, output_dir=args.output, prefix=args.prefix, suffix=args.suffix, delete_original=args.delete, backup_zip=backup_zip, preserve_timestamp=args.preserve_time, remove_tags=remove_tags, verify=args.verify, watermark_text=args.watermark, resize=resize, convert_to=args.convert, export_metadata=args.export_metadata, report_data=session_report)
            total_success += s
            total_fail += f_count
            last_file_path = f
        else:
            print(f"[!] File not found: {f}")
            total_fail += 1
            
    print("-" * 40)
    print(f"Summary: {total_success} successful, {total_fail} failed.")
    
    if session_report and HAS_REPORTLAB:
        report_path = f"ScrubReport_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        generate_pdf_report(report_path, session_report)
        print(f"Report generated: {report_path}")
    
    if args.open:
        target_dir = args.output if args.output else (os.path.dirname(last_file_path) if last_file_path else None)
        if target_dir:
            open_folder(target_dir)

if __name__ == "__main__":
    main()