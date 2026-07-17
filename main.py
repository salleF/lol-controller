import time
import threading
import pydirectinput
from inputs import get_gamepad
import config
import aim_math
import wasd_logic


def normalize_axis(value):
    """
    Normaliza o valor do analógico do XInput (-32768 a 32767)
    para o formato (-1.0 a 1.0)
    """
    return value / 32768.0


def main(stop_event=None):
    """
    Loop principal do controle.
    Usa config.CONTROLLER_LAYOUT para mapear os inputs do controle real.
    """
    print("O script está rodando usando 'inputs'. Pressione Ctrl+C no terminal para parar.")

    if stop_event is None:
        stop_event = threading.Event()

    # Recarregar configuração antes de iniciar
    config.load_config()

    layout = config.CONTROLLER_LAYOUT

    # --- Construir mapa dinâmico de botões: event_code → nome_interno ---
    inputs_map = {}
    for btn_name in ["SQUARE", "TRIANGLE", "CIRCLE", "CROSS", "L1", "R1", "L3", "R3", "START", "SELECT"]:
        event_code = layout.get(btn_name, "")
        if event_code:
            inputs_map[event_code] = btn_name

    # --- Códigos dos eixos e triggers ---
    l2_code = layout.get("L2", "ABS_Z")
    r2_code = layout.get("R2", "ABS_RZ")

    dpad_y_code = layout.get("DPAD_Y_CODE", "ABS_HAT0Y")
    dpad_x_code = layout.get("DPAD_X_CODE", "ABS_HAT0X")
    dpad_up_val = layout.get("DPAD_UP_VAL", -1)
    dpad_down_val = layout.get("DPAD_DOWN_VAL", 1)
    dpad_left_val = layout.get("DPAD_LEFT_VAL", -1)
    dpad_right_val = layout.get("DPAD_RIGHT_VAL", 1)

    axis_lx = layout.get("AXIS_LX", "ABS_X")
    axis_ly = layout.get("AXIS_LY", "ABS_Y")
    axis_rx = layout.get("AXIS_RX", "ABS_RX")
    axis_ry = layout.get("AXIS_RY", "ABS_RY")
    
    invert_lx = layout.get("INVERT_LX", False)
    invert_ly = layout.get("INVERT_LY", True)
    invert_rx = layout.get("INVERT_RX", False)
    invert_ry = layout.get("INVERT_RY", True)

    # --- Estado compartilhado ---
    lx, ly = 0.0, 0.0
    rx, ry = 0.0, 0.0
    keys_pressed = set()
    keyboard_keys_down = {}

    def _handle_action(btn_name, is_pressed):
        """Executa a ação mapeada para o botão do controle, seja ela mouse ou teclado."""
        action = config.MAPPING.get(btn_name, "")
        if not action or action == "—":
            return

        if action == "Ctrl":
            if is_pressed:
                pydirectinput.keyDown('ctrl')
            else:
                pydirectinput.keyUp('ctrl')
        elif action == "R-Click":
            aim_math.simulate_right_click(is_pressed)
        elif action == "L-Click":
            aim_math.simulate_left_click(is_pressed)
        else:
            # Ação de tecla comum (q, e, r, 1, 2, 3, 4, p, b, f, etc.)
            if is_pressed:
                if not keyboard_keys_down.get(action, False):
                    pydirectinput.keyDown(action)
                    keyboard_keys_down[action] = True
                    keys_pressed.add(btn_name)
            else:
                if keyboard_keys_down.get(action, False):
                    pydirectinput.keyUp(action)
                    keyboard_keys_down[action] = False
                    if btn_name in keys_pressed:
                        keys_pressed.remove(btn_name)

    def reader_loop():
        nonlocal lx, ly, rx, ry
        trigger_states = {
            "L2": False,
            "R2": False
        }
        
        while not stop_event.is_set():
            try:
                events = get_gamepad()
                for event in events:
                    if event.ev_type == 'Sync':
                        continue

                    code = event.code
                    state = event.state

                    # --- ANALÓGICO ESQUERDO ---
                    if code == axis_lx:
                        v = normalize_axis(state)
                        lx = -v if invert_lx else v
                    elif code == axis_ly:
                        v = normalize_axis(state)
                        ly = -v if invert_ly else v

                    # --- ANALÓGICO DIREITO ---
                    elif code == axis_rx:
                        v = normalize_axis(state)
                        rx = -v if invert_rx else v
                    elif code == axis_ry:
                        v = normalize_axis(state)
                        ry = -v if invert_ry else v

                    # --- GATILHOS (L2 / R2) ---
                    elif code == l2_code:
                        pressed = state > 128 if 0 <= state <= 255 else abs(state) > 16000
                        if pressed != trigger_states["L2"]:
                            trigger_states["L2"] = pressed
                            _handle_action("L2", pressed)

                    elif code == r2_code:
                        pressed = state > 128 if 0 <= state <= 255 else abs(state) > 16000
                        if pressed != trigger_states["R2"]:
                            trigger_states["R2"] = pressed
                            _handle_action("R2", pressed)

                    # --- BOTÕES DE FACE E OMBROS ---
                    elif event.ev_type == 'Key' and code in inputs_map:
                        btn_name = inputs_map[code]
                        is_pressed = state == 1
                        _handle_action(btn_name, is_pressed)

                    # --- D-PAD (Setinhas) ---
                    elif code == dpad_y_code:
                        if state == dpad_up_val:
                            _handle_action("DPAD_UP", True)
                        elif state == dpad_down_val:
                            _handle_action("DPAD_DOWN", True)
                        else:
                            _handle_action("DPAD_UP", False)
                            _handle_action("DPAD_DOWN", False)

                    elif code == dpad_x_code:
                        if state == dpad_right_val:
                            _handle_action("DPAD_RIGHT", True)
                        elif state == dpad_left_val:
                            _handle_action("DPAD_LEFT", True)
                        else:
                            _handle_action("DPAD_RIGHT", False)
                            _handle_action("DPAD_LEFT", False)

            except Exception:
                # Caso de desconexão ou encerramento
                break

    def cleanup():
        """Garante que todas as teclas e cliques sejam soltos ao parar."""
        wasd_logic.release_all_wasd()
        pydirectinput.keyUp('ctrl')
        aim_math.simulate_right_click(False)
        aim_math.simulate_left_click(False)
        
        # Solta todas as teclas que ficaram marcadas como pressionadas
        for action, is_down in keyboard_keys_down.items():
            if is_down:
                pydirectinput.keyUp(action)
        keyboard_keys_down.clear()
        keys_pressed.clear()

    # Iniciar thread assíncrona para ler eventos do controle
    t_reader = threading.Thread(target=reader_loop, daemon=True)
    t_reader.start()

    try:
        # Loop principal síncrono com taxa de atualização constante de 100Hz (10ms)
        while not stop_event.is_set():
            wasd_logic.update_wasd(lx, ly)
            aim_math.update_aim(rx, ry)
            time.sleep(0.01)

    except KeyboardInterrupt:
        print("\nSaindo... Soltando todas as teclas.")
    finally:
        cleanup()
        print("Script parado. Todas as teclas foram soltas.")


if __name__ == "__main__":
    main()
