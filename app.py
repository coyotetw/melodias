import streamlit as st
import yt_dlp
import os
import subprocess
import tempfile
import shutil
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
        help="Convierte la melodía a MIDI para ver las notas exactas")

st.markdown('<div class="tip">💡 <b>Tip:</b> El MIDI te va a mostrar las notas exactas. Podés abrirlo en MuseScore (gratis) para ver la partitura, o en GarageBand / cualquier DAW.</div>', unsafe_allow_html=True)

if st.button("🚀 Extraer Melodía", type="primary", use_container_width=True):
    if not youtube_url or "youtube.com" not in youtube_url and "youtu.be" not in youtube_url:
        st.error("❌ Por favor ingresá una URL válida de YouTube")
        st.stop()

    work_dir = tempfile.mkdtemp()
    audio_path = None
    melody_path = None
    midi_path = None

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

            audio_path = audio_out + ".wav"
            if not os.path.exists(audio_path):
                # buscar el archivo descargado
                for f in os.listdir(work_dir):
                    if f.endswith(".wav"):
                        audio_path = os.path.join(work_dir, f)
                        break

            st.write(f"✅ Descargado: **{title}**")
            status.update(label=f"✅ Audio descargado: {title}", state="complete")

        # --- PASO 2: Separar stems ---
        if separar_stems:
            with st.status("🎤 Separando melodía del acompañamiento...", expanded=True) as status:
                st.write("Esto puede tardar 1-3 minutos dependiendo de la canción...")

                result = subprocess.run(
                    ["python", "-m", "demucs", "--two-stems=vocals", "-o", work_dir, audio_path],
                    capture_output=True, text=True, timeout=300
                )

                if result.returncode != 0:
                    st.error(f"Error en separación: {result.stderr}")
                    st.stop()

                # Buscar el archivo de vocals generado por demucs
                vocals_candidates = list(Path(work_dir).rglob("vocals.wav"))
                if vocals_candidates:
                    melody_path = str(vocals_candidates[0])
                    st.write("✅ Melodía principal aislada")
                else:
                    st.warning("⚠️ No se encontró archivo de vocals, usando audio completo")
                    melody_path = audio_path

                status.update(label="✅ Melodía separada", state="complete")
        else:
            melody_path = audio_path

        # --- PASO 3: Convertir a MIDI ---
        if generar_midi:
            with st.status("🎼 Convirtiendo a MIDI (Basic Pitch)...", expanded=True) as status:
                st.write("Detectando notas musicales...")

                midi_dir = os.path.join(work_dir, "midi_out")
                os.makedirs(midi_dir, exist_ok=True)

                result = subprocess.run(
                    ["basic-pitch", midi_dir, melody_path],
                    capture_output=True, text=True, timeout=300
                )

                midi_candidates = list(Path(midi_dir).glob("*.mid")) + list(Path(midi_dir).glob("*.midi"))

                if midi_candidates:
                    midi_path = str(midi_candidates[0])
                    st.write("✅ MIDI generado con las notas de la melodía")
                else:
                    st.warning("⚠️ No se pudo generar MIDI. El audio WAV de la melodía igual está disponible.")

                status.update(label="✅ Conversión a MIDI completada", state="complete")

        # --- PASO 4: Mostrar resultados ---
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

                # Reproductor inline
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
        2. **Abrí el MIDI en [MuseScore](https://musescore.org)** (gratis) → Te muestra las notas exactas en partitura
        3. **O importá el MIDI en GarageBand / Guitar Pro** → Ves la tablatura directamente
        4. **Practicá nota por nota** usando el MIDI como guía de tempo y altura
        """)

    except subprocess.TimeoutExpired:
        st.error("⏱️ La operación tardó demasiado. Intentá con una canción más corta (menos de 5 min).")
    except Exception as e:
        st.error(f"❌ Error: {str(e)}")
        st.info("Asegurate de que la URL sea pública y que el video esté disponible en tu región.")
    finally:
        if work_dir and os.path.exists(work_dir):
            shutil.rmtree(work_dir, ignore_errors=True)

st.divider()
st.markdown("""
<p style="color:#555; font-size:0.8rem; text-align:center;">
Powered by <b>yt-dlp</b> · <b>Demucs</b> (Meta AI) · <b>Basic Pitch</b> (Spotify) | 
Solo para uso personal y educativo
</p>
""", unsafe_allow_html=True)
