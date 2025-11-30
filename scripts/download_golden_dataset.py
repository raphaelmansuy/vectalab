#!/usr/bin/env python3
"""
Download a large, diverse "Golden Dataset" of SVGs for benchmarking.
"""

import os
import requests
import random
import time
from pathlib import Path

# Configuration
GOLDEN_DIR = Path("golden_data")
ICONS_DIR = GOLDEN_DIR / "icons"
LOGOS_DIR = GOLDEN_DIR / "logos"
ILLUSTRATIONS_DIR = GOLDEN_DIR / "illustrations"

# Limits
MAX_ICONS = 100
MAX_LOGOS = 100
MAX_ILLUSTRATIONS = 50

def download_file(url, output_path):
    """Download a file from a URL."""
    try:
        response = requests.get(url)
        response.raise_for_status()
        with open(output_path, 'wb') as f:
            f.write(response.content)
        print(f"✅ Downloaded: {output_path.name}")
        return True
    except Exception as e:
        print(f"❌ Failed to download {url}: {e}")
        return False

def fetch_github_files(owner, repo, path, limit=None):
    """Fetch a list of files from a GitHub repository directory."""
    api_url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
    try:
        response = requests.get(api_url)
        response.raise_for_status()
        files = response.json()
        svg_files = [f for f in files if f['name'].endswith('.svg')]
        
        if limit and len(svg_files) > limit:
            return random.sample(svg_files, limit)
        return svg_files
    except Exception as e:
        print(f"❌ Failed to fetch file list from {api_url}: {e}")
        return []

def download_icons():
    """Download icons from Feather Icons."""
    print("\n⬇️  Downloading Icons...")
    files = fetch_github_files("feathericons", "feather", "icons", MAX_ICONS)
    for file_info in files:
        download_file(file_info['download_url'], ICONS_DIR / file_info['name'])

def download_logos():
    """Download logos from Gilbarbara Logos and Simple Icons."""
    print("\n⬇️  Downloading Logos (Gilbarbara)...")
    files = fetch_github_files("gilbarbara", "logos", "logos", MAX_LOGOS)
    for file_info in files:
        download_file(file_info['download_url'], LOGOS_DIR / file_info['name'])

    print("\n⬇️  Downloading Logos (Simple Icons)...")
    files = fetch_github_files("simple-icons", "simple-icons", "icons", MAX_LOGOS)
    for file_info in files:
        download_file(file_info['download_url'], LOGOS_DIR / f"simple_{file_info['name']}")

def download_illustrations():
    """Download complex SVGs/illustrations."""
    print("\n⬇️  Downloading Illustrations...")
    
    # 1. W3C SVG Test Suite samples
    w3c_base = "https://dev.w3.org/SVG/tools/svgweb/samples/svg-files/"
    w3c_files = [
        'tiger.svg', 'car.svg', 'gallardo.svg', 'tommek_Car.svg',
        'compuserver_msn_Ford_Focus.svg', 'juanmontoya_lingerie.svg',
        'scimitar.svg', 'rg1024_green_grapes.svg',
        'rg1024_Presentation_with_girl.svg', 'rg1024_metal_effect.svg',
        'beetle.svg', 'cartman.svg', 'cowboy.svg', 'sodipodi.svg',
        'android.svg', 'aztec_mask.svg', 'barchart_3d.svg',
        'butterfly.svg', 'chess.svg', 'drops.svg', 'flower.svg',
        'linux.svg', 'lion.svg', 'motors.svg', 'mushroom.svg',
        'plane.svg', 'snowman.svg', 'star.svg', 'tux.svg'
    ]
    
    for filename in w3c_files:
        url = w3c_base + filename
        download_file(url, ILLUSTRATIONS_DIR / filename)

    # 2. Twemoji (Complex Emojis)
    print("\n⬇️  Downloading Illustrations (Twemoji)...")
    # Twemoji repo structure is assets/svg/
    files = fetch_github_files("twitter", "twemoji", "assets/svg", MAX_ILLUSTRATIONS)
    for file_info in files:
        download_file(file_info['download_url'], ILLUSTRATIONS_DIR / f"twemoji_{file_info['name']}")


def main():
    # Ensure directories exist
    ICONS_DIR.mkdir(parents=True, exist_ok=True)
    LOGOS_DIR.mkdir(parents=True, exist_ok=True)
    ILLUSTRATIONS_DIR.mkdir(parents=True, exist_ok=True)
    
    download_icons()
    download_logos()
    download_illustrations()
    
    print("\n✨ Golden Dataset Download Complete!")
    print(f"📂 Location: {GOLDEN_DIR.absolute()}")

if __name__ == "__main__":
    main()
