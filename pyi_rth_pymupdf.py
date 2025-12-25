# PyInstaller runtime hook for pymupdf
import sys
import os

# Ensure pymupdf can find its native libraries
if hasattr(sys, '_MEIPASS'):
    # Running in PyInstaller bundle
    bundle_dir = sys._MEIPASS
    pymupdf_dir = os.path.join(bundle_dir, 'pymupdf')
    if os.path.exists(pymupdf_dir) and pymupdf_dir not in sys.path:
        sys.path.insert(0, pymupdf_dir)
