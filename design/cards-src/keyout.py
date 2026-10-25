import sys
from PIL import Image
import numpy as np
from scipy import ndimage
src, out = sys.argv[1], sys.argv[2]
im = Image.open(src).convert('RGB').resize((1000, 1400), Image.LANCZOS)
a = np.asarray(im).astype(int)
r, g, b = a[..., 0], a[..., 1], a[..., 2]
m = (r > 150) & (b > 150) & (g < 130) & (r - g > 70) & (b - g > 70)
lab, n = ndimage.label(m)
sizes = ndimage.sum(m, lab, range(1, n + 1))
keep = np.isin(lab, [i + 1 for i, s in enumerate(sizes) if s > 9])   # every pink area, including bits cut off by the decorations
keep = ndimage.binary_fill_holes(keep)
keep = ndimage.binary_dilation(keep, iterations=2)                       # eat the anti-aliased pink fringe
alpha = np.where(keep, 0, 255).astype(np.uint8)
rgba = np.dstack([np.asarray(im), alpha])
Image.fromarray(rgba, 'RGBA').save(out, 'WEBP', quality=80, method=6)
