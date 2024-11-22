import sys
from gpiozero import Motor
from time import sleep

# Inicializa os motores
motor_A = Motor(forward=17, backward=18)
motor_B = Motor(forward=21, backward=22)

def move_motors(error):
    error = int(error)
    if error > 0:
        print("Erro positivo: corrigindo para a direita.")
        motor_A.forward()
        motor_B.backward()
    elif error < 0:
        print("Erro negativo: corrigindo para a esquerda.")
        motor_A.backward()
        motor_B.forward()
    else:
        print("Erro zero: andando para frente.")
        motor_A.forward()
        motor_B.forward()
    motor_A.stop()
    motor_B.stop()

if __name__ == "__main__":
    if len(sys.argv) > 1:
        erro = sys.argv[1]
        move_motors(erro)
    else:
        print("Erro não informado!")
