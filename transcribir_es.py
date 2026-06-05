#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
transcribir_es.py
-----------------
Igual que transcribir.py pero fuerza idioma español por defecto,
lo que evita que Whisper detecte mal el idioma en videos en castellano.

Uso basico:
    python transcribir_es.py "mi video.mp4"
    python transcribir_es.py "mi video.mp4" --modelo small --timestamps

Flags:
    --modelo      tiny | base | small | medium | large-v3   (default: small)
    --timestamps  agrega marcas de tiempo [hh:mm:ss] al inicio de cada bloque
    --idioma      forzar otro idioma si hace falta (default: es)
"""

import argparse
import os
import struct
import sys
import tempfile

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
        description="Transcribe video/audio en español a .txt con faster-whisper"
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
        default="es",
        help="Forzar idioma (default: es)",
    )
    args = parser.parse_args()

    if not os.path.isfile(args.entrada):
        print(f"No encuentro el archivo: {args.entrada}")
        sys.exit(1)

    from faster_whisper import WhisperModel

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
        model = WhisperModel(args.modelo, device="cpu", compute_type="int8")

        print("Transcribiendo... (puede tardar; veras el progreso en %)")
        segments, info = model.transcribe(
            ruta_transcribir,
            language=args.idioma,
            vad_filter=True,
        )

        duracion = info.duration or 0
        print(f"Idioma: {info.language}  |  Duracion: {hhmmss(duracion)}")

        salida = os.path.splitext(args.entrada)[0] + ".txt"

        bucket_anterior = -1
        with open(salida, "w", encoding="utf-8") as f:
            for seg in segments:
                texto = seg.text.strip()
                if args.timestamps:
                    f.write(f"[{hhmmss(seg.start)}] {texto}\n")
                else:
                    f.write(texto + " ")

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
