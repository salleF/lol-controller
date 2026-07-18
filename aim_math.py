import math
import time
import config
import pydirectinput

# Desativar a pausa e fail-safe do pydirectinput para melhorar a performance
pydirectinput.PAUSE = 0
pydirectinput.FAILSAFE = False

import ctypes

_last_was_in_deadzone = False

# --- Estado da animação de retorno elástico ao centro ---
# Quando o analógico direito é solto (cruza para dentro da deadzone), em vez de
# teleportar o cursor para o centro num único frame, interpolamos suavemente da
# posição atual até o centro ao longo de config.AIM_RETURN_MS milissegundos,
# usando uma curva ease-out cúbica (monotônica, sem overshoot). A animação é
# tocada a partir do próprio tick de 100Hz de main.py (não há thread/timer
# novo): cada chamada de update_aim() avança um passo com base no tempo
# decorrido. Se AIM_RETURN_MS for 0, o comportamento antigo de teleporte
# instantâneo é reproduzido exatamente.
_returning = False
_return_start_time = 0.0
_return_start_x = 0
_return_start_y = 0
_return_duration = 0.0


class _POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


def _get_cursor_pos():
    """Posição atual do cursor em pixels físicos (o processo já é DPI-aware)."""
    pt = _POINT()
    ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
    return pt.x, pt.y


def update_aim(rx, ry):
    """
    Recebe os valores do Analógico Direito (rx, ry) normalizados entre -1.0 e 1.0.
    Move o mouse proporcionalmente dentro do círculo invisível.
    Se o analógico for solto, o mouse retorna suavemente ao centro (animação
    elástica ease-out de config.AIM_RETURN_MS ms; 0 = teleporte instantâneo).
    """
    global _last_was_in_deadzone, _returning
    global _return_start_time, _return_start_x, _return_start_y, _return_duration

    center_x = config.SCREEN_WIDTH // 2
    center_y = config.SCREEN_HEIGHT // 2

    # Calcula a magnitude do vetor para aplicar a deadzone
    magnitude = math.sqrt(rx**2 + ry**2)

    if magnitude < config.DEADZONE:
        if not _last_was_in_deadzone:
            # Borda: o analógico acabou de ser solto.
            _last_was_in_deadzone = True
            return_ms = config.AIM_RETURN_MS
            if return_ms <= 0:
                # Comportamento antigo: teleporte instantâneo para o centro.
                ctypes.windll.user32.SetCursorPos(center_x, center_y)
                _returning = False
            else:
                # Inicia a animação a partir de onde o cursor está agora.
                _return_start_x, _return_start_y = _get_cursor_pos()
                _return_start_time = time.perf_counter()
                _return_duration = return_ms / 1000.0
                _returning = True
            return

        # Já estava dentro da deadzone: avança a animação se ainda em curso.
        if _returning:
            elapsed = time.perf_counter() - _return_start_time
            t = elapsed / _return_duration
            if t >= 1.0:
                # Última etapa: garante que termina exatamente no centro e
                # depois para de tocar no cursor (assim o usuário pode usar o
                # mouse de verdade depois se quiser).
                ctypes.windll.user32.SetCursorPos(center_x, center_y)
                _returning = False
            else:
                eased = 1.0 - (1.0 - t) ** 3  # ease-out cúbica, monotônica
                cur_x = int(_return_start_x + (center_x - _return_start_x) * eased)
                cur_y = int(_return_start_y + (center_y - _return_start_y) * eased)
                ctypes.windll.user32.SetCursorPos(cur_x, cur_y)
        # Se a animação já terminou, NÃO tocamos mais no cursor.
        return

    _last_was_in_deadzone = False
    # O jogador empurrou o analógico de volta: aborta qualquer animação de
    # retorno em curso e deixa o input ao vivo assumir o controle imediatamente
    # (nunca "brigar" com a mira do jogador).
    _returning = False

    # Direção unitária do analógico. magnitude > 0 aqui (já passou da deadzone),
    # então a divisão é segura.
    ux = rx / magnitude
    uy = ry / magnitude

    # Reescala a magnitude para que o cursor comece do ZERO na borda da deadzone
    # em vez de "pular" DEADZONE*AIM_RADIUS pixels no primeiro instante em que o
    # analógico cruza a deadzone. Assim a mira fina perto do centro fica acessível
    # e o deslocamento é contínuo a partir da borda. Deflexão total = raio efetivo.
    clamped = min(magnitude, 1.0)
    scaled = (clamped - config.DEADZONE) / (1.0 - config.DEADZONE)

    # Limita o raio efetivo ao maior círculo que cabe na tela. Se AIM_RADIUS for
    # maior que a distância do centro até a borda mais próxima, o clamp de tela
    # faria o cursor "grudar" numa borda por uma faixa de deflexões e comprimir
    # um eixo em relação ao outro; usar o raio efetivo mantém os dois eixos
    # proporcionais e deixa o clamp abaixo apenas como rede de segurança.
    eff_radius = min(config.AIM_RADIUS, center_x, center_y)

    # Calcula a posição proporcional à inclinação do analógico
    target_x = center_x + int(ux * scaled * eff_radius)
    target_y = center_y + int(uy * scaled * eff_radius)

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
