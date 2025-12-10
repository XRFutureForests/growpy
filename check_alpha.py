from PIL import Image
import numpy as np
from pathlib import Path

def analyze_alpha_corners(texture_path):
    """Check corner values to determine alpha convention."""
    img = Image.open(texture_path)
    img_array = np.array(img.convert("L"), dtype=np.float32) / 255.0
    
    h, w = img_array.shape
    
    # Sample 10x10 patches at each corner
    patch_size = 10
    
    corners = {
        "top_left": img_array[0:patch_size, 0:patch_size],
        "top_right": img_array[0:patch_size, -patch_size:],
        "bottom_left": img_array[-patch_size:, 0:patch_size],
        "bottom_right": img_array[-patch_size:, -patch_size:],
    }
    
    print(f"\n{Path(texture_path).parent.name}:")
    print(f"  Size: {w}x{h}")
    
    for corner_name, patch in corners.items():
        mean = patch.mean()
        print(f"  {corner_name}: {mean:.3f}")
    
    # Overall histogram
    hist, _ = np.histogram(img_array.flatten(), bins=[0, 0.2, 0.4, 0.6, 0.8, 1.0])
    print(f"  Histogram: 0-0.2: {hist[0]}, 0.2-0.4: {hist[1]}, 0.4-0.6: {hist[2]}, 0.6-0.8: {hist[3]}, 0.8-1.0: {hist[4]}")
    
    # Determine convention based on corners
    corner_means = [patch.mean() for patch in corners.values()]
    corner_mean = np.mean(corner_means)
    
    if corner_mean < 0.1:
        print(f"  Corners are BLACK (< 0.1) -> Likely OPAQUE background (inverted)")
    elif corner_mean > 0.9:
        print(f"  Corners are WHITE (> 0.9) -> Likely TRANSPARENT background (standard)")
    else:
        print(f"  Corners are MID-TONE ({corner_mean:.3f}) -> AMBIGUOUS")

# Analyze textures
textures = [
    "data/assets/twigs/pacific_silver_fir_twig/textures/pacific_silver_fir_twig_alpha.png",
    "data/assets/twigs/paper_birch_twig/textures/paper_birch_twig_alpha.png",
    "data/assets/twigs/black_alder_twig/textures/black_alder_twig_alpha.png",
    "data/assets/twigs/european_beech_twig/textures/european_beech_twig_alpha.png",
    "data/assets/twigs/european_oak_twig/textures/european_oak_twig_alpha.png",
]

for tex in textures:
    p = Path(tex)
    if p.exists():
        analyze_alpha_corners(tex)
