import math
import config
import pydirectinput

# Desativar a pausa e fail-safe do pydirectinput para melhorar a performance
pydirectinput.PAUSE = 0
pydirectinput.FAILSAFE = False

import ctypes

_last_was_in_deadzone = False

def update_aim(rx, ry):
    """
    Recebe os valores do Analógico Direito (rx, ry) normalizados entre -1.0 e 1.0.
    Move o mouse proporcionalmente dentro do círculo invisível.
    Se o analógico for solto, o mouse retorna ao centro.
    """
    global _last_was_in_deadzone
    
    center_x = config.SCREEN_WIDTH // 2
    center_y = config.SCREEN_HEIGHT // 2

    # Calcula a magnitude do vetor para aplicar a deadzone
    magnitude = math.sqrt(rx**2 + ry**2)
    
    if magnitude < config.DEADZONE:
        if not _last_was_in_deadzone:
            # Retorna o mouse para o centro APENAS quando acaba de soltar
            # Assim o usuário pode usar o mouse de verdade depois se quiser
            ctypes.windll.user32.SetCursorPos(center_x, center_y)
            _last_was_in_deadzone = True
        return
    
    _last_was_in_deadzone = False

    # Se o analógico for empurrado além do limite unitário (ex: em diagonais), normaliza
    if magnitude > 1.0:
        rx /= magnitude
        ry /= magnitude

    # Calcula a posição diretamente proporcional à inclinação do analógico
    target_x = center_x + int(rx * config.AIM_RADIUS)
    target_y = center_y + int(ry * config.AIM_RADIUS)
    
    # Limita as coordenadas para não sair da tela (precaução)
    target_x = max(0, min(config.SCREEN_WIDTH - 1, target_x))
    target_y = max(0, min(config.SCREEN_HEIGHT - 1, target_y))
    
    # Move o cursor usando ctypes (ignora DPI scaling e bugs do pydirectinput)
    ctypes.windll.user32.SetCursorPos(target_x, target_y)


def simulate_right_click(down=True):
    """
    Simula o clique ou soltura do botão direito do mouse.
    """
    if down:
        pydirectinput.mouseDown(button='right')
    else:
        pydirectinput.mouseUp(button='right')


def simulate_left_click(down=True):
    """
    Simula o clique ou soltura do botão esquerdo do mouse.
    """
    if down:
        pydirectinput.mouseDown(button='left')
    else:
        pydirectinput.mouseUp(button='left')
