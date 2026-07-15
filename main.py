import time
import pydirectinput
from inputs import get_gamepad
import config
import aim_math
import wasd_logic

# Mapeamento do nome interno do inputs para o nosso config.py
# (Isso assume layout XInput padrão que o Windows aplica à maioria dos controles via DS4Windows/USB)
INPUTS_MAP = {
    "BTN_WEST": "SQUARE",      # X / Quadrado
    "BTN_NORTH": "TRIANGLE",   # Y / Triângulo
    "BTN_EAST": "CIRCLE",      # B / Bolinha
    "BTN_SOUTH": "CROSS",      # A / Cruz
    "BTN_TL": "L1",            # LB / L1
    "BTN_TR": "R1",            # RB / R1
}

def normalize_axis(value):
    """
    Normaliza o valor do analógico do XInput (-32768 a 32767)
    para o formato que já fizemos antes (-1.0 a 1.0)
    """
    return value / 32768.0

def main():
    print("O script está rodando usando 'inputs'. Pressione Ctrl+C no terminal para parar.")

    keys_pressed = set()
    l2_pressed = False
    r2_pressed = False
    
    # Guarda o estado atual dos analógicos
    lx, ly = 0.0, 0.0
    rx, ry = 0.0, 0.0

    try:
        while True:
            # get_gamepad() pausa o código até que um botão seja apertado ou analógico movido.
            # Isso é extremamente eficiente em CPU.
            events = get_gamepad()
            
            for event in events:
                if event.ev_type == 'Sync':
                    continue

                # --- PROCESSAMENTO DOS ANALÓGICOS ---
                # Analógico Esquerdo
                if event.code == 'ABS_X':
                    lx = normalize_axis(event.state)
                elif event.code == 'ABS_Y':
                    ly = normalize_axis(event.state)
                    # Nota: O eixo Y normalmente é invertido no Xinput (cima é positivo)
                    # O wasd_logic original assumiu ly < 0 para UP (padrão Pygame). 
                    # Então invertemos para manter compatibilidade.
                    ly = -ly 
                
                # Analógico Direito
                elif event.code == 'ABS_RX':
                    rx = normalize_axis(event.state)
                elif event.code == 'ABS_RY':
                    ry = normalize_axis(event.state)
                    ry = -ry # Inverter Y para manter compatibilidade

                # --- GATILHOS (L2 / R2) ---
                # No Windows Xinput, os gatilhos vão de 0 a 255.
                elif event.code == 'ABS_Z': # L2
                    current_l2 = event.state > 128
                    if current_l2 != l2_pressed:
                        if current_l2:
                            pydirectinput.keyDown('ctrl')
                        else:
                            pydirectinput.keyUp('ctrl')
                        l2_pressed = current_l2
                
                elif event.code == 'ABS_RZ': # R2
                    current_r2 = event.state > 128
                    if current_r2 != r2_pressed:
                        aim_math.simulate_right_click(current_r2)
                        r2_pressed = current_r2

                # --- BOTÕES DE FACE E OMBROS ---
                elif event.ev_type == 'Key':
                    if event.code in INPUTS_MAP:
                        abstract_name = INPUTS_MAP[event.code]
                        if abstract_name in config.MAPPING:
                            key_to_press = config.MAPPING[abstract_name]
                            if event.state == 1 and abstract_name not in keys_pressed:
                                pydirectinput.keyDown(key_to_press)
                                keys_pressed.add(abstract_name)
                            elif event.state == 0 and abstract_name in keys_pressed:
                                pydirectinput.keyUp(key_to_press)
                                keys_pressed.remove(abstract_name)
                
                # --- D-PAD (Setinhas) ---
                elif event.code == 'ABS_HAT0Y':
                    if event.state == -1: # Pra Cima
                        pydirectinput.keyDown(config.MAPPING["DPAD_UP"])
                        keys_pressed.add("DPAD_UP")
                    elif event.state == 1: # Pra Baixo
                        pydirectinput.keyDown(config.MAPPING["DPAD_DOWN"])
                        keys_pressed.add("DPAD_DOWN")
                    else: # Soltou o Y
                        if "DPAD_UP" in keys_pressed:
                            pydirectinput.keyUp(config.MAPPING["DPAD_UP"])
                            keys_pressed.remove("DPAD_UP")
                        if "DPAD_DOWN" in keys_pressed:
                            pydirectinput.keyUp(config.MAPPING["DPAD_DOWN"])
                            keys_pressed.remove("DPAD_DOWN")
                
                elif event.code == 'ABS_HAT0X':
                    if event.state == 1: # Direita
                        pydirectinput.keyDown(config.MAPPING["DPAD_RIGHT"])
                        keys_pressed.add("DPAD_RIGHT")
                    elif event.state == -1: # Esquerda
                        pydirectinput.keyDown(config.MAPPING["DPAD_LEFT"])
                        keys_pressed.add("DPAD_LEFT")
                    else: # Soltou o X
                        if "DPAD_RIGHT" in keys_pressed:
                            pydirectinput.keyUp(config.MAPPING["DPAD_RIGHT"])
                            keys_pressed.remove("DPAD_RIGHT")
                        if "DPAD_LEFT" in keys_pressed:
                            pydirectinput.keyUp(config.MAPPING["DPAD_LEFT"])
                            keys_pressed.remove("DPAD_LEFT")

            # Após processar todos os eventos do pacote (até o Sync), 
            # atualiza o WASD e a Mira contínua usando os valores estocados.
            wasd_logic.update_wasd(lx, ly)
            aim_math.update_aim(rx, ry)
            
    except KeyboardInterrupt:
        print("\nSaindo... Soltando todas as teclas.")
        wasd_logic.release_all_wasd()
        if l2_pressed:
            pydirectinput.keyUp('ctrl')
        aim_math.simulate_right_click(False)
        for abstract_name in list(keys_pressed):
            if abstract_name in config.MAPPING:
                pydirectinput.keyUp(config.MAPPING[abstract_name])

if __name__ == "__main__":
    main()
