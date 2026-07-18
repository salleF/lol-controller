import ctypes
import time
import threading
from collections import defaultdict

import pydirectinput
from inputs import get_gamepad, UnpluggedError
import config
import aim_math
import wasd_logic


def _set_dpi_awareness():
    """
    Declara o processo como DPI-aware para que ctypes.windll.user32.SetCursorPos
    (usado em aim_math.py) e as coordenadas de tela calculadas a partir de
    config.SCREEN_WIDTH/SCREEN_HEIGHT correspondam aos pixels físicos reais,
    mesmo com escala de exibição do Windows configurada (125%, 150%, etc.).
    Sem isso, o cursor pode ser posicionado no lugar errado da tela.
    """
    try:
        # PROCESS_PER_MONITOR_DPI_AWARE
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except (AttributeError, OSError):
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except (AttributeError, OSError):
            pass


def _warn_if_not_admin():
    """
    Avisa no console se o processo não está elevado. Se o jogo/anti-cheat
    rodar como Administrador, o Windows (UIPI) descarta silenciosamente o
    input sintético enviado por um processo não elevado, e o pydirectinput
    continua "reportando sucesso" — sem isso o usuário não teria pista
    nenhuma do motivo de nada estar funcionando.
    """
    try:
        is_admin = ctypes.windll.shell32.IsUserAnAdmin()
    except (AttributeError, OSError):
        return
    if not is_admin:
        print(
            "AVISO: este script não está sendo executado como Administrador. "
            "Se o League of Legends (ou o Vanguard) estiver rodando elevado, "
            "o Windows pode bloquear silenciosamente as teclas/cliques simulados. "
            "Se os comandos não surtirem efeito no jogo, execute como Administrador."
        )


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

    _set_dpi_awareness()
    _warn_if_not_admin()

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

    # Rastreia, por AÇÃO (tecla, 'Ctrl', 'R-Click' ou 'L-Click'), quais botões
    # físicos do controle a estão mantendo pressionada no momento. Isso é
    # necessário porque a GUI permite mapear mais de um botão físico para a
    # mesma ação: se guardássemos apenas um booleano por ação (ou nada, no
    # caso de Ctrl/cliques), soltar UM dos botões enviaria keyUp/mouseUp
    # mesmo com o outro botão mapeado para a mesma ação ainda pressionado.
    # Só disparamos o "down" real quando o primeiro botão começa a segurar a
    # ação, e o "up" real quando o último botão que a segurava é solto.
    action_holders = defaultdict(set)

    def _apply_action_state(action, down):
        """Efetiva (de fato) o down/up de uma ação — chamado só na borda."""
        if action == "Ctrl":
            if down:
                pydirectinput.keyDown('ctrl')
            else:
                pydirectinput.keyUp('ctrl')
        elif action == "R-Click":
            aim_math.simulate_right_click(down)
        elif action == "L-Click":
            aim_math.simulate_left_click(down)
        else:
            # Ação de tecla comum (q, e, r, 1, 2, 3, 4, p, b, f, etc.)
            if down:
                pydirectinput.keyDown(action)
            else:
                pydirectinput.keyUp(action)

    def _handle_action(btn_name, is_pressed):
        """Executa a ação mapeada para o botão do controle, seja ela mouse ou teclado."""
        action = config.MAPPING.get(btn_name, "")
        if not action or action == "—":
            return

        holders = action_holders[action]
        if is_pressed:
            if btn_name in holders:
                return  # evento repetido, já contabilizado
            was_active = bool(holders)
            holders.add(btn_name)
            keys_pressed.add(btn_name)
            if not was_active:
                _apply_action_state(action, True)
        else:
            if btn_name not in holders:
                return
            holders.discard(btn_name)
            keys_pressed.discard(btn_name)
            if not holders:
                _apply_action_state(action, False)

    # Maior valor absoluto já visto em cada gatilho — usado para tornar o
    # limiar de acionamento adaptável à escala do hardware.
    trigger_max = {"L2": 0, "R2": 0}

    def _is_trigger_pressed(name, state):
        """Limiar de acionamento para gatilhos analógicos (L2/R2).

        A lib 'inputs' reporta o gatilho em faixas diferentes conforme o
        controle: 0..255 no XInput padrão, mas também 0..1023, 0..4095 ou
        16-bit com sinal em alguns pads/clones. Um limiar fixo (128/16000)
        deixava uma faixa morta entre 256 e 16000 onde o gatilho nunca era
        reconhecido, deixando L2/R2 inúteis nesses controles. Aqui mantemos
        o maior valor absoluto já visto para cada gatilho e consideramos
        pressionado a partir de 50% desse máximo; enquanto nenhum acionamento
        real foi observado (máximo abaixo de um piso de ruído), usamos o
        fallback fixo de 128.
        """
        mag = abs(state)
        if mag > trigger_max[name]:
            trigger_max[name] = mag
        if trigger_max[name] > 32:
            return mag > 0.5 * trigger_max[name]
        return mag > 128

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
                    # Um lote de eventos pode chegar bem depois de Parar ter
                    # sido clicado (get_gamepad() bloqueia); não injete mais
                    # nenhum input se o encerramento já foi sinalizado —
                    # senão uma tecla/clique pode ficar presa mesmo após
                    # cleanup() já ter rodado.
                    if stop_event.is_set():
                        return

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
                        pressed = _is_trigger_pressed("L2", state)
                        if pressed != trigger_states["L2"]:
                            trigger_states["L2"] = pressed
                            _handle_action("L2", pressed)

                    elif code == r2_code:
                        pressed = _is_trigger_pressed("R2", state)
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

            except UnpluggedError:
                # Controle foi desconectado: não há mais como ler input.
                # Zera os eixos para que o loop principal volte ao neutro
                # (evita WASD/mira travados na última posição lida) e sinaliza
                # o encerramento para que cleanup() solte tudo de fato.
                lx = ly = rx = ry = 0.0
                stop_event.set()
                print("Controle desconectado. Encerrando o script.")
                break
            except Exception as exc:
                # Erro inesperado (não é uma desconexão conhecida): também
                # zera os eixos e encerra, mas deixa o erro visível em vez de
                # escondê-lo silenciosamente.
                lx = ly = rx = ry = 0.0
                stop_event.set()
                print(f"Erro inesperado na leitura do controle: {exc!r}")
                break

    def cleanup():
        """Garante que todas as teclas e cliques sejam soltos ao parar."""
        wasd_logic.release_all_wasd()

        # Solta de fato qualquer ação que ainda tinha algum botão segurando-a
        for action, holders in list(action_holders.items()):
            if holders:
                _apply_action_state(action, False)
        action_holders.clear()
        keys_pressed.clear()

        # Garantias extras (idempotentes) para o caso de algum estado ter
        # ficado inconsistente: nunca custa soltar de novo.
        pydirectinput.keyUp('ctrl')
        aim_math.simulate_right_click(False)
        aim_math.simulate_left_click(False)

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
        # Sinaliza o encerramento e espera a thread leitora terminar antes de
        # liberar teclas/mouse — get_gamepad() não tem timeout e não pode ser
        # interrompida, mas o próximo lote de eventos que ela processar
        # (se algum já estiver em trânsito) agora respeita stop_event no
        # início do laço `for event in events`. Sem esse join, um evento
        # em trânsito podia chegar depois de cleanup() já ter rodado e
        # deixar uma tecla/clique presa.
        stop_event.set()
        t_reader.join(timeout=1.0)
        cleanup()
        print("Script parado. Todas as teclas foram soltas.")


if __name__ == "__main__":
    main()
