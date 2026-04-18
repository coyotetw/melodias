# 🎸 YouTube → Melodía para Guitarra

Extraé la melodía principal de cualquier canción de YouTube y convertila a MIDI para guiarte al tocar guitarra.

## ¿Qué hace?

1. **Descarga el audio** de cualquier URL de YouTube (vía `yt-dlp`)
2. **Separa la melodía** del acompañamiento usando IA (Meta's `Demucs`)
3. **Convierte a MIDI** detectando las notas exactas (Spotify's `Basic Pitch`)
4. Te da un **WAV para escuchar** y tararear + un **MIDI para ver las notas** en MuseScore/GarageBand

## Deploy en Streamlit Cloud

1. Hacé fork de este repo
2. Entrá a [share.streamlit.io](https://share.streamlit.io)
3. Conectá tu repo → seleccioná `app.py`
4. ¡Listo!

> ⚠️ **Nota**: El procesamiento puede tardar 2-5 minutos por canción porque Demucs es un modelo pesado. Streamlit Cloud tiene límite de memoria (1GB), por lo que se recomienda usar canciones de menos de 5 minutos.

## Uso local

```bash
# Clonar repo
git clone <tu-repo>
cd youtube-to-melody

# Instalar dependencias del sistema (Ubuntu/Debian)
sudo apt-get install ffmpeg libsndfile1

# Instalar dependencias Python
pip install -r requirements.txt

# Correr la app
streamlit run app.py
```

## Cómo usar el MIDI resultante

- **[MuseScore](https://musescore.org)** (gratis) → Ve las notas en partitura
- **GarageBand** (Mac/iOS) → Importá el MIDI y mirá el piano roll
- **Guitar Pro** → Te genera tablatura de guitarra automáticamente
- **[MIDI.js](https://cifkao.github.io/html-midi-player/)** → Reproducilo online sin instalar nada

## Stack técnico

| Herramienta | Uso |
|---|---|
| `yt-dlp` | Descarga audio de YouTube |
| `Demucs` (Meta AI) | Separa voz/melodía del fondo |
| `Basic Pitch` (Spotify) | Convierte audio a MIDI |
| `Streamlit` | Interfaz web |
| `FFmpeg` | Procesamiento de audio |

## Limitaciones

- Solo para uso personal/educativo
- Canciones largas (>5 min) pueden agotar la memoria en Streamlit Cloud
- La calidad del MIDI depende de qué tan clara sea la melodía en la canción
