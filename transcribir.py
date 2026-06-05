#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
transcribir.py
--------------
Transcribe un video o audio a texto plano usando faster-whisper.

Para videos, extrae primero el audio a un WAV temporal (16 kHz mono) antes
de transcribir. Esto evita quedarse sin RAM al decodificar todo el audio de
golpe desde un archivo de video (critico en videos de varias horas).

Uso basico:
    python transcribir.py "mi video.mp4"
    python transcribir.py "mi video.mp4" --modelo base
    python transcribir.py "mi video.mp4" --modelo small --timestamps

Salida:
    Crea un archivo .txt con el mismo nombre del video, en la misma carpeta.

Flags:
    --modelo      tiny | base | small | medium | large-v3   (default: small)
                  base   = rapido, menos preciso
                  small  = buen equilibrio
                  medium / large = mas preciso, mucho mas lento en CPU
    --timestamps  agrega marcas de tiempo [hh:mm:ss] al inicio de cada bloque
    --idioma      forzar idioma (ej: en, es). Por defecto lo detecta solo.
"""

import argparse
import os
import struct
import sys
import tempfile

# Extensiones que faster-whisper puede leer directamente sin extraccion previa
_EXTENSIONES_AUDIO = {".wav", ".mp3", ".m4a", ".ogg", ".flac", ".aac", ".opus", ".wma"}


def hhmmss(segundos):
    s = int(segundos)
    h = s // 3600
    m = (s % 3600) // 60
    seg = s % 60
    return f"{h:02d}:{m:02d}:{seg:02d}"


def extraer_audio_wav(ruta_entrada, ruta_wav):
    """Extrae el audio de un video a WAV 16 kHz mono usando PyAV en modo
    streaming: procesa paquete a paquete sin cargar el audio completo en RAM."""
    import av

    RATE = 16000
    inp = av.open(ruta_entrada)
    astream = inp.streams.audio[0]
    resampler = av.AudioResampler(format="s16", layout="mono", rate=RATE)

    print(f"Extrayendo audio a WAV temporal ({RATE} Hz mono)...")
    with open(ruta_wav, "wb") as f:
        # Cabecera WAV con tamaños en cero; se corrigen al cerrar
        f.write(b"RIFF\x00\x00\x00\x00WAVEfmt ")
        f.write(struct.pack("<IHHIIHH", 16, 1, 1, RATE, RATE * 2, 2, 16))
        f.write(b"data\x00\x00\x00\x00")
        n_samples = 0
        for packet in inp.demux(astream):
            for frame in packet.decode():
                for rf in resampler.resample(frame):
                    data = bytes(rf.planes[0])
                    f.write(data)
                    n_samples += len(data) // 2
        total_bytes = n_samples * 2
        f.seek(4)
        f.write(struct.pack("<I", 36 + total_bytes))
        f.seek(40)
        f.write(struct.pack("<I", total_bytes))
    inp.close()

    mb = os.path.getsize(ruta_wav) / (1024 * 1024)
    print(f"Audio extraido: {mb:.0f} MB  ({n_samples / RATE / 3600:.2f} horas)")


def main():
    parser = argparse.ArgumentParser(
        description="Transcribe video/audio a .txt con faster-whisper"
    )
    parser.add_argument("entrada", help="Ruta del video o audio a transcribir")
    parser.add_argument(
        "--modelo",
        default="small",
        help="tiny | base | small | medium | large-v3 (default: small)",
    )
    parser.add_argument(
        "--timestamps",
        action="store_true",
        help="Agrega marcas de tiempo [hh:mm:ss] a cada bloque",
    )
    parser.add_argument(
        "--idioma",
        default=None,
        help="Forzar idioma (ej: en, es). Por defecto se detecta solo.",
    )
    args = parser.parse_args()

    if not os.path.isfile(args.entrada):
        print(f"No encuentro el archivo: {args.entrada}")
        sys.exit(1)

    # Import diferido para que --help no tarde en cargar el modelo
    from faster_whisper import WhisperModel

    # Extraer audio si la entrada es un video (no un archivo de audio ya puro)
    ext = os.path.splitext(args.entrada)[1].lower()
    wav_tmp = None
    ruta_transcribir = args.entrada

    if ext not in _EXTENSIONES_AUDIO:
        fd, wav_tmp = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        try:
            extraer_audio_wav(args.entrada, wav_tmp)
        except Exception as e:
            os.unlink(wav_tmp)
            print(f"Error extrayendo audio: {e}")
            sys.exit(1)
        ruta_transcribir = wav_tmp

    try:
        print(f"Cargando modelo '{args.modelo}' (la primera vez descarga el modelo)...")
        # int8 en CPU: rapido y con poca RAM. Si tenes GPU NVIDIA: device='cuda'.
        model = WhisperModel(args.modelo, device="cpu", compute_type="int8")

        print("Transcribiendo... (puede tardar; veras el progreso en %)")
        segments, info = model.transcribe(
            ruta_transcribir,
            language=args.idioma,
            vad_filter=False,
        )

        duracion = info.duration or 0
        print(f"Idioma detectado: {info.language}  |  Duracion: {hhmmss(duracion)}")

        salida = os.path.splitext(args.entrada)[0] + ".txt"

        bucket_anterior = -1
        with open(salida, "w", encoding="utf-8") as f:
            for seg in segments:
                texto = seg.text.strip()
                if args.timestamps:
                    f.write(f"[{hhmmss(seg.start)}] {texto}\n")
                else:
                    f.write(texto + " ")

                # Progreso por baldes de 5%
                if duracion > 0:
                    pct = int(seg.end / duracion * 100)
                    bucket = pct // 5
                    if bucket > bucket_anterior:
                        bucket_anterior = bucket
                        print(f"   {pct:>2d}%   ({hhmmss(seg.end)} / {hhmmss(duracion)})")

        print(f"\nListo. Transcripcion guardada en:\n{salida}")

    finally:
        if wav_tmp and os.path.exists(wav_tmp):
            os.unlink(wav_tmp)


if __name__ == "__main__":
    main()
