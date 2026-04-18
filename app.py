import streamlit as st
import yt_dlp
import os
import subprocess
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
🎵 <b>Paso 2:</b> Separamos la melodía vocal/principal → 
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
    separar_stems = st.checkbox("🎤 Separar melodía del fondo", value=True,
        help="Usa Demucs para aislar la voz/melodía principal (recomendado)")
with col2:
    generar_midi = st.checkbox("🎼 Generar archivo MIDI", value=True,
        help="Convierte la melodía a MIDI usando CREPE (detección de pitch por IA)")

st.markdown('<div class="tip">💡 <b>Tip:</b> El MIDI te va a mostrar las notas exactas. Podés abrirlo en MuseScore (gratis) para ver la partitura, o en GarageBand / cualquier DAW.</div>', unsafe_allow_html=True)


def audio_to_midi(audio_path: str, midi_out_path: str, min_confidence: float = 0.5):
    """
    Detecta el pitch frame a frame con CREPE y genera un MIDI.
    No usa TensorFlow directamente — crepe lo maneja internamente.
    """
    import crepe
    import librosa
    import pretty_midi
    import soundfile as sf

    # Cargar audio en mono, 16kHz (ideal para crepe)
    y, sr = librosa.load(audio_path, sr=16000, mono=True)

    # Limitar a 4 minutos para no agotar memoria
    max_samples = 4 * 60 * sr
    if len(y) > max_samples:
        y = y[:max_samples]

    # Detectar pitch con CREPE (modelo "tiny" para ser liviano)
    time, frequency, confidence, _ = crepe.predict(y, sr, model_capacity="tiny", viterbi=True)

    # Construir MIDI a partir de las frecuencias detectadas
    midi = pretty_midi.PrettyMIDI(initial_tempo=120)
    instrument = pretty_midi.Instrument(program=0, name="Melodía")  # Piano como referencia

    dt = time[1] - time[0] if len(time) > 1 else 0.01
    note_on = None
    prev_note = None

    for t, freq, conf in zip(time, frequency, confidence):
        if conf < min_confidence or freq < 50:
            # Silencio — cerrar nota anterior si la hay
            if note_on is not None:
                note = pretty_midi.Note(
                    velocity=80,
                    pitch=prev_note,
                    start=note_on,
                    end=float(t)
                )
                instrument.notes.append(note)
                note_on = None
                prev_note = None
            continue

        midi_note = int(np.round(69 + 12 * np.log2(freq / 440)))
        midi_note = max(0, min(127, midi_note))

        if prev_note is None:
            note_on = float(t)
            prev_note = midi_note
        elif midi_note != prev_note:
            # Nueva nota diferente — cerrar la anterior
            note = pretty_midi.Note(
                velocity=80,
                pitch=prev_note,
                start=note_on,
                end=float(t)
            )
            instrument.notes.append(note)
            note_on = float(t)
            prev_note = midi_note

    # Cerrar última nota
    if note_on is not None and prev_note is not None:
        note = pretty_midi.Note(
            velocity=80,
            pitch=prev_note,
            start=note_on,
            end=float(t) + dt
        )
        instrument.notes.append(note)

    midi.instruments.append(instrument)
    midi.write(midi_out_path)
    return len(instrument.notes)


