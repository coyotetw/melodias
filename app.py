import streamlit as st
import yt_dlp
import os
import tempfile
import shutil
import numpy as np
from pathlib import Path

st.set_page_config(
    page_title="🎸 YouTube → Melodía para Guitarra",
    page_icon="🎸",
    layout="centered"
)

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Bebas+Neue&family=Inter:wght@300;400;600&display=swap');
    .main { background: #0d0d0d; }
    h1 { font-family: 'Bebas Neue', sans-serif; font-size: 3rem !important; color: #f5c518; letter-spacing: 2px; }
    .subtitle { font-family: 'Inter', sans-serif; color: #aaa; font-weight: 300; font-size: 1.1rem; margin-top: -1rem; margin-bottom: 2rem; }
    .step-box { background: #1a1a1a; border-left: 4px solid #f5c518; padding: 1rem 1.5rem; border-radius: 4px; margin: 1rem 0; }
    .step-box p { color: #ddd; font-family: 'Inter', sans-serif; margin: 0; }
    .tip { background: #1a1a2e; border: 1px solid #3a3a6e; padding: 1rem; border-radius: 8px; color: #a0a0ff; font-size: 0.9rem; }
</style>
""", unsafe_allow_html=True)

st.markdown("<h1>🎸 YouTube → Melodía</h1>", unsafe_allow_html=True)
st.markdown('<p class="subtitle">Extraé la melodía principal de cualquier canción para tararearla en guitarra</p>', unsafe_allow_html=True)

st.markdown("""
<div class="step-box">
<p>📥 <b>Paso 1:</b> Pegá el link de YouTube →
🎵 <b>Paso 2:</b> Aislamos la melodía (filtro armónico) →
🎼 <b>Paso 3:</b> Convertimos a MIDI →
🎸 <b>Paso 4:</b> ¡Tocala en guitarra!</p>
</div>
""", unsafe_allow_html=True)

youtube_url = st.text_input(
    "🔗 URL de YouTube",
    placeholder="https://www.youtube.com/watch?v=...",
    help="Pegá el link completo del video de YouTube"
)

col1, col2 = st.columns(2)
with col1:
    separar_armonicos = st.checkbox("🎵 Aislar componente armónica", value=True,
        help="Separa la melodía del ritmo/percusión usando librosa (HPSS)")
with col2:
    generar_midi = st.checkbox("🎼 Generar archivo MIDI", value=True,
        help="Detecta el pitch frame a frame y genera un archivo MIDI")

duracion_max = st.slider("⏱️ Duración máxima a procesar (segundos)", 30, 240, 120, 10,
    help="Limitá la duración para evitar quedarte sin memoria")

st.markdown('<div class="tip">💡 <b>Tip:</b> Abrí el MIDI en <a href="https://musescore.org" target="_blank">MuseScore</a> (gratis) para ver las notas en partitura, o en GarageBand / Guitar Pro para ver tablatura.</div>', unsafe_allow_html=True)


def separar_melodia(y: np.ndarray, sr: int) -> np.ndarray:
    """Separa la componente armónica (melodía) de la percusiva usando HPSS de librosa."""
    import librosa
    y_harm, _ = librosa.effects.hpss(y, margin=3.0)
    return y_harm


def audio_a_midi(y: np.ndarray, sr: int, midi_path: str, min_freq: float = 80.0, confianza_min: float = 0.15) -> int:
    """
    Detecta pitch frame a frame con librosa.pyin (más preciso que piptrack)
    y construye un archivo MIDI con midiutil.
    """
    import librosa
    from midiutil import MIDIFile

    # pyin: probabilistic YIN, muy bueno para melodías monofónicas
    f0, voiced_flag, voiced_probs = librosa.pyin(
        y,
        fmin=librosa.note_to_hz('C2'),   # ~65 Hz
        fmax=librosa.note_to_hz('C7'),   # ~2093 Hz
        sr=sr,
        frame_length=2048,
        hop_length=512,
    )

    # Tiempo de cada frame
    times = librosa.times_like(f0, sr=sr, hop_length=512)

    # Construir MIDI
    midi = MIDIFile(1)
    track, channel = 0, 0
    tempo = 120
    midi.addTempo(track, 0, tempo)

    beats_per_sec = tempo / 60.0
    notas_agregadas = 0

    note_start_beat = None
    note_start_time = None
    prev_midi_note = None

    def cerrar_nota(t_end):
        nonlocal notas_agregadas
        if note_start_time is not None and prev_midi_note is not None:
            dur_seg = t_end - note_start_time
            if dur_seg >= 0.05:  # ignorar notas < 50ms
                start_beat = note_start_time * beats_per_sec
                dur_beat = dur_seg * beats_per_sec
                midi.addNote(track, channel, prev_midi_note, start_beat, dur_beat, 80)
                notas_agregadas += 1

    for t, freq, voiced in zip(times, f0, voiced_flag):
        if not voiced or freq is None or np.isnan(freq) or freq < min_freq:
            cerrar_nota(t)
            note_start_time = None
            prev_midi_note = None
            continue

        midi_note = int(np.round(69 + 12 * np.log2(freq / 440.0)))
        midi_note = max(0, min(127, midi_note))

        if prev_midi_note is None:
            note_start_time = float(t)
            prev_midi_note = midi_note
        elif midi_note != prev_midi_note:
            cerrar_nota(float(t))
            note_start_time = float(t)
            prev_midi_note = midi_note

    # Cerrar última nota
    if times[-1] is not None:
        cerrar_nota(float(times[-1]))

    with open(midi_path, "wb") as f:
        midi.writeFile(f)

    return notas_agregadas


def guardar_wav(y: np.ndarray, sr: int, path: str):
    import soundfile as sf
    sf.write(path, y, sr)


if st.button("🚀 Extraer Melodía", type="primary", use_container_width=True):
    if not youtube_url or ("youtube.com" not in youtube_url and "youtu.be" not in youtube_url):
        st.error("❌ Por favor ingresá una URL válida de YouTube")
        st.stop()

    work_dir = tempfile.mkdtemp()
    title = "canción"

    try:
        # --- PASO 1: Descargar audio ---
        with st.status("📥 Descargando audio de YouTube...", expanded=True) as status:
            st.write("Conectando con YouTube...")
            audio_out = os.path.join(work_dir, "audio")

            ydl_opts = {
                "format": "bestaudio/best",
                "outtmpl": audio_out,
                "postprocessors": [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "wav",
                    "preferredquality": "192",
                }],
                "quiet": True,
                "no_warnings": True,
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(youtube_url, download=True)
                title = info.get("title", "canción")

            # Buscar el wav descargado
            audio_path = audio_out + ".wav"
            if not os.path.exists(audio_path):
                for f in os.listdir(work_dir):
                    if f.endswith(".wav"):
                        audio_path = os.path.join(work_dir, f)
                        break

            if not os.path.exists(audio_path):
                st.error("❌ No se pudo encontrar el archivo de audio. ¿El video es público?")
                st.stop()

            st.write(f"✅ Descargado: **{title}**")
            status.update(label=f"✅ Audio descargado: {title}", state="complete")

        # --- PASO 2: Cargar con librosa y recortar ---
        with st.status("🎵 Cargando y procesando audio...", expanded=True) as status:
            import librosa

            st.write(f"Cargando primeros {duracion_max}s en mono a 22050 Hz...")
            y, sr = librosa.load(audio_path, sr=22050, mono=True, duration=duracion_max)
            st.write(f"✅ Audio cargado: {len(y)/sr:.1f}s, {sr}Hz")

            melody_wav_path = os.path.join(work_dir, "melodia.wav")

            if separar_armonicos:
                st.write("Separando componente armónica (HPSS)...")
                y_melody = separar_melodia(y, sr)
                guardar_wav(y_melody, sr, melody_wav_path)
                st.write("✅ Melodía armónica aislada")
            else:
                y_melody = y
                guardar_wav(y_melody, sr, melody_wav_path)

            status.update(label="✅ Audio procesado", state="complete")

        # --- PASO 3: Generar MIDI ---
        midi_path = None
        if generar_midi:
            with st.status("🎼 Detectando notas y generando MIDI...", expanded=True) as status:
                st.write("Usando pYIN para detección de pitch (esto tarda ~30s)...")
                midi_path = os.path.join(work_dir, "melodia.mid")
                n_notas = audio_a_midi(y_melody, sr, midi_path)
                st.write(f"✅ MIDI generado con {n_notas} notas")
                status.update(label=f"✅ MIDI listo — {n_notas} notas detectadas", state="complete")

        # --- PASO 4: Resultados ---
        st.success(f"🎉 ¡Listo! **{title}**")
        st.subheader("📁 Descargar archivos")

        col_a, col_b = st.columns(2)

        with col_a:
            if os.path.exists(melody_wav_path):
                with open(melody_wav_path, "rb") as f:
                    wav_bytes = f.read()
                st.download_button(
                    label="🎤 Descargar Melodía (WAV)",
                    data=wav_bytes,
                    file_name=f"melodia_{title[:30]}.wav",
                    mime="audio/wav",
                    use_container_width=True
                )
                st.caption("Escuchala para guiarte al tararear")
                st.audio(wav_bytes, format="audio/wav")

        with col_b:
            if midi_path and os.path.exists(midi_path):
                with open(midi_path, "rb") as f:
                    midi_bytes = f.read()
                st.download_button(
                    label="🎼 Descargar MIDI",
                    data=midi_bytes,
                    file_name=f"melodia_{title[:30]}.mid",
                    mime="audio/midi",
                    use_container_width=True
                )
                st.caption("Abrí en MuseScore para ver las notas")

        st.subheader("🎸 ¿Cómo usar el MIDI?")
        st.markdown("""
        1. **[MuseScore](https://musescore.org)** (gratis) → Importá el `.mid` y ves la partitura con todas las notas
        2. **[Guitar Pro](https://www.guitar-pro.com)** → Te genera la tablatura de guitarra automáticamente
        3. **GarageBand** (Mac/iOS) → Piano roll visual con las notas
        4. **[MIDI.js online](https://cifkao.github.io/html-midi-player/)** → Reproducilo en el browser sin instalar nada
        """)

    except Exception as e:
        st.error(f"❌ Error: {str(e)}")
        st.info("Verificá que el link sea público y el video esté disponible en tu región.")
        import traceback
        with st.expander("Detalle técnico del error"):
            st.code(traceback.format_exc())
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)

st.divider()
st.markdown("""
<p style="color:#555; font-size:0.8rem; text-align:center;">
Powered by <b>yt-dlp</b> · <b>librosa</b> (HPSS + pYIN) · <b>midiutil</b> | Solo para uso personal y educativo
</p>
""", unsafe_allow_html=True)
