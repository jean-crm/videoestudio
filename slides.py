#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
slides.py
---------
Extrae las "pantallas" (slides) de un video y las guarda en un PDF,
quedandose solo con los frames que cambian de verdad. Sirve para no perder
los diagramas y el codigo que el video muestra y que una transcripcion no captura.

Los valores por defecto estan pensados para que el/los PDF resultantes se
puedan subir a Claude sin problemas:
  - Cada PDF queda por debajo de 28 MB  (limite de Claude: 30 MB por archivo).
  - Cada PDF queda en 95 paginas o menos (Claude analiza las imagenes de un PDF
    como visual solo si tiene menos de ~100 paginas; pasado eso se queda con el
    texto, que en capturas de pantalla no sirve).
Si hace falta, parte el PDF en varias partes para respetar ambos limites.

Uso basico:
    python slides.py "mi video.mp4"
    python slides.py "mi video.mp4" --umbral 12
    python slides.py "mi video.mp4" --umbral 12 --calidad 70

Salida:
    Crea "mi video.pdf" en la misma carpeta. Si hay que partirlo, genera
    "mi video_parte1.pdf", "mi video_parte2.pdf", etc.

Flags:
    --intervalo    cada cuantos segundos mira un frame del video (default: 2)
    --umbral       cuanto tiene que cambiar la imagen para contar como slide
                   nueva (0-255). Mas bajo = mas slides; mas alto = menos.
                   default: 8   (probar 4 si se saltea pantallas, 12 si repite)
    --calidad      calidad JPEG de las imagenes dentro del PDF (1-95). default: 75
    --max-mb       tamano maximo por PDF en MB antes de partirlo. default: 28
                   (margen seguro bajo el limite de 30 MB de Claude)
    --max-paginas  paginas maximas por PDF antes de partirlo. default: 95
                   (margen seguro bajo el limite de ~100 paginas de Claude)
"""

import argparse
import os
import sys
import io


def main():
    parser = argparse.ArgumentParser(
        description="Extrae slides de un video a PDF (listo para subir a Claude)"
    )
    parser.add_argument("video", help="Ruta del video")
    parser.add_argument("--intervalo", type=float, default=2.0,
                        help="Segundos entre frames muestreados (default: 2)")
    parser.add_argument("--umbral", type=float, default=8.0,
                        help="Diferencia minima para nueva slide, 0-255 (default: 8)")
    parser.add_argument("--calidad", type=int, default=75,
                        help="Calidad JPEG 1-95 (default: 75)")
    parser.add_argument("--max-mb", type=float, default=28.0,
                        help="Tamano maximo por PDF en MB (default: 28)")
    parser.add_argument("--max-paginas", type=int, default=95,
                        help="Paginas maximas por PDF (default: 95)")
    args = parser.parse_args()

    if not os.path.isfile(args.video):
        print(f"No encuentro el archivo: {args.video}")
        sys.exit(1)

    import cv2
    from PIL import Image

    cap = cv2.VideoCapture(args.video)
    if not cap.isOpened():
        print("No pude abrir el video.")
        sys.exit(1)

    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    total_frames = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0
    duracion = total_frames / fps if fps else 0
    salto = max(1, int(round(fps * args.intervalo)))

    print(f"FPS: {fps:.1f}  |  Duracion aprox: {duracion/60:.1f} min")
    print(f"Mirando un frame cada {args.intervalo} s (umbral={args.umbral})...")

    slides = []          # imagenes PIL aceptadas
    ref_pequena = None   # frame anterior reducido a gris para comparar
    idx = 0

    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if idx % salto == 0:
            # Reducir a 32x32 gris para comparar rapido y robusto
            pequena = cv2.resize(frame, (32, 32))
            pequena = cv2.cvtColor(pequena, cv2.COLOR_BGR2GRAY)

            es_nueva = ref_pequena is None
            if not es_nueva:
                dif = cv2.absdiff(pequena, ref_pequena).mean()
                es_nueva = dif >= args.umbral

            if es_nueva:
                ref_pequena = pequena
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                slides.append(Image.fromarray(rgb))
                seg = idx / fps if fps else 0
                print(f"   slide {len(slides):>3d}  (t={int(seg)//60:02d}:{int(seg)%60:02d})")
        idx += 1

    cap.release()

    if not slides:
        print("No detecte ninguna slide. Proba bajar --umbral.")
        sys.exit(1)

    base = os.path.splitext(args.video)[0]
    print(f"\nTotal de slides detectadas: {len(slides)}")
    guardar_pdf(slides, base, args.calidad, args.max_mb, args.max_paginas)


def guardar_pdf(slides, base, calidad, max_mb, max_paginas):
    """Guarda las slides en uno o varios PDF, respetando a la vez el limite de
    tamano (max_mb) y de paginas (max_paginas) para que se puedan subir a Claude."""

    def jpeg_bytes(im):
        buf = io.BytesIO()
        im.convert("RGB").save(buf, format="JPEG", quality=calidad)
        return buf.tell()

    def escribir(imgs, ruta):
        imgs[0].convert("RGB").save(
            ruta, "PDF", save_all=True,
            append_images=[im.convert("RGB") for im in imgs[1:]],
            quality=calidad,
        )
        mb = os.path.getsize(ruta) / (1024 * 1024)
        print(f"   guardado: {ruta}  ({mb:.1f} MB, {len(imgs)} paginas)")

    limite_bytes = max_mb * 1024 * 1024

    # Armar trozos de forma codiciosa: cada trozo respeta el tope de paginas
    # y el tope de tamano (estimado por la suma de los JPEG, que es casi igual
    # al PDF final salvo unos KB de estructura por pagina).
    trozos = []
    actual = []
    acum = 0
    for im in slides:
        b = jpeg_bytes(im)
        supera_pag = len(actual) >= max_paginas
        supera_mb = bool(actual) and (acum + b > limite_bytes)
        if supera_pag or supera_mb:
            trozos.append(actual)
            actual = []
            acum = 0
        actual.append(im)
        acum += b
    if actual:
        trozos.append(actual)

    if len(trozos) == 1:
        escribir(trozos[0], base + ".pdf")
        return

    print(f"Para respetar los limites de Claude (<= {max_mb:.0f} MB y "
          f"<= {max_paginas} paginas por archivo) lo parto en {len(trozos)}.")
    for n, trozo in enumerate(trozos, 1):
        escribir(trozo, f"{base}_parte{n}.pdf")


if __name__ == "__main__":
    main()