if st.button("🚀 Extraer Melodía", type="primary", use_container_width=True):
    if not youtube_url or ("youtube.com" not in youtube_url and "youtu.be" not in youtube_url):
        st.error("❌ Por favor ingresá una URL válida de YouTube")
        st.stop()

    work_dir = tempfile.mkdtemp()
    audio_path = None
    melody_path = None
    midi_path = None
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

            # yt-dlp puede guardar con extensión distinta, buscar el wav
            audio_path = audio_out + ".wav"
            if not os.path.exists(audio_path):
                for f in os.listdir(work_dir):
                    if f.endswith(".wav"):
                        audio_path = os.path.join(work_dir, f)
                        break

            if not audio_path or not os.path.exists(audio_path):
                st.error("❌ No se pudo encontrar el archivo de audio descargado.")
                st.stop()

            st.write(f"✅ Descargado: **{title}**")
            status.update(label=f"✅ Audio descargado: {title}", state="complete")

        # --- PASO 2: Separar stems con Demucs ---
        if separar_stems:
            with st.status("🎤 Separando melodía del acompañamiento (Demucs)...", expanded=True) as status:
                st.write("Esto puede tardar 2-4 minutos...")

                result = subprocess.run(
                    ["python", "-m", "demucs", "--two-stems=vocals", "-o", work_dir, audio_path],
                    capture_output=True, text=True, timeout=360
                )

                if result.returncode != 0:
                    st.warning(f"⚠️ Demucs tuvo un error, usando audio completo.\n{result.stderr[-300:]}")
                    melody_path = audio_path
                else:
                    vocals_candidates = list(Path(work_dir).rglob("vocals.wav"))
                    if vocals_candidates:
                        melody_path = str(vocals_candidates[0])
                        st.write("✅ Melodía/voz aislada correctamente")
                    else:
                        st.warning("⚠️ No se encontró archivo de vocals, usando audio completo")
                        melody_path = audio_path

                status.update(label="✅ Separación completada", state="complete")
        else:
            melody_path = audio_path

        # --- PASO 3: Convertir a MIDI con CREPE ---
        if generar_midi:
            with st.status("🎼 Detectando notas y generando MIDI (CREPE)...", expanded=True) as status:
                st.write("Analizando el pitch de la melodía...")

                midi_path = os.path.join(work_dir, "melodia.mid")
                n_notas = audio_to_midi(melody_path, midi_path)
                st.write(f"✅ MIDI generado con {n_notas} notas detectadas")
                status.update(label="✅ MIDI generado", state="complete")

        # --- PASO 4: Resultados ---
        st.success(f"🎉 ¡Listo! Melodía de **{title}** procesada")
        st.subheader("📁 Descargar archivos")

        col_a, col_b = st.columns(2)

        with col_a:
            if melody_path and os.path.exists(melody_path):
                with open(melody_path, "rb") as f:
                    st.download_button(
                        label="🎤 Descargar Melodía (WAV)",
                        data=f.read(),
                        file_name=f"melodia_{title[:30]}.wav",
                        mime="audio/wav",
                        use_container_width=True
                    )
                st.caption("Escuchala para guiarte al tararear")
                with open(melody_path, "rb") as f:
                    st.audio(f.read(), format="audio/wav")

        with col_b:
            if midi_path and os.path.exists(midi_path):
                with open(midi_path, "rb") as f:
                    st.download_button(
                        label="🎼 Descargar MIDI",
                        data=f.read(),
                        file_name=f"melodia_{title[:30]}.mid",
                        mime="audio/midi",
                        use_container_width=True
                    )
                st.caption("Abrí en MuseScore para ver las notas")

        st.subheader("🎸 ¿Cómo usarlo?")
        st.markdown("""
        1. **Escuchá el WAV** → Tararéala para internalizar la melodía
        2. **Abrí el MIDI en [MuseScore](https://musescore.org)** (gratis) → Te muestra las notas en partitura
        3. **O importá el MIDI en GarageBand / Guitar Pro** → Ves la tablatura directamente
        4. **Practicá nota por nota** usando el MIDI como guía de tempo y altura
        """)

    except subprocess.TimeoutExpired:
        st.error("⏱️ La operación tardó demasiado. Intentá con una canción más corta (menos de 4 min).")
    except Exception as e:
        st.error(f"❌ Error inesperado: {str(e)}")
        st.info("Asegurate de que la URL sea pública y que el video esté disponible.")
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)

st.divider()
st.markdown("""
<p style="color:#555; font-size:0.8rem; text-align:center;">
Powered by <b>yt-dlp</b> · <b>Demucs</b> (Meta AI) · <b>CREPE</b> (pitch detection) · <b>pretty_midi</b> | 
Solo para uso personal y educativo
</p>
""", unsafe_allow_html=True)
