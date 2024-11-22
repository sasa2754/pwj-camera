from flask import Flask, Response
import cv2
import subprocess
import mysql.connector
from collections import deque
import time

# Inicializa a fila de entregas do robô
delivery_queue = deque()
is_busy = False

# Inicializa a webcam
cap = cv2.VideoCapture(0)

# Função para conectar ao banco de dados mysql
def create_connection():
    try:
        connection = mysql.connector.connect(
            host='paparella.com.br',
            user='paparell_deliveries',
            password='Sabrina123@sa',
            database='paparell_deliveries'
        )
        if connection.is_connected():
            print("Conexão com o mysql foi bem-sucedida!")
        return connection
    except mysql.connector.Error as e:
        print(f'Erro ao conectar no mysql: {e}')
        return None

# Função para pegar os dados do banco  
def get_data_from_mysql():
    connection = create_connection()
    if connection:
        cursor = connection.cursor()
        cursor.execute("SELECT sector, dateInit, dateEnd FROM deliveries ORDER BY dateInit")
        records = cursor.fetchall()

        for row in records:
            sector, dateInit, dateEnd = row
            delivery_queue.append({'sector': sector, 'dateInit': dateInit, 'dateEnd': dateEnd})
            print(f"Setor: {sector}, Data Inicial: {dateInit}, Data Final: {dateEnd}")

        cursor.close()
        connection.close()

# Função para processar entrega
def process_delivery(delivery):
    global is_busy

    if is_busy:
        print("Carrinho está ocupado. A entrega será processada depois!")
        return

    is_busy = True
    sector = delivery['sector']
    print(f'Processando entrega para o setor {sector}')

    while True:  # Loop para seguir a linha até o setor
        success, frame = cap.read()
        if not success:
            print("Erro ao capturar frame da câmera.")
            break

        # Simulação de detecção de erro com base no setor
        if sector == "ETS":
            print("ETS - Linha amarela")
            result = detec_line_yellow(frame)
        elif sector == "SAP":
            print("SAP - Linha azul")
            result = detec_line_blue(frame)
        else:
            print(f"Setor desconhecido: {sector}. Parando...")
            break

        if result and isinstance(result, tuple) and len(result) == 2:
            frame, error = result
            subprocess.Popen(["python3", "motor.py", str(error)])  # Chama o script do motor
        else:
            print("Erro indefinido. Continuando a busca...")

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    is_busy = False

# Flask streaming para a webcam
def generate_frames():
    while True:
        success, frame = cap.read()
        if not success:
            break
        else:
            ret, buffer = cv2.imencode('.jpg', frame)
            frame = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n\r\n')

# Rota para exibir o vídeo
app = Flask(__name__)

@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == '__main__':
    get_data_from_mysql()
    app.run(host="0.0.0.0", port=5000, debug=True)
