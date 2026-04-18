import streamlit as st
import os
import tempfile
import shutil
import numpy as np
from pathlib import Path

st.set_page_config(
    page_title="🎸 Melodía para Guitarra",
    page_icon="🎸",
    layout="centered"
)

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Bebas+Neue&family=Inter:wght@300;400;600&display=swap');
    h1 { font-family: 'Bebas Neue', sans-serif; font-size: 3rem !important; color: #f5c518; letter-spacing: 2px; }
    .subtitle { font-family: 'Inter', sans-serif; color: #aaa; font-weight: 300; font-size: 1.1rem; margin-top: -1rem; margin-bottom: 2rem; }
    .step-box { background: #1a1a1a; border-left: 4px solid #f5c518; padding: 1rem 1.5rem; border-radius: 4px; margin: 1rem 0; }
    .step-box p { color: #ddd; font-family: 'Inter', sans-serif; margin: 0; }
    .tip { background: #1a1a2e; border: 1px solid #3a3a6e; padding: 1rem; border-radius: 8px; color: #a0a0ff; font-size: 0.9rem; margin: 1rem 0; }
    .warn { background: #2e1a1a; border: 1px solid #6e3a3a; padding: 1rem; border-radius: 8px; color: #ffaaaa; font-size: 0.9rem; margin: 1rem 0; }
</style>
""", unsafe_allow_html=True)

st.markdown("<h1>🎸 Extraer Melodía</h1>", unsafe_allow_html=True)
st.markdown('<p class="subtitle">Subí un audio o video y extraemos la melodía principal para que la tararees en guitarra</p>', unsafe_allow_html=True)

st.markdown("""
<div class="step-box">
<p>📁 <b>Paso 1:</b> Subí tu archivo de audio o video →
🎵 <b>Paso 2:</b> Aislamos la melodía →
🎼 <b>Paso 3:</b> Generamos el MIDI →
🎸 <b>Paso 4:</b> ¡Tocala en guitarra!</p>
</div>
""", unsafe_allow_html=True)

# --- Instrucciones para bajar de YouTube localmente ---
with st.expander("💡 ¿Cómo bajo el audio de YouTube a mi computadora?"):
    st.markdown("""
    **Opción 1 — yt-dlp (recomendado, gratis):**
    ```bash
    # Instalás yt-dlp una vez
    pip install yt-dlp

    # Descargás solo el audio en mp3
    yt-dlp -x --audio-format mp3 "https://www.youtube.com/watch?v=..."
    ```

    **Opción 2 — Sitios web gratuitos:**
    - [cobalt.tools](https://cobalt.tools) — el más confiable, sin publicidad
    - [yt1s.com](https://yt1s.com) — también funciona bien

    Después subís el mp3/mp4 acá directamente ↓
    """)

# --- Upload ---
archivo = st.file_uploader(
    "📁 Subí tu archivo de audio o video",
    type=["mp3", "wav", "ogg", "flac", "m4a", "mp4", "webm", "mkv", "avi"],
    help="Formatos soportados: MP3, WAV, OGG, FLAC, M4A, MP4, WEBM, MKV, AVI"
)

if archivo:
    st.markdown(f'<div class="tip">✅ Archivo cargado: <b>{archivo.name}</b> ({archivo.size/1024/1024:.1f} MB)</div>', unsafe_allow_html=True)

st.divider()

col1, col2 = st.columns(2)
with col1:
    separar_armonicos = st.checkbox("🎵 Aislar componente armónica", value=True,
        help="Separa la melodía del ritmo/percusión (HPSS de librosa)")
with col2:
    generar_midi = st.checkbox("🎼 Generar archivo MIDI", value=True,
        help="Detecta el pitch y genera un MIDI con las notas")

duracion_max = st.slider("⏱️ Duración máxima a procesar (segundos)", 30, 300, 150, 10,
    help="Limitá para no quedarte sin memoria. 150s suele ser suficiente para la melodía principal.")

st.markdown('<div class="tip">💡 Abrí el MIDI en <a href="https://musescore.org" target="_blank"><b>MuseScore</b></a> (gratis) para ver la partitura, o en Guitar Pro para ver tablatura.</div>', unsafe_allow_html=True)


def separar_melodia(y, sr):
    import librosa
    y_harm, _ = librosa.effects.hpss(y, margin=3.0)
    return y_harm


def audio_a_midi(y, sr, midi_path):
    import librosa
    from midiutil import MIDIFile

    f0, voiced_flag, _ = librosa.pyin(
        y,
        fmin=librosa.note_to_hz('C2'),
        fmax=librosa.note_to_hz('C7'),
        sr=sr,
        frame_length=2048,
        hop_length=512,
    )

    times = librosa.times_like(f0, sr=sr, hop_length=512)

    midi = MIDIFile(1)
    midi.addTempo(0, 0, 120)
    beats_per_sec = 120 / 60.0
    notas = 0

    note_start_time = None
    prev_note = None

    def cerrar_nota(t_end):
        nonlocal notas
        if note_start_time is not None and prev_note is not None:
            dur = t_end - note_start_time
            if dur >= 0.05:
                midi.addNote(0, 0, prev_note, note_start_time * beats_per_sec, dur * beats_per_sec, 80)
                notas += 1

    for t, freq, voiced in zip(times, f0, voiced_flag):
        if not voiced or freq is None or np.isnan(freq) or freq < 60:
            cerrar_nota(float(t))
            note_start_time = None
            prev_note = None
            continue

        midi_note = int(np.round(69 + 12 * np.log2(freq / 440.0)))
        midi_note = max(0, min(127, midi_note))

        if prev_note is None:
            note_start_time = float(t)
            prev_note = midi_note
        elif midi_note != prev_note:
            cerrar_nota(float(t))
            note_start_time = float(t)
            prev_note = midi_note

    cerrar_nota(float(times[-1]) if len(times) > 0 else 0)

    with open(midi_path, "wb") as f:
        midi.writeFile(f)

    return notas


def convertir_a_wav_con_ffmpeg(input_path, output_path):
    """Convierte cualquier formato a WAV usando ffmpeg."""
    import subprocess
    result = subprocess.run(
        ["ffmpeg", "-y", "-i", input_path, "-ac", "1", "-ar", "22050", output_path],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg error: {result.stderr[-500:]}")


if st.button("🚀 Extraer Melodía", type="primary", use_container_width=True, disabled=archivo is None):

    if archivo is None:
        st.error("❌ Primero subí un archivo de audio o video")
        st.stop()

    work_dir = tempfile.mkdtemp()

    try:
        # --- PASO 1: Guardar archivo subido ---
        with st.status("💾 Guardando archivo...", expanded=True) as status:
            ext = Path(archivo.name).suffix.lower()
            input_path = os.path.join(work_dir, f"input{ext}")
            wav_path = os.path.join(work_dir, "audio.wav")

            with open(input_path, "wb") as f:
                f.write(archivo.read())

            st.write(f"✅ Guardado: {archivo.name}")

            # Convertir a WAV si no lo es ya
            if ext != ".wav":
                st.write("Convirtiendo a WAV con FFmpeg...")
                convertir_a_wav_con_ffmpeg(input_path, wav_path)
            else:
                import shutil as sh
                sh.copy(input_path, wav_path)

            status.update(label="✅ Archivo listo", state="complete")

        # --- PASO 2: Cargar con librosa ---
        with st.status("🎵 Cargando audio...", expanded=True) as status:
            import librosa
            import soundfile as sf

            st.write(f"Cargando primeros {duracion_max}s...")
            y, sr = librosa.load(wav_path, sr=22050, mono=True, duration=duracion_max)
            st.write(f"✅ {len(y)/sr:.1f}s cargados a {sr}Hz")

            melody_path = os.path.join(work_dir, "melodia.wav")

            if separar_armonicos:
                st.write("Aislando componente armónica (HPSS)...")
                y_melody = separar_melodia(y, sr)
            else:
                y_melody = y

            sf.write(melody_path, y_melody, sr)
            status.update(label="✅ Audio procesado", state="complete")

        # --- PASO 3: MIDI ---
        midi_path = None
        if generar_midi:
            with st.status("🎼 Detectando notas y generando MIDI...", expanded=True) as status:
                st.write("Analizando pitch con pYIN (puede tardar 30-60s)...")
                midi_path = os.path.join(work_dir, "melodia.mid")
                n = audio_a_midi(y_melody, sr, midi_path)
                st.write(f"✅ {n} notas detectadas")
                status.update(label=f"✅ MIDI listo — {n} notas", state="complete")

        # --- PASO 4: Descargas ---
        nombre_base = Path(archivo.name).stem[:30]
        st.success("🎉 ¡Procesamiento completado!")
        st.subheader("📁 Tus archivos")

        col_a, col_b = st.columns(2)

        with col_a:
            if os.path.exists(melody_path):
                with open(melody_path, "rb") as f:
                    wav_bytes = f.read()
                st.download_button("🎤 Descargar Melodía WAV", wav_bytes,
                    file_name=f"melodia_{nombre_base}.wav", mime="audio/wav",
                    use_container_width=True)
                st.caption("Escuchala para guiarte")
                st.audio(wav_bytes, format="audio/wav")

        with col_b:
            if midi_path and os.path.exists(midi_path):
                with open(midi_path, "rb") as f:
                    midi_bytes = f.read()
                st.download_button("🎼 Descargar MIDI", midi_bytes,
                    file_name=f"melodia_{nombre_base}.mid", mime="audio/midi",
                    use_container_width=True)
                st.caption("Abrí en MuseScore / Guitar Pro")

        st.subheader("🎸 ¿Cómo usar el MIDI?")
        st.markdown("""
        | Programa | Qué te muestra | Precio |
        |---|---|---|
        | [MuseScore](https://musescore.org) | Partitura con notas | Gratis |
        | [Guitar Pro](https://www.guitar-pro.com) | Tablatura de guitarra | Pago |
        | GarageBand (Mac/iOS) | Piano roll visual | Gratis |
        | [html-midi-player](https://cifkao.github.io/html-midi-player/) | Reproducción en browser | Gratis online |
        """)

    except Exception as e:
        st.error(f"❌ Error: {str(e)}")
        import traceback
        with st.expander("Ver detalle del error"):
            st.code(traceback.format_exc())
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)

elif archivo is None:
    st.markdown('<div class="warn">⬆️ Subí un archivo arriba para habilitar el botón de procesar.</div>', unsafe_allow_html=True)

st.divider()
st.markdown("""
<p style="color:#555; font-size:0.8rem; text-align:center;">
Powered by <b>librosa</b> (HPSS + pYIN) · <b>midiutil</b> · <b>FFmpeg</b> | Solo para uso personal y educativo
</p>
""", unsafe_allow_html=True)
