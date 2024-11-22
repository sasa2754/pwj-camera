from flask import Flask, Response
import cv2
import numpy as np
import mysql.connector
from collections import deque
import time
import threading
import socket

# import subprocess

# Inicializa a fila de entregas do robô
delivery_queue = deque()
is_busy = False

ESP32_IP = '192.168.230.247' # Endereço IP da esp32
ESP32_PORT = 80 # Mesma porta configurada na ESP32

# Cria um socket TPC (socket é um ponto de comunicação entre dois dispositivos de uma rede, ele permite a troca de dados entre dispositivos usando protocolos de rede, como o TCP, que é um protocolo que garante que os dados sejam entregues na ordem correta e sem falhas)
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

def ensure_connection():
    try:
        s.connect((ESP32_IP, ESP32_PORT))
    except socket.error as e:
        print(f'Erro de conexão: {e}')
        time.sleep(5)  # Espera um tempo antes de tentar novamente
        ensure_connection()


# Função para enviar o erro para a ESP32
def send_error(error):
    try:
        s.sendall(f'{error}\n'.encode()) # O erro é enviado como uma string, para facilitar a leitura na ESP32, pois podemos ler cada linha de dados com o parâmetro final do \n e só converter depois com um .toInt
    except Exception as e:
        print(f'Erro ao enviar dados para a ESP32: {e}')



# Inicializa a webcam
cap = cv2.VideoCapture(1)  # Verifique se o índice da câmera está correto (0 ou 1)

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
    print("Buscando entregas do banco de dados...")
    connection = create_connection()

    if connection:
        cursor = connection.cursor()
        cursor.execute("SELECT sector, dateInit, dateEnd FROM deliveries ORDER BY dateInit")
        records = cursor.fetchall()

        for row in records:
            sector, dateInit, dateEnd = row
            delivery_queue.append({'sector': sector, 'dateInit': dateInit, 'dateEnd': dateEnd})
            print(f"Entrega encontrada - Setor: {sector}, Data Inicial: {dateInit}, Data Final: {dateEnd}")

        cursor.close()
        connection.close()
    else:
        print("Não foi possível conectar ao banco de dados.")

# Função de ver se o robô está ocupado ou livre e realizar a entrega com base nisso
def process_delivery(delivery):
    global is_busy

    if is_busy:
        print("Carrinho está ocupado. A entrega será processada depois!")
        return

    is_busy = True
    sector = delivery['sector']
    print(f'Iniciando a entrega para o setor {sector}')

    while True:  # Loop para seguir a linha até o setor
        success, frame = cap.read()
        if not success:
            print("Erro ao capturar frame da câmera. Continuando a busca...")
            continue  # Continua tentando capturar o frame

        if sector == "ETS":
            print("ETS - Linha amarela")
            result = detec_line_yellow(frame)
        elif sector == "SAP":
            print("SAP - Linha azul")
            result = detec_line_blue(frame)
        elif sector == "ICO":
            print("ICO - Linha vermelha")
            result = detec_line_red(frame)
        else:
            print(f"Setor desconhecido: {sector}. Continuando a busca...")
            continue  # Continua a busca sem interromper o processo

        if result is None:
            print(f"Não foi possível detectar a linha para o setor {sector}. Continuando a busca...")
            continue  # Continua buscando sem interromper o processo

        # Garantir que result tenha dois valores a serem desempacotados
        if isinstance(result, tuple) and len(result) == 2:
            frame, error = result
            send_error(error)
            # subprocess.Popen(["python3", "motor.py", str(error)])  # Chama o script do motor

        else:
            print(f"Erro no retorno da detecção da linha para o setor {sector}. Continuando a busca...")
            continue  # Se não for um retorno válido, continua buscando

        if detect_line_green(frame):
            print("Carrinho chegou ao destino, entrega concluída. Voltando para a base!")
            break

        # Exibe o frame com feedback visual (opcional)
        cv2.imshow('Robô', frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):  # Permite interromper o loop com 'q'
            print("Entrega interrompida pelo usuário.")
            break

    print(f"Entrega para o setor {sector} concluída. Processando próxima entrega...")

    # Processa a próxima entrega na fila, se houver
    if delivery_queue:
        next_delivery = delivery_queue.popleft()
        print("Próxima entrega na fila.")
        process_delivery(next_delivery)

# Função para detectar uma linha amarela
def detec_line_yellow(frame):
    print("Entrou na função da ETS")
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    lower_yellow = np.array([20, 100, 100])
    upper_yellow = np.array([30, 255, 255])

    mask = cv2.inRange(hsv, lower_yellow, upper_yellow)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    if contours:
        largest_contour = max(contours, key=cv2.contourArea)
        M = cv2.moments(largest_contour)

        if M["m00"] != 0:
            cx = int(M["m10"] / M["m00"])
            cy = int(M["m01"] / M["m00"])

            cv2.drawContours(frame, [largest_contour], -1, (0, 255, 0), 3)
            cv2.circle(frame, (cx, cy), 5, (255, 0, 0), -1)

            frame_center_x = frame.shape[1] // 2
            error = cx - frame_center_x
            return frame, error
        print("Chegou ao final da função ETS")
        return frame, None 

# Função para detectar uma linha azul
def detec_line_blue(frame):
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    lower_blue = np.array([100, 150, 0])
    upper_blue = np.array([140, 255, 255])

    mask = cv2.inRange(hsv, lower_blue, upper_blue)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    if contours:
        largest_contour = max(contours, key=cv2.contourArea)
        M = cv2.moments(largest_contour)

        if M["m00"] != 0:
            cx = int(M["m10"] / M["m00"])
            cy = int(M["m01"] / M["m00"])

            cv2.drawContours(frame, [largest_contour], -1, (0, 255, 0), 3)
            cv2.circle(frame, (cx, cy), 5, (255, 0, 0), -1)

            frame_center_x = frame.shape[1] // 2
            error = cx - frame_center_x
            return frame, error
        
        return frame, None

def detec_line_red(frame):
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    lower_red = np.array([0, 100, 100])
    upper_red = np.array([10, 255, 255])
    mask = cv2.inRange(hsv, lower_red, upper_red)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if contours:
        largest_contour = max(contours, key=cv2.contourArea)
        M = cv2.moments(largest_contour)

        if M["m00"] != 0:
            cx = int(M["m10"] / M["m00"])
            cy = int(M["m01"] / M["m00"])

            cv2.drawContours(frame, [largest_contour], -1, (0, 255, 0), 3)
            cv2.circle(frame, (cx, cy), 5, (255, 0, 0), -1)

            frame_center_x = frame.shape[1] // 2
            error = cx - frame_center_x
            return frame, error
        
        return frame, None

# Função para detectar a linha verde (destino de entrega)
def detect_line_green(frame):
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    lower_green = np.array([35, 50, 50])
    upper_green = np.array([85, 255, 255])

    mask = cv2.inRange(hsv, lower_green, upper_green)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    if contours:
        largest_contour = max(contours, key=cv2.contourArea)
        if cv2.contourArea(largest_contour) > 1000:
            return True
    return False

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

@app.route('/deliveries')
def deliveries():
    # Buscar e processar entregas
    get_data_from_mysql()

    if delivery_queue:
        delivery = delivery_queue.popleft()
        threading.Thread(target=process_delivery, args=(delivery,)).start()
        return "Entrega em andamento..."
    return "Nenhuma entrega pendente."

if __name__ == '__main__':
    deliveries()
    app.run(debug=True, host='0.0.0.0', port=5000)
