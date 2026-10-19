import sys, os, glob, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import numpy as np
from PIL import Image
import vit_bakgrund as v
mapp = sys.argv[1]
ut = mapp + '_mask'
os.makedirs(ut, exist_ok=True)
t0 = time.time()
for i, f in enumerate(sorted(glob.glob(mapp + '/*.png'))):
    dst = os.path.join(ut, os.path.basename(f))
    if os.path.exists(dst):
        continue
    a = v.mask_for(Image.open(f).convert('RGB'))
    Image.fromarray((a * 255 + 0.5).astype(np.uint8)).save(dst)
    if i % 20 == 0:
        print(mapp, i, round(time.time() - t0), flush=True)
