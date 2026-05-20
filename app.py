import os
import streamlit as st
import numpy as np
from PIL import Image
from keras.models import load_model
import paho.mqtt.client as mqtt
import json
import platform
import base64
from bokeh.models.widgets import Button
from bokeh.models import CustomJS
from streamlit_bokeh_events import streamlit_bokeh_events

# =====================================================
# CONFIG STREAMLIT
# =====================================================

st.set_page_config(page_title="Cofre Inteligente")
st.title("🔐 Cofre Inteligente con IA")
st.write("Python:", platform.python_version())

# =====================================================
# MQTT
# =====================================================

BROKER = "broker.mqttdashboard.com"
PUERTO = 1883
TOPIC_ESTADO = "cofre/estado"
TOPIC_VOZ = "cofre/voz"

client = mqtt.Client()
client.connect(BROKER, PUERTO, 60)
client.loop_start()

# =====================================================
# CARGAR MODELO
# =====================================================

model = load_model("keras_model.h5", compile=False)

with open("labels.txt", "r") as f:
    class_names = f.read().splitlines()

# =====================================================
# VARIABLES DE ESTADO
# =====================================================

if "autorizado" not in st.session_state:
    st.session_state.autorizado = False

if "cofre_abierto" not in st.session_state:
    st.session_state.cofre_abierto = False

# =====================================================
# FUNCIÓN MQTT
# =====================================================

def publicar(topic, mensaje):
    client.publish(topic, json.dumps(mensaje))

# =====================================================
# FUNCIÓN IMAGEN A BASE64
# =====================================================

def imagen_a_base64(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()

# =====================================================
# RECONOCIMIENTO FACIAL
# =====================================================

st.subheader("📷 Reconocimiento Facial")

img_file_buffer = st.camera_input("Tomar foto")

if img_file_buffer is not None:
    image = Image.open(img_file_buffer).convert("RGB")
    image = image.resize((224, 224))
    image_array = np.array(image)
    normalized_image_array = (image_array.astype(np.float32) / 127.0) - 1

    data = np.ndarray(shape=(1, 224, 224, 3), dtype=np.float32)
    data[0] = normalized_image_array

    prediction = model.predict(data)
    index = np.argmax(prediction)
    class_name = class_names[index]
    confidence_score = prediction[0][index]

    st.write(f"Clase detectada: {class_name}")
    st.write(f"Confianza: {confidence_score:.2f}")

    if (
        ("Dueño 1" in class_name or "Dueño 2" in class_name)
        and confidence_score > 0.85
    ):
        st.success("✅ Dueño reconocido")
        publicar(TOPIC_ESTADO, {"estado": "DUENO"})
        st.session_state.autorizado = True
    else:
        st.error("🚨 Intruso detectado")
        publicar(TOPIC_ESTADO, {"estado": "INTRUSO"})
        st.session_state.autorizado = False

# =====================================================
# CONTROL POR VOZ
# =====================================================

st.markdown("---")
st.subheader("🎤 Control por Voz del Cofre")

if st.session_state.autorizado:

    st.markdown("<p style='text-align:center;'>Presiona el botón y di <b>ábrete</b> o <b>ciérrate</b></p>", unsafe_allow_html=True)

    stt_button = Button(
        label="🎤 Iniciar Grabación",
        width=200,
        button_type="success"
    )

    stt_button.js_on_event("button_click", CustomJS(code="""
        var recognition = new webkitSpeechRecognition();
        recognition.continuous = false;
        recognition.interimResults = false;
        recognition.lang = 'es-ES';

        recognition.onresult = function(e) {
            var value = "";
            for (var i = e.resultIndex; i < e.results.length; ++i) {
                if (e.results[i].isFinal) {
                    value += e.results[i][0].transcript;
                }
            }
            if (value != "") {
                document.dispatchEvent(new CustomEvent("GET_TEXT", {detail: value}));
            }
        }
        recognition.start();
    """))

    result = streamlit_bokeh_events(
        stt_button,
        events="GET_TEXT",
        key="listen",
        refresh_on_update=False,
        override_height=75,
        debounce_time=0
    )

    # =====================================================
    # PROCESAR COMANDO DE VOZ
    # =====================================================

    if result and "GET_TEXT" in result:
        texto = result.get("GET_TEXT").strip().lower()

        st.markdown(
            f"<h4 style='text-align:center; color:#2c3e50;'>🗣️ Escuché: <i>{texto}</i></h4>",
            unsafe_allow_html=True
        )

        # Variantes de comando para mayor tolerancia
        comandos_abrir  = ["ábrete", "abrete", "abrir", "abre"]
        comandos_cerrar = ["ciérrate", "cierrate", "cerrar", "cierra"]

        if any(cmd in texto for cmd in comandos_abrir):
            publicar(TOPIC_VOZ, {"cofre": "ABRIR"})
            st.session_state.cofre_abierto = True
            st.success("📦 Cofre abierto")

        elif any(cmd in texto for cmd in comandos_cerrar):
            publicar(TOPIC_VOZ, {"cofre": "CERRAR"})
            st.session_state.cofre_abierto = False
            st.warning("📦 Cofre cerrado")

        else:
            st.error(f"❌ Comando no reconocido: '{texto}'")

else:
    st.warning("⚠️ Debe reconocerse un dueño primero")

# =====================================================
# ESTADO VISUAL DEL COFRE — HTML con opacidad
# =====================================================

st.markdown("---")
st.subheader("📦 Estado del Cofre")

b64_cerrado = imagen_a_base64("cofre_cerrado.jpg")
b64_abierto = imagen_a_base64("cofre_abierto.jpg")

op_cerrado = 0 if st.session_state.cofre_abierto else 1
op_abierto = 1 if st.session_state.cofre_abierto else 0

st.components.v1.html(f"""
    <div style="position: relative; width: 300px; height: 300px;">

        <img
            src="data:image/png;base64,{b64_cerrado}"
            style="
                position: absolute;
                top: 0; left: 0;
                width: 300px;
                opacity: {op_cerrado};
                transition: opacity 0.5s ease;
            "
        />

        <img
            src="data:image/png;base64,{b64_abierto}"
            style="
                position: absolute;
                top: 0; left: 0;
                width: 300px;
                opacity: {op_abierto};
                transition: opacity 0.5s ease;
            "
        />

    </div>
""", height=320)

if st.session_state.cofre_abierto:
    st.success("📦 Cofre abierto")
else:
    st.warning("📦 Cofre cerrado")
