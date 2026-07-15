import config
import pydirectinput

# Estado atual das teclas para não mandar múltiplos keydowns desnecessários
current_keys_down = {
    'w': False,
    'a': False,
    's': False,
    'd': False
}

def update_wasd(lx, ly):
    """
    Recebe os eixos do analógico esquerdo (lx, ly) e simula W, A, S, D.
    """
    # Determinar quais direções estão ativas além da deadzone
    up = ly < -config.DEADZONE
    down = ly > config.DEADZONE
    left = lx < -config.DEADZONE
    right = lx > config.DEADZONE

    # Mapeamento do estado desejado para cada tecla
    desired_keys = {
        'w': up,
        's': down,
        'a': left,
        'd': right
    }

    # Aplica as mudanças no pydirectinput
    for key, should_be_down in desired_keys.items():
        if should_be_down and not current_keys_down[key]:
            pydirectinput.keyDown(key)
            current_keys_down[key] = True
        elif not should_be_down and current_keys_down[key]:
            pydirectinput.keyUp(key)
            current_keys_down[key] = False

def release_all_wasd():
    """Garante que todas as teclas de movimento sejam soltas"""
    for key, is_down in current_keys_down.items():
        if is_down:
            pydirectinput.keyUp(key)
            current_keys_down[key] = False
