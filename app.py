import streamlit as st
import numpy as np
from tensorflow.keras.models import load_model
from PIL import Image
import paho.mqtt.client as mqtt
import json

# =====================================================
# CONFIGURACIÓN STREAMLIT
# =====================================================

st.set_page_config(page_title="Cofre Inteligente", layout="centered")

st.title("🔐 Sistema de Seguridad IoT")

estado_texto = st.empty()

# =====================================================
# IMÁGENES DEL COFRE
# =====================================================

COFRE_CERRADO = "cofre_cerrado.png"
COFRE_ABIERTO = "cofre_abierto.png"

imagen_estado = st.image(COFRE_CERRADO)

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
# CARGAR MODELO TEACHABLE MACHINE
# =====================================================

modelo = load_model("keras_model.h5", compile=False)

with open("labels.txt", "r") as f:
    class_names = f.read().splitlines()

# =====================================================
# VARIABLES
# =====================================================

if "autorizado" not in st.session_state:
    st.session_state.autorizado = False

# =====================================================
# FUNCIÓN MQTT
# =====================================================

def publicar(topic, mensaje):

    client.publish(topic, json.dumps(mensaje))

# =====================================================
# INTERFAZ
# =====================================================

st.subheader("📷 Reconocimiento Facial")

foto = st.camera_input("Tomar foto")

# =====================================================
# SI HAY FOTO
# =====================================================

if foto is not None:

    image = Image.open(foto).convert("RGB")

    image = image.resize((224, 224))

    image_array = np.asarray(image)

    normalized_image_array = (image_array.astype(np.float32) / 127.5) - 1

    data = np.ndarray(shape=(1, 224, 224, 3), dtype=np.float32)

    data[0] = normalized_image_array

    # =====================================================
    # PREDICCIÓN
    # =====================================================

    prediction = modelo.predict(data, verbose=0)

    index = np.argmax(prediction)

    class_name = class_names[index]

    confidence_score = prediction[0][index]

    st.write(f"Clase detectada: {class_name}")

    st.write(f"Confianza: {confidence_score:.2f}")

    # =====================================================
    # DUEÑOS AUTORIZADOS
    # =====================================================

    if (
        ("Dueño 1" in class_name or "Dueño 2" in class_name)
        and confidence_score > 0.85
    ):

        st.success("✅ Dueño reconocido")

        publicar(
            TOPIC_ESTADO,
            {"estado": "DUENO"}
        )

        st.session_state.autorizado = True

    else:

        st.error("🚨 Intruso detectado")

        publicar(
            TOPIC_ESTADO,
            {"estado": "INTRUSO"}
        )

        st.session_state.autorizado = False

# =====================================================
# CONTROL DEL COFRE
# =====================================================

st.markdown("---")

st.subheader("🎤 Comandos del Cofre")

# =====================================================
# SOLO SI ESTÁ AUTORIZADO
# =====================================================

if st.session_state.autorizado:

    comando = st.text_input(
        "Comando",
        placeholder="Escribe: Abrete o Cierrate"
    )

    # =====================================================
    # ABRIR
    # =====================================================

    if comando.lower() == "abrete":

        publicar(
            TOPIC_VOZ,
            {"cofre": "ABRIR"}
        )

        imagen_estado.image(COFRE_ABIERTO)

        estado_texto.success("📦 Cofre abierto")

    # =====================================================
    # CERRAR
    # =====================================================

    elif comando.lower() == "cierrate":

        publicar(
            TOPIC_VOZ,
            {"cofre": "CERRAR"}
        )

        imagen_estado.image(COFRE_CERRADO)

        estado_texto.warning("📦 Cofre cerrado")

else:

    st.warning("⚠️ Debe reconocerse un dueño primero")
