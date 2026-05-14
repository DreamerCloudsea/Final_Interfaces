import streamlit as st
import cv2
import numpy as np
from keras.models import load_model
import paho.mqtt.client as mqtt
import json
import time
from PIL import Image


# =====================================================
# CONFIGURACIÓN STREAMLIT
# =====================================================

st.set_page_config(page_title="Cofre Inteligente", layout="centered")

st.title("🔐 Sistema de Seguridad IoT")

estado_texto = st.empty()
imagen_estado = st.empty()
camara_frame = st.empty()

# =====================================================
# IMÁGENES DEL COFRE
# =====================================================

COFRE_CERRADO = "cofre_cerrado.png"
COFRE_ABIERTO = "cofre_abierto.png"

imagen_actual = COFRE_CERRADO

# =====================================================
# MQTT
# =====================================================

BROKER = "broker.mqttdashboard.com"
PUERTO = 1883

TOPIC_MOVIMIENTO = "cofre/movimiento"
TOPIC_ESTADO = "cofre/estado"
TOPIC_VOZ = "cofre/voz"

# =====================================================
# CARGAR MODELO TEACHABLE MACHINE
# =====================================================

modelo = load_model("keras_model.h5", compile=False)

with open("labels.txt", "r") as f:
    class_names = f.read().splitlines()

# =====================================================
# MQTT CLIENT
# =====================================================

client = mqtt.Client()

# =====================================================
# VARIABLES
# =====================================================

esperando_voz = False
cofre_abierto = False

# =====================================================
# FUNCIÓN PUBLICAR MQTT
# =====================================================

def publicar(topic, mensaje):

    client.publish(topic, json.dumps(mensaje))

# =====================================================
# RECONOCIMIENTO FACIAL
# =====================================================

def reconocer_persona():

    global esperando_voz

    estado_texto.info("📷 Analizando rostro...")

    cap = cv2.VideoCapture(0)

    tiempo_inicio = time.time()

    resultado = "INTRUSO"

    while time.time() - tiempo_inicio < 5:

        ret, frame = cap.read()

        if not ret:
            continue

        img = cv2.resize(frame, (224, 224))

        image_array = np.asarray(img)

        normalized_image_array = (image_array.astype(np.float32) / 127.5) - 1

        data = np.ndarray(shape=(1, 224, 224, 3), dtype=np.float32)

        data[0] = normalized_image_array

        prediction = modelo.predict(data, verbose=0)

        index = np.argmax(prediction)

        class_name = class_names[index]

        confidence_score = prediction[0][index]

        # Mostrar cámara
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        camara_frame.image(frame_rgb)

        estado_texto.write(
            f"Detectado: {class_name} | Confianza: {confidence_score:.2f}"
        )

        # =====================================================
        # DUEÑOS AUTORIZADOS
        # =====================================================

        if (
            ("Dueño 1" in class_name or "Dueño 2" in class_name)
            and confidence_score > 0.85
        ):

            resultado = "DUENO"
            break

    cap.release()

    # =====================================================
    # RESULTADO FINAL
    # =====================================================

    if resultado == "DUENO":

        publicar(
            TOPIC_ESTADO,
            {"estado": "DUENO"}
        )

        estado_texto.success("✅ Dueño reconocido")

        esperando_voz = True

    else:

        publicar(
            TOPIC_ESTADO,
            {"estado": "INTRUSO"}
        )

        estado_texto.error("🚨 Intruso detectado")

        esperando_voz = False

# =====================================================
# RECONOCIMIENTO DE VOZ
# =====================================================

def escuchar_comando():

    global cofre_abierto

    comando = st.text_input(
        "🎤 Comando de voz",
        placeholder="Escribe: Abrete o Cierrate"
    )

    if comando:

        comando = comando.lower()

        # =====================================================
        # ABRIR
        # =====================================================

        if "abrete" in comando:

            publicar(
                TOPIC_VOZ,
                {"cofre": "ABRIR"}
            )

            estado_texto.success("📦 Cofre abierto")

            imagen_estado.image(COFRE_ABIERTO)

            cofre_abierto = True

        # =====================================================
        # CERRAR
        # =====================================================

        elif "cierrate" in comando:

            publicar(
                TOPIC_VOZ,
                {"cofre": "CERRAR"}
            )

            estado_texto.warning("📦 Cofre cerrado")

            imagen_estado.image(COFRE_CERRADO)

            cofre_abierto = False

# =====================================================
# CALLBACK MQTT
# =====================================================

def on_message(client, userdata, msg):

    tema = msg.topic

    mensaje = json.loads(msg.payload.decode())

    # =====================================================
    # DETECCIÓN MOVIMIENTO
    # =====================================================

    if tema == TOPIC_MOVIMIENTO:

        movimiento = mensaje["movimiento"]

        if movimiento == "SI":

            estado_texto.warning("👀 Movimiento detectado")

            reconocer_persona()

# =====================================================
# MQTT SETUP
# =====================================================

client.on_message = on_message

client.connect(BROKER, PUERTO, 60)

client.subscribe(TOPIC_MOVIMIENTO)

client.loop_start()

# =====================================================
# INTERFAZ INICIAL
# =====================================================

imagen_estado.image(COFRE_CERRADO)

st.markdown("---")

st.subheader("Estado del sistema")

# =====================================================
# VOZ SOLO SI ESTÁ AUTORIZADO
# =====================================================

if esperando_voz:

    escuchar_comando()

# =====================================================
# LOOP VISUAL
# =====================================================

while True:
    time.sleep(1)
