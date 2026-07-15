import math
import config
import pydirectinput

# Desativar a pausa e fail-safe do pydirectinput para melhorar a performance
pydirectinput.PAUSE = 0
pydirectinput.FAILSAFE = False

def update_aim(rx, ry):
    """
    Recebe os valores do Analógico Direito (rx, ry) normalizados entre -1.0 e 1.0.
    Move o mouse para a borda do círculo invisível baseado no ângulo do analógico.
    """
    # Calcula a magnitude do vetor para aplicar a deadzone
    magnitude = math.sqrt(rx**2 + ry**2)
    
    if magnitude < config.DEADZONE:
        # Se o analógico estiver solto (ou muito pouco mexido), não fazemos nada
        return
    
    # Calcula o ângulo em radianos (math.atan2(y, x))
    # Nota: Em joysticks, Y para cima costuma ser negativo, dependendo da biblioteca.
    # No Pygame, Y para cima é negativo, para baixo é positivo.
    # Na tela do PC, Y=0 é o topo, Y máximo é a base. Portanto os eixos costumam bater.
    angle = math.atan2(ry, rx)
    
    # Calcula as coordenadas X e Y no círculo a partir do centro da tela
    center_x = config.SCREEN_WIDTH // 2
    center_y = config.SCREEN_HEIGHT // 2
    
    target_x = center_x + int(math.cos(angle) * config.AIM_RADIUS)
    target_y = center_y + int(math.sin(angle) * config.AIM_RADIUS)
    
    # Limita as coordenadas para não sair da tela (precaução)
    target_x = max(0, min(config.SCREEN_WIDTH - 1, target_x))
    target_y = max(0, min(config.SCREEN_HEIGHT - 1, target_y))
    
    # Move o cursor usando o pydirectinput (simula movimentação nativa do mouse)
    pydirectinput.moveTo(target_x, target_y)

def simulate_right_click(down=True):
    """
    Simula o clique ou soltura do botão direito do mouse.
    """
    if down:
        pydirectinput.mouseDown(button='right')
    else:
        pydirectinput.mouseUp(button='right')
