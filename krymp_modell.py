"""Gör en ONNX-modell ~4 ggr mindre: vikterna sparas som int8 per kanal och
packas upp (Cast + Mul) när modellen laddas. Själva uträkningen sker
fortfarande i float32, så resultatet blir nästan identiskt.

Används av hemsidans "Fixa bilder", som kör bildmodellerna i besökarens
webbläsare. Skriptet behöver bara numpy (inte paketet onnx): ONNX-filen
läses och skrivs direkt i protobuf-formatet.

Användning:
    python3 krymp_modell.py in.onnx ut.onnx
"""
import sys

import numpy as np

def varint(b,i):
    r=s=0
    while True:
        c=b[i];i+=1;r|=(c&0x7f)<<s;s+=7
        if c<0x80:return r,i
def fields(b):
    i=0;out=[]
    while i<len(b):
        k,i=varint(b,i);f,w=k>>3,k&7
        if w==0: v,i=varint(b,i)
        elif w==2:
            n,i=varint(b,i);v=b[i:i+n];i+=n
        elif w==5: v=b[i:i+4];i+=4
        elif w==1: v=b[i:i+8];i+=8
        else: raise Exception(w)
        out.append((f,w,v))
    return out
def enc_varint(n):
    o=bytearray()
    while True:
        c=n&0x7f;n>>=7
        if n:o.append(c|0x80)
        else:o.append(c);return bytes(o)
def enc(fs):
    o=bytearray()
    for f,w,v in fs:
        o+=enc_varint(f<<3|w)
        if w==0:o+=enc_varint(v)
        elif w==2:o+=enc_varint(len(v))+v
        else:o+=v
    return bytes(o)

def tensor(name, dt, dims, raw):
    return enc([(1, 0, d) for d in dims] + [(2, 0, dt), (8, 2, name.encode()), (9, 2, raw)])

def kvantisera(src, dst):
    m = fields(open(src, "rb").read())
    ut_m = []
    for f, w, v in m:
        if f != 7:
            ut_m.append((f, w, v)); continue
        g = fields(v)
        nya_noder, ovr = [], []
        for gf, gw, gv in g:
            if gf != 5:
                ovr.append((gf, gw, gv)); continue
            t = fields(gv)
            dims = [x for k, _, x in t if k == 1]
            dt = [x for k, _, x in t if k == 2][0]
            name = [x for k, _, x in t if k == 8][0].decode()
            raw = [x for k, _, x in t if k == 9]
            if dt != 1 or not raw or len(dims) < 2 or int(np.prod(dims)) < 4096:
                ovr.append((gf, gw, gv)); continue
            W = np.frombuffer(raw[0], np.float32).reshape(dims)
            skala = np.abs(W.reshape(dims[0], -1)).max(1) / 127.0
            skala = np.where(skala == 0, 1.0, skala).astype(np.float32)
            q = np.clip(np.round(W / skala.reshape([-1] + [1] * (len(dims) - 1))), -127, 127).astype(np.int8)
            ovr.append((5, 2, tensor(name + "__q", 3, dims, q.tobytes())))
            ovr.append((5, 2, tensor(name + "__s", 1, [dims[0]] + [1] * (len(dims) - 1), skala.tobytes())))
            # Cast + Mul i stället för DequantizeLinear, så det fungerar oavsett opset.
            attr = enc([(1, 2, b"to"), (3, 0, 1), (20, 0, 2)])
            nya_noder.append((1, 2, enc([(1, 2, (name + "__q").encode()), (2, 2, (name + "__f").encode()),
                                            (3, 2, ("cast_" + name).encode()), (4, 2, b"Cast"), (5, 2, attr)])))
            nya_noder.append((1, 2, enc([(1, 2, (name + "__f").encode()), (1, 2, (name + "__s").encode()),
                                            (2, 2, name.encode()), (3, 2, ("mul_" + name).encode()),
                                            (4, 2, b"Mul")])))
        ut_m.append((7, 2, enc(nya_noder + ovr)))
    open(dst, "wb").write(enc(ut_m))

if __name__ == "__main__":
    kvantisera(sys.argv[1], sys.argv[2])
