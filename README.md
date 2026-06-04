# videoestudio

Convierte videos de cursos en material de estudio: extrae la transcripción del
audio y las slides (diagramas y código) a un PDF, para después armar un resumen
de estudio en español con Claude.

La idea es dejar de mirar y escuchar 3+ horas de video. La máquina te saca el
texto y las pantallas; vos te concentrás en leer el resumen y **escribir tus
apuntes a mano**, que es donde de verdad se fija el aprendizaje.

---

## Qué hace cada script

- **`transcribir.py`** → pasa el audio a texto (`.txt`) con `faster-whisper`.
- **`slides.py`** → extrae las pantallas que cambian (diagramas, código) a un `.pdf`.

Los valores por defecto de `slides.py` están pensados para que el PDF se pueda
subir a Claude sin problemas: cada archivo queda por debajo de **28 MB** y de
**95 páginas** (los límites de Claude son 30 MB y ~100 páginas para el análisis
visual de las imágenes). Si hace falta, parte el PDF en varias partes
(`_parte1.pdf`, `_parte2.pdf`, …).

---

## Requisitos

- Python 3.10 o superior.
- `ffmpeg` (recomendado) para que `faster-whisper` lea cualquier formato de
  video sin problemas.

---

## Instalación

Cloná el repo e instalá las dependencias (una sola vez):

```bash
git clone https://github.com/TU_USUARIO/videoestudio.git
cd videoestudio
pip install faster-whisper opencv-python pillow
```

Instalá `ffmpeg`:

- **Windows:** `winget install Gyan.FFmpeg`
- **macOS:** `brew install ffmpeg`
- **Linux:** `sudo apt install ffmpeg`

La primera vez que corras `transcribir.py` se descarga el modelo de Whisper
(queda cacheado, no se vuelve a bajar).

---

## Uso

Poné el video en la misma carpeta que los scripts. En dos terminales separadas
(corren en paralelo, así no esperás uno y después el otro):

```bash
# 1) Transcripción (texto)
python transcribir.py "Curso de Go.mp4" --modelo small

# 2) Slides (PDF con diagramas y código)
python slides.py "Curso de Go.mp4"
```

### Ajustes rápidos

| Quiero…                                  | Comando                       |
|------------------------------------------|-------------------------------|
| Transcripción más rápida (menos precisa) | `--modelo base`               |
| Transcripción más precisa                | `--modelo small` o `medium`   |
| Marcas de tiempo en la transcripción     | `--timestamps`                |
| Menos slides (repite pantallas)          | `--umbral 12` (o más alto)    |
| Más slides (se saltea pantallas)         | `--umbral 4` (o más bajo)     |
| Procesar slides más rápido               | `--intervalo 3`               |
| PDF más liviano                          | `--calidad 65`                |
| Partir el PDF en trozos más chicos       | `--max-mb 20`                 |

---

## Después: el resumen en Claude

**1.** Creá un proyecto por curso (ej. "Curso de Go"). Un proyecto por curso, no
los mezcles.

**2.** Pegá estas instrucciones una sola vez, en la configuración del proyecto:

```
Resumí en español. Mantené los términos técnicos en inglés tal como aparecen en
el curso, con una breve explicación la primera vez que cada uno aparece. Cuando
una idea dependa de un diagrama o de código mostrado en las slides, marcalo e
indicá a qué slide del PDF corresponde.
```

**3.** Subí el `.txt` y el `.pdf` (todas las partes, si se partió) a la base de
conocimiento del proyecto.

**4.** Pedí el resumen ilustrado pegando esto en un chat del proyecto:

```
Te subí la transcripción (.txt) y el PDF de slides de un curso (si hay varias
partes, son todas del mismo video en orden). Armame un documento de estudio
descargable en HTML (.html), en un solo archivo con las imágenes embebidas
(base64, sin archivos sueltos), estilo informe pero con las imágenes reales de
las slides embebidas, no solo referenciadas. Instrucciones:

- Resumí en español. Mantené los términos técnicos en inglés tal como aparecen
  en el curso, con una breve explicación la primera vez que aparece cada uno.
- Organizá el resumen por temas/secciones, siguiendo el orden del curso.
- Para cada idea que dependa de un diagrama o de código mostrado en pantalla,
  extraé del PDF la slide correspondiente e insertá la imagen real al lado (o
  debajo) de esa explicación.
- Emparejá cada slide con la explicación por contenido (la transcripción y las
  slides no están sincronizadas). Si no estás seguro de un emparejamiento,
  marcalo con una nota tipo "[revisar: posible slide X]".
- No metas todas las slides: elegí solo las que aportan (diagramas y bloques de
  código importantes) y descartá las pantallas repetidas o intermedias.
- Al final, dejá una lista corta de las slides que incluiste con su número, para
  poder cruzarlas con el PDF. Cuando termines, dame el .html para descargar.
```

**5.** Leelo con las slides al lado y **escribí tu resumen a mano**. Ese paso es
el que de verdad fija el aprendizaje: no lo saltees ni lo apures.

---

## Dónde está la velocidad

Los pasos de máquina (transcribir y sacar slides) corren solos de fondo. Tu
tiempo enfocado es leer el resumen y escribir tus apuntes. Eliminás mirar y
escuchar horas de video, que era el verdadero ladrón de tiempo.
