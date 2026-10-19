# Marknadsföringsvideor

Verktyg för TikTok/Reels-videor (9:16, 1080x1920) av lagret.

## Daglig bildvideo (ingen filmning)

    python3 video/daglig_video.py --mapp /mnt/project-files/saljbilder/02-replay-jeans-bla \
        --marke Replay --titel "Anbass jeans, mörkblå" --detalj "W31 L32  ·  Bra skick" \
        --pris "299 kr" --rubrik "Dagens fynd" --ut dagens.mp4

Produktbilderna visas i helbild med långsam inzoomning och svep mellan bilderna,
med rubrik på första bilden och annonskortet (pris, storlek, "Finns på Vinted & Plick") på slutet.

## Filmade klipp med studiobakgrund (som blazer-videon)

1. Konvertera klippet (HLG/HDR från iPhone) till PNG-rutor:
   `ffmpeg -i klipp.mov -vf "zscale=t=linear:npl=203,format=gbrpf32le,zscale=p=bt709,tonemap=tonemap=hable:desat=0,zscale=t=bt709:m=bt709:r=pc,format=rgb24" f1/%04d.png`
2. Motivmasker per ruta: `python3 video/masker.py f1` (skriver `f1_mask/`, kräver modellerna i `VIT_BAKGRUND_MODELLER`).
3. Studiobakgrund utan flimmer: `python3 video/studio_video.py f1 f1_mask s1 --hojd 0.81`.
   Kameran ska stå still: tomma väggen räknas fram från början/slutet av klippet och används för att
   hitta det modellen missar och ta bort vägg/golv i glipor. `--hojd` beskär bort golvet nertill.
4. Klipp ihop med frysning och annonskort: `python3 video/klipp_ihop.py` (styrs av `plan.json` och `PRODUKTER`).
