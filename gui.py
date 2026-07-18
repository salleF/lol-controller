# ==============================================================================
# GUI do LoL Controller — Interface com controle visual e calibração
# ==============================================================================
"""GUI do LoL Controller (customtkinter).

Este módulo implementa toda a interface gráfica do app: o diagrama visual do
controle e a barra de habilidades do LoL (aba "Mapeamento"), onde o usuário
associa botões físicos a teclas/ações; a aba "Configurações" (resolução,
raio de mira, deadzone, inversão de eixos); o painel de detecção ao vivo de
input do gamepad; e o `CalibrationWizard`, um assistente passo-a-passo que
detecta automaticamente os códigos de botão/eixo de um controle não-padrão.
O botão Iniciar/Parar do cabeçalho roda o loop de controle de main.py em uma
thread de segundo plano.
"""
import customtkinter as ctk
import tkinter as tk
import threading
import queue
import os
import sys
import ctypes

# Quando congelado pelo PyInstaller (onefile), os dados embarcados (icon.ico e
# os assets do customtkinter) sao extraidos para sys._MEIPASS; ao rodar do
# codigo-fonte, cai no diretorio do proprio arquivo.
SCRIPT_DIR = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

import config

# Declara o processo como "DPI aware" o quanto antes, antes de qualquer janela
# Tk/CTk ser criada. Sem isso, em displays com escala (125%/150%/etc.) o
# Windows escala a janela e as coordenadas de tela reportadas ficam erradas,
# o que desalinha a matemática de mira em aim_math.py (que usa GetSystemMetrics
# e SetCursorPos em coordenadas físicas). Antes, isso só funcionava por efeito
# colateral não documentado do customtkinter.
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PROCESS_PER_MONITOR_DPI_AWARE
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

# Lock global para evitar que duas threads leitoras de gamepad (o painel de
# detecção e o assistente de calibração) chamem get_gamepad() simultaneamente
# sobre o mesmo dispositivo — a lib 'inputs' não é segura para múltiplos
# leitores concorrentes e os eventos acabam se perdendo/dividindo entre filas.
_gamepad_reader_lock = threading.Lock()


def _get_system_resolution():
    """Retorna (largura, altura) da tela principal via Win32 GetSystemMetrics,
    ou None se a chamada falhar (ex.: rodando fora do Windows)."""
    try:
        user32 = ctypes.windll.user32
        w = user32.GetSystemMetrics(0)   # SM_CXSCREEN
        h = user32.GetSystemMetrics(1)   # SM_CYSCREEN
        if w > 0 and h > 0:
            return w, h
    except Exception:
        pass
    return None

# ==============================================================================
# CONSTANTES DE DESIGN
# ==============================================================================
BG_DARK = "#0d0d1a"
BG_CARD = "#161630"
BG_CARD_HOVER = "#1e1e45"
BG_INPUT = "#1a1a3e"
BG_GLOW = "#2d1b69"
ACCENT_PRIMARY = "#7c3aed"
ACCENT_PRIMARY_HOVER = "#6d28d9"
ACCENT_SECONDARY = "#06b6d4"
ACCENT_SUCCESS = "#10b981"
ACCENT_DANGER = "#ef4444"
ACCENT_WARNING = "#f59e0b"
TEXT_PRIMARY = "#f1f5f9"
TEXT_SECONDARY = "#94a3b8"
TEXT_MUTED = "#64748b"
BORDER_COLOR = "#2e2e5e"
BORDER_COLOR_STRONG = "#3f3f7a"

# Escala de espaçamento consistente, usada em todo o layout em vez de valores
# soltos de padx/pady — evita a mistura de gaps de 4px e 20px lado a lado que
# fazia o layout parecer espremido em uns lugares e desalinhado em outros.
PAD_XS = 6
PAD_SM = 10
PAD_MD = 16
PAD_LG = 22
PAD_XL = 30

# Nomes amigáveis dos botões
BUTTON_LABELS = {
    "SQUARE":     "□  Quadrado / X",
    "TRIANGLE":   "△  Triângulo / Y",
    "CIRCLE":     "○  Bola / B",
    "CROSS":      "✕  Cruz / A",
    "R1":         "R1 / RB",
    "L1":         "L1 / LB",
    "R2":         "R2 / RT",
    "L2":         "L2 / LT",
    "DPAD_UP":    "↑  D-Pad Cima",
    "DPAD_RIGHT": "→  D-Pad Direita",
    "DPAD_DOWN":  "↓  D-Pad Baixo",
    "DPAD_LEFT":  "←  D-Pad Esquerda",
    "L3":         "L3 (Pressionar Analógico E)",
    "R3":         "R3 (Pressionar Analógico D)",
    "START":      "START / Options",
    "SELECT":     "SELECT / Share",
}

BUTTON_DESCRIPTIONS = {
    "SQUARE": "Habilidade Q", "TRIANGLE": "Habilidade W",
    "CIRCLE": "Habilidade E", "CROSS": "Habilidade R (Ultimate)",
    "R1": "Feitiço 2 (F)", "L1": "Feitiço 1 (Q)",
    "DPAD_UP": "Item 1", "DPAD_RIGHT": "Item 2",
    "DPAD_DOWN": "Item 3", "DPAD_LEFT": "Item 4",
    "L2": "Gatilho L2 / LT", "R2": "Gatilho R2 / RT",
    "L3": "Outra Tecla", "R3": "Ataque Básico / Extra",
    "START": "Menu do Jogo", "SELECT": "Retorno (Recall)",
}

AVAILABLE_KEYS = [
    "q", "e", "r", "t", "y", "u", "i", "o", "p",
    "f", "g", "h", "j", "k", "l",
    "z", "x", "c", "v", "b", "n", "m",
    "1", "2", "3", "4", "5", "6", "7",
    "space", "shift", "tab", "escape",
]


# ==============================================================================
# WIDGET DE ANALÓGICO VISUAL
# ==============================================================================
class AnalogStickWidget(ctk.CTkFrame):
    """Pequeno widget de canvas que desenha a posição ao vivo de um analógico
    (bolinha dentro de um círculo), colorida de acordo com a magnitude do
    deslocamento — usado no diagrama do controle e no painel de detecção."""

    def __init__(self, parent, label_text, size=104):
        super().__init__(parent, fg_color="transparent", width=size, height=size + 24)
        self.pack_propagate(False)
        self.size = size
        self.center = size // 2
        self.stick_radius = (size // 2) - 12

        self.canvas = tk.Canvas(self, width=size, height=size,
                                bg=BG_INPUT, highlightthickness=0, bd=0)
        self.canvas.pack()
        pad = 6
        self.canvas.create_oval(pad, pad, size - pad, size - pad,
                                outline=BORDER_COLOR_STRONG, width=2, fill=BG_DARK)
        c = self.center
        self.canvas.create_line(c, pad + 2, c, size - pad - 2, fill="#1e1e45", width=1)
        self.canvas.create_line(pad + 2, c, size - pad - 2, c, fill="#1e1e45", width=1)
        dot_r = 6
        self.dot = self.canvas.create_oval(c - dot_r, c - dot_r, c + dot_r, c + dot_r,
                                           fill=ACCENT_SECONDARY, outline="#22d3ee", width=1)
        ctk.CTkLabel(self, text=label_text, font=ctk.CTkFont(size=11, weight="bold"),
                     text_color=TEXT_SECONDARY).pack(pady=(6, 0))

    def update_position(self, x, y):
        dot_r = 6
        px = self.center + int(x * self.stick_radius)
        py = self.center + int(y * self.stick_radius)
        self.canvas.coords(self.dot, px - dot_r, py - dot_r, px + dot_r, py + dot_r)
        mag = (x ** 2 + y ** 2) ** 0.5
        if mag > 0.3:
            self.canvas.itemconfig(self.dot, fill=ACCENT_PRIMARY, outline="#a855f7")
        elif mag > 0.1:
            self.canvas.itemconfig(self.dot, fill=ACCENT_SECONDARY, outline="#22d3ee")
        else:
            self.canvas.itemconfig(self.dot, fill=TEXT_MUTED, outline=TEXT_MUTED)


# ==============================================================================
# ASSISTENTE DE CALIBRAÇÃO
# ==============================================================================
class CalibrationWizard(ctk.CTkToplevel):
    """Guia passo-a-passo para calibrar o layout do controle."""

    STEPS = [
        ("button",  "CROSS",      "✕",  "Pressione o botão  ✕  Cruz / A"),
        ("button",  "CIRCLE",     "○",  "Pressione o botão  ○  Bola / B"),
        ("button",  "SQUARE",     "□",  "Pressione o botão  □  Quadrado / X"),
        ("button",  "TRIANGLE",   "△",  "Pressione o botão  △  Triângulo / Y"),
        ("button",  "L1",         "L1", "Pressione  L1 / LB"),
        ("button",  "R1",         "R1", "Pressione  R1 / RB"),
        ("button",  "L3",         "L3", "Pressione o Analógico ESQUERDO (L3)"),
        ("button",  "R3",         "R3", "Pressione o Analógico DIREITO (R3)"),
        ("button",  "START",      "START", "Pressione OPTIONS / START / MENU"),
        ("button",  "SELECT",     "SELECT", "Pressione SHARE / SELECT / BACK"),
        ("trigger", "L2",         "L2", "Pressione  L2 / LT  até o fundo"),
        ("trigger", "R2",         "R2", "Pressione  R2 / RT  até o fundo"),
        ("dpad",    "DPAD_UP",    "↑",  "Pressione  D-Pad  ↑  Cima"),
        ("dpad",    "DPAD_RIGHT", "→",  "Pressione  D-Pad  →  Direita"),
        ("analog",  "LX_RIGHT",  "⊙→", "Mova o Analógico ESQUERDO\ntodo para a DIREITA"),
        ("analog",  "LY_UP",     "⊙↑", "Mova o Analógico ESQUERDO\ntodo para CIMA"),
        ("analog",  "RX_RIGHT",  "⊙→", "Mova o Analógico DIREITO\ntodo para a DIREITA"),
        ("analog",  "RY_UP",     "⊙↑", "Mova o Analógico DIREITO\ntodo para CIMA"),
    ]

    def __init__(self, parent_app):
        super().__init__(parent_app)
        self.parent_app = parent_app
        self.current_step = 0
        self.results = {}
        self.event_queue = queue.Queue()
        self.detect_stop = threading.Event()
        self.waiting = False
        self.assigned_codes = set()
        self._advance_after_id = None
        self._poll_job = None

        # --- Janela ---
        self.title("Calibração do Controle")
        self.geometry("500x440")
        self.configure(fg_color=BG_DARK)
        self.resizable(False, False)
        self.transient(parent_app)
        self.grab_set()
        self.update_idletasks()
        x = parent_app.winfo_x() + (parent_app.winfo_width() // 2) - 250
        y = parent_app.winfo_y() + (parent_app.winfo_height() // 2) - 220
        self.geometry(f"+{x}+{y}")
        self.protocol("WM_DELETE_WINDOW", self._cancel)

        # --- UI ---
        card = ctk.CTkFrame(self, fg_color=BG_CARD, corner_radius=14)
        card.pack(fill="both", expand=True, padx=12, pady=12)
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=24, pady=20)

        ctk.CTkLabel(inner, text="🎮  Calibração do Controle",
                     font=ctk.CTkFont(size=18, weight="bold"),
                     text_color=TEXT_PRIMARY).pack(anchor="w")
        self.step_lbl = ctk.CTkLabel(inner, text="",
                                     font=ctk.CTkFont(size=11), text_color=TEXT_MUTED)
        self.step_lbl.pack(anchor="w", pady=(2, 8))

        self.progress = ctk.CTkProgressBar(inner, progress_color=ACCENT_PRIMARY,
                                           fg_color=BG_INPUT, height=6, corner_radius=3)
        self.progress.pack(fill="x", pady=(0, 20))
        self.progress.set(0)

        self.symbol_lbl = ctk.CTkLabel(inner, text="",
                                       font=ctk.CTkFont(size=52, weight="bold"),
                                       text_color=ACCENT_SECONDARY)
        self.symbol_lbl.pack(pady=(10, 6))

        self.instr_lbl = ctk.CTkLabel(inner, text="",
                                      font=ctk.CTkFont(size=15, weight="bold"),
                                      text_color=TEXT_PRIMARY, justify="center")
        self.instr_lbl.pack(pady=(0, 6))

        # Feedback
        self.feedback_frame = ctk.CTkFrame(inner, fg_color=BG_INPUT, corner_radius=8,
                                           height=36)
        self.feedback_frame.pack(fill="x", pady=(8, 16))
        self.feedback_frame.pack_propagate(False)
        self.feedback_lbl = ctk.CTkLabel(self.feedback_frame, text="Aguardando input...",
                                         font=ctk.CTkFont(size=12),
                                         text_color=TEXT_MUTED)
        self.feedback_lbl.pack(expand=True)

        # Botões
        btn_row = ctk.CTkFrame(inner, fg_color="transparent")
        btn_row.pack(fill="x", side="bottom")

        self.next_btn = ctk.CTkButton(
            btn_row, text="Próximo →", width=130, height=36, corner_radius=8,
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=ACCENT_SUCCESS, hover_color="#0d9668", text_color="#ffffff",
            state="disabled", command=self._next_step,
        )
        self.next_btn.pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            btn_row, text="Pular", width=80, height=36, corner_radius=8,
            font=ctk.CTkFont(size=12), fg_color=BG_INPUT,
            hover_color=BG_CARD_HOVER, text_color=TEXT_SECONDARY,
            border_width=1, border_color=BORDER_COLOR,
            command=self._skip_step,
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            btn_row, text="Cancelar", width=90, height=36, corner_radius=8,
            font=ctk.CTkFont(size=12), fg_color=BG_INPUT,
            hover_color=ACCENT_DANGER, text_color=TEXT_SECONDARY,
            border_width=1, border_color=BORDER_COLOR,
            command=self._cancel,
        ).pack(side="right")

        # --- Iniciar ---
        self._start_reader()
        self._show_step()

    # ---------- Leitor de gamepad ----------
    def _start_reader(self):
        self.detect_stop.clear()
        t = threading.Thread(target=self._reader_loop, daemon=True)
        t.start()

    def _reader_loop(self):
        stop = self.detect_stop
        try:
            from inputs import get_gamepad
        except ImportError:
            self.event_queue.put(("__error__", "Biblioteca 'inputs' não encontrada"))
            return

        # Evita duas threads (calibração + painel de detecção) chamando
        # get_gamepad() ao mesmo tempo. O leitor anterior pode ainda estar
        # bloqueado dentro de get_gamepad() segurando o lock (ele o solta assim
        # que o próximo evento chega), então esperamos o lock em vez de exibir
        # um erro fatal — desistimos apenas se a calibração for cancelada antes
        # de conseguir o lock.
        while not stop.is_set():
            if _gamepad_reader_lock.acquire(timeout=0.5):
                break
        else:
            return
        try:
            while not stop.is_set():
                try:
                    events = get_gamepad()
                    for ev in events:
                        if ev.ev_type == "Sync":
                            continue
                        if stop.is_set():
                            return
                        self.event_queue.put(ev)
                except Exception as e:
                    self.event_queue.put(("__error__", str(e)))
                    break
        finally:
            _gamepad_reader_lock.release()

    # ---------- Exibir passo ----------
    def _show_step(self):
        # Cancela qualquer job de after() pendente de um passo anterior
        # (evita pilhas de _poll_events/_auto_advance concorrentes quando o
        # usuário clica "Pular"/"Próximo" rapidamente).
        if self._poll_job is not None:
            try:
                self.after_cancel(self._poll_job)
            except Exception:
                pass
            self._poll_job = None
        if self._advance_after_id is not None:
            try:
                self.after_cancel(self._advance_after_id)
            except Exception:
                pass
            self._advance_after_id = None

        if self.current_step >= len(self.STEPS):
            self._show_done()
            return

        # Limpar fila
        while not self.event_queue.empty():
            try:
                self.event_queue.get_nowait()
            except queue.Empty:
                break

        step_type, name, symbol, instruction = self.STEPS[self.current_step]
        total = len(self.STEPS)

        self.step_lbl.configure(text=f"Passo {self.current_step + 1} de {total}")
        self.progress.set(self.current_step / total)
        self.symbol_lbl.configure(text=symbol)
        self.instr_lbl.configure(text=instruction)
        self.feedback_lbl.configure(text="Aguardando input...", text_color=TEXT_MUTED)
        self.feedback_frame.configure(fg_color=BG_INPUT, border_width=0)
        self.next_btn.configure(state="disabled", text="Próximo →")

        self.waiting = True
        self._poll_events()

    # ---------- Processar eventos ----------
    def _poll_events(self):
        if not self.waiting:
            return
        try:
            for _ in range(30):
                ev = self.event_queue.get_nowait()
                if isinstance(ev, tuple) and ev[0] == "__error__":
                    self._show_error(ev[1])
                    return
                if self._try_match(ev):
                    return
        except queue.Empty:
            pass
        if self.waiting:
            self._poll_job = self.after(16, self._poll_events)

    def _show_error(self, message):
        """Exibe um erro do leitor de gamepad (lib ausente, desconexão, lock
        de leitor ocupado) em vez de deixar a tela travada em 'Aguardando
        input...' sem explicação."""
        self.waiting = False
        self.feedback_lbl.configure(text=f"❌  {message}", text_color=ACCENT_DANGER)
        self.feedback_frame.configure(fg_color="#3b0d0d", border_width=1,
                                      border_color=ACCENT_DANGER)

    def _try_match(self, event):
        step_type, name, symbol, instruction = self.STEPS[self.current_step]
        code = event.code
        state = event.state

        if step_type == "button":
            if event.ev_type == "Key" and state == 1 and code not in self.assigned_codes:
                self.results[name] = code
                self.assigned_codes.add(code)
                self._show_matched(f"Detectado: {code}")
                return True

        elif step_type == "trigger":
            if event.ev_type == "Absolute":
                # Além do gatilho analógico (0..255>180 ou >20000), aceita o
                # caso em que L2/R2 chegam como eixo Absolute digital 0/1 —
                # senão esse controle nunca casa no passo do gatilho.
                is_trigger = (0 <= state <= 255 and state > 180) or (state > 20000) or (abs(state) == 1)
                if is_trigger and code not in self.assigned_codes:
                    self.results[name] = code
                    self.assigned_codes.add(code)
                    self._show_matched(f"Detectado: {code} (valor {state})")
                    return True
            elif event.ev_type == "Key" and state == 1 and code not in self.assigned_codes:
                # Alguns controles reportam L2/R2 como botão digital (0/1)
                # em vez de eixo analógico — aceita esse formato também.
                self.results[name] = code
                self.assigned_codes.add(code)
                self._show_matched(f"Detectado: {code} (botão)")
                return True

        elif step_type == "dpad":
            if event.ev_type == "Absolute" and state != 0 and abs(state) <= 1:
                self.results[name] = {"code": code, "value": state}
                self._show_matched(f"Detectado: {code} = {state}")
                return True
            if event.ev_type == "Key" and state == 1 and code not in self.assigned_codes:
                self.results[name] = {"code": code, "value": 1, "is_key": True}
                self.assigned_codes.add(code)
                self._show_matched(f"Detectado: {code} (botão)")
                return True

        elif step_type == "analog":
            # Aceita tanto eixos de 16 bits (deflexão total ~32767) quanto
            # eixos de faixa menor (8 bits, 0..255) que nunca chegam a 20000 —
            # espelha a lógica de faixa dupla do passo de gatilho, senão a
            # calibração trava em "Aguardando input..." nesses controles.
            is_analog = (abs(state) > 180 and abs(state) <= 255) or abs(state) > 20000
            if event.ev_type == "Absolute" and is_analog:
                if code not in self.assigned_codes:
                    self.results[name] = {"code": code, "value": state}
                    self.assigned_codes.add(code)
                    self._show_matched(f"Detectado: {code} = {state}")
                    return True
        return False

    def _show_matched(self, text):
        self.waiting = False
        self.feedback_lbl.configure(text=f"✅  {text}", text_color=ACCENT_SUCCESS)
        self.feedback_frame.configure(fg_color="#0d2818", border_width=1,
                                      border_color=ACCENT_SUCCESS)
        self.next_btn.configure(state="normal")
        self._advance_after_id = self.after(700, self._auto_advance)

    def _auto_advance(self):
        if self.next_btn.cget("state") == "normal" and self.current_step < len(self.STEPS):
            self._next_step()

    def _next_step(self):
        self.current_step += 1
        self._show_step()

    def _skip_step(self):
        self.current_step += 1
        self._show_step()

    # ---------- Concluído ----------
    def _show_done(self):
        self.progress.set(1.0)
        self.step_lbl.configure(text="Concluído!")
        self.symbol_lbl.configure(text="✅")
        self.instr_lbl.configure(text="Calibração concluída!")
        self.feedback_lbl.configure(
            text=f"{len(self.results)} inputs configurados",
            text_color=ACCENT_SUCCESS,
        )
        self.feedback_frame.configure(fg_color="#0d2818", border_width=1,
                                      border_color=ACCENT_SUCCESS)
        self.next_btn.configure(text="💾  Salvar", state="normal",
                                command=self._save)

    def _save(self):
        # Parte do layout JÁ calibrado atual, não do genérico hardcoded —
        # assim, qualquer passo pulado ou sem correspondência preserva o
        # valor calibrado anteriormente em vez de reverter para o default.
        layout = dict(config.CONTROLLER_LAYOUT)

        # Botões
        for btn in ["SQUARE", "TRIANGLE", "CIRCLE", "CROSS", "L1", "R1", "L3", "R3", "START", "SELECT"]:
            if btn in self.results:
                layout[btn] = self.results[btn]

        # Triggers
        for trigger in ["L2", "R2"]:
            if trigger in self.results:
                layout[trigger] = self.results[trigger]

        # D-pad
        if "DPAD_UP" in self.results:
            r = self.results["DPAD_UP"]
            if not r.get("is_key"):
                layout["DPAD_Y_CODE"] = r["code"]
                layout["DPAD_UP_VAL"] = r["value"]
                layout["DPAD_DOWN_VAL"] = -r["value"]
        if "DPAD_RIGHT" in self.results:
            r = self.results["DPAD_RIGHT"]
            if not r.get("is_key"):
                layout["DPAD_X_CODE"] = r["code"]
                layout["DPAD_RIGHT_VAL"] = r["value"]
                layout["DPAD_LEFT_VAL"] = -r["value"]

        # Analógicos
        if "LX_RIGHT" in self.results:
            r = self.results["LX_RIGHT"]
            layout["AXIS_LX"] = r["code"]
            layout["INVERT_LX"] = r["value"] < 0
        if "LY_UP" in self.results:
            r = self.results["LY_UP"]
            layout["AXIS_LY"] = r["code"]
            layout["INVERT_LY"] = r["value"] > 0
        if "RX_RIGHT" in self.results:
            r = self.results["RX_RIGHT"]
            layout["AXIS_RX"] = r["code"]
            layout["INVERT_RX"] = r["value"] < 0
        if "RY_UP" in self.results:
            r = self.results["RY_UP"]
            layout["AXIS_RY"] = r["code"]
            layout["INVERT_RY"] = r["value"] > 0

        # Aplicar e salvar
        config.CONTROLLER_LAYOUT = layout
        config.save_config()

        # Notificar a GUI principal
        self.parent_app._rebuild_detection_maps()
        self.parent_app._flash_status("✅  Controle calibrado com sucesso!", ACCENT_SUCCESS)
        self._cancel()

    def _cancel(self):
        self.detect_stop.set()
        self.waiting = False
        # Cancela quaisquer callbacks self.after() pendentes antes de
        # destruir a janela, para não disparar TclError em widgets já
        # destruídos quando o timer chegar.
        if self._advance_after_id is not None:
            try:
                self.after_cancel(self._advance_after_id)
            except Exception:
                pass
            self._advance_after_id = None
        if self._poll_job is not None:
            try:
                self.after_cancel(self._poll_job)
            except Exception:
                pass
            self._poll_job = None
        self.grab_release()
        if getattr(self.parent_app, "_calibration_wizard", None) is self:
            self.parent_app._calibration_wizard = None
        self.destroy()


# ==============================================================================
# CLASSE PRINCIPAL DA GUI
# ==============================================================================
class LoLControllerApp(ctk.CTk):
    """Janela principal do LoL Controller Configurator.

    Possui duas abas — Mapeamento (diagrama visual do controle + barra de
    habilidades do LoL + painel de detecção ao vivo) e Configurações
    (resolução, raio de mira, deadzone, inversão de eixos) — e o botão
    Iniciar/Parar do cabeçalho, que roda o loop de controle de main.py em
    uma thread de segundo plano. Mantém o estado de config (config.py) e o
    estado de UI (self.ctrl_buttons, self.hud_slots, self.setting_vars).
    """

    def __init__(self):
        super().__init__()

        self.title("LoL Controller Configurator")
        self.geometry("1040x940")
        self.minsize(960, 820)
        self.configure(fg_color=BG_DARK)
        self.resizable(True, True)

        icon_path = os.path.join(SCRIPT_DIR, "icon.ico")
        if os.path.exists(icon_path):
            self.iconbitmap(icon_path)

        # Estado
        self.is_running = False
        self.detecting = False
        self.stop_event = threading.Event()
        self.detect_stop = threading.Event()
        self.event_queue = queue.Queue()
        self.ctrl_buttons = {}
        self.hud_slots = {}
        self.setting_vars = {}
        self.analog_state = {"lx": 0.0, "ly": 0.0, "rx": 0.0, "ry": 0.0}
        self._calibration_wizard = None
        self._controller_thread = None

        config.load_config()
        self._rebuild_detection_maps()

        self._build_header()
        self._build_tabs()
        self._build_status_bar()

        # Inicializa o HUD carregando o mapeamento correto
        self._update_all_mappings_ui()

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ---------- Mapas dinâmicos de detecção ----------
    def _rebuild_detection_maps(self):
        """Reconstrói os mapas de detecção a partir do CONTROLLER_LAYOUT atual."""
        layout = config.CONTROLLER_LAYOUT
        self._btn_code_map = {}
        for btn in ["SQUARE", "TRIANGLE", "CIRCLE", "CROSS", "L1", "R1", "L2", "R2", "L3", "R3", "START", "SELECT"]:
            self._btn_code_map[layout.get(btn, "")] = btn
        self._l2_code = layout.get("L2", "ABS_Z")
        self._r2_code = layout.get("R2", "ABS_RZ")
        self._dpad_y_code = layout.get("DPAD_Y_CODE", "ABS_HAT0Y")
        self._dpad_x_code = layout.get("DPAD_X_CODE", "ABS_HAT0X")
        self._dpad_up_val = layout.get("DPAD_UP_VAL", -1)
        self._dpad_down_val = layout.get("DPAD_DOWN_VAL", 1)
        self._dpad_left_val = layout.get("DPAD_LEFT_VAL", -1)
        self._dpad_right_val = layout.get("DPAD_RIGHT_VAL", 1)
        self._axis_lx = layout.get("AXIS_LX", "ABS_X")
        self._axis_ly = layout.get("AXIS_LY", "ABS_Y")
        self._axis_rx = layout.get("AXIS_RX", "ABS_RX")
        self._axis_ry = layout.get("AXIS_RY", "ABS_RY")
        self._invert_lx = layout.get("INVERT_LX", False)
        self._invert_ly = layout.get("INVERT_LY", True)
        self._invert_rx = layout.get("INVERT_RX", False)
        self._invert_ry = layout.get("INVERT_RY", True)

        self._update_all_mappings_ui()

        # Atualizar os checkboxes da tela se já estiverem renderizados
        if hasattr(self, "inv_lx_var"):
            self.inv_lx_var.set(self._invert_lx)
            self.inv_ly_var.set(self._invert_ly)
            self.inv_rx_var.set(self._invert_rx)
            self.inv_ry_var.set(self._invert_ry)

    @staticmethod
    def _format_mapped_key(value):
        """Texto exibido para uma tecla/ação mapeada: '—' quando vazio/None,
        senão a tecla em maiúsculas. Usado por _make_ctrl_btn e
        _update_all_mappings_ui para que os dois nunca divirjam (antes,
        _make_ctrl_btn renderizava uma string em branco para um mapeamento
        vazio como "" enquanto aqui renderizava '—')."""
        return value.upper() if value else "—"

    def _update_all_mappings_ui(self):
        """Atualiza os labels no diagrama de controle e na barra de habilidades do LoL."""
        # 1. Atualizar labels no diagrama do controle
        for btn_name, info in self.ctrl_buttons.items():
            if btn_name in config.MAPPING:
                mapped_key = config.MAPPING[btn_name]
                info["key_label"].configure(text=self._format_mapped_key(mapped_key))

        # 2. Atualizar labels na barra do LoL
        for key_code, info in self.hud_slots.items():
            info["lbl_btn"].configure(text="—")

        for btn_name, key_code in config.MAPPING.items():
            if key_code in self.hud_slots:
                short_label = btn_name
                if btn_name == "SQUARE": short_label = "□ X"
                elif btn_name == "TRIANGLE": short_label = "△ Y"
                elif btn_name == "CIRCLE": short_label = "○ B"
                elif btn_name == "CROSS": short_label = "✕ A"
                elif btn_name == "DPAD_UP": short_label = "D-Up"
                elif btn_name == "DPAD_RIGHT": short_label = "D-Right"
                elif btn_name == "DPAD_DOWN": short_label = "D-Down"
                elif btn_name == "DPAD_LEFT": short_label = "D-Left"
                self.hud_slots[key_code]["lbl_btn"].configure(text=short_label)

    # ==========================================================================
    # HEADER
    # ==========================================================================
    def _build_header(self):
        header = ctk.CTkFrame(self, fg_color=BG_CARD, corner_radius=0, height=84)
        header.pack(fill="x")
        header.pack_propagate(False)
        inner = ctk.CTkFrame(header, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=PAD_XL)

        title_frame = ctk.CTkFrame(inner, fg_color="transparent")
        title_frame.pack(side="left", fill="y", pady=PAD_MD)
        ctk.CTkLabel(title_frame, text="🎮  LoL Controller",
                     font=ctk.CTkFont(size=26, weight="bold"),
                     text_color=TEXT_PRIMARY).pack(anchor="w")
        ctk.CTkLabel(title_frame, text="Configure seu controle para jogar LoL de forma nativa e ergonômica",
                     font=ctk.CTkFont(size=12),
                     text_color=TEXT_SECONDARY).pack(anchor="w", pady=(3, 0))

        self.start_btn = ctk.CTkButton(
            inner, text="▶  INICIAR", width=180, height=48, corner_radius=10,
            font=ctk.CTkFont(size=15, weight="bold"),
            fg_color=ACCENT_SUCCESS, hover_color="#0d9668", text_color="#ffffff",
            command=self._toggle_script,
        )
        self.start_btn.pack(side="right", pady=PAD_MD)

        # Linha de destaque sutil separando o header do resto da janela — dá
        # uma "borda" visual em vez do header se misturar direto com o fundo.
        ctk.CTkFrame(self, fg_color=BORDER_COLOR_STRONG, height=1,
                     corner_radius=0).pack(fill="x")

    # ==========================================================================
    # TABS
    # ==========================================================================
    def _build_tabs(self):
        self.tabview = ctk.CTkTabview(
            self, fg_color=BG_DARK,
            segmented_button_fg_color=BG_CARD,
            segmented_button_selected_color=ACCENT_PRIMARY,
            segmented_button_selected_hover_color=ACCENT_PRIMARY_HOVER,
            segmented_button_unselected_color=BG_CARD,
            segmented_button_unselected_hover_color=BG_CARD_HOVER,
            text_color=TEXT_PRIMARY, corner_radius=12,
            anchor="center",
        )
        self.tabview.pack(fill="both", expand=True, padx=PAD_LG, pady=(PAD_MD, 0))
        try:
            # CTkTabview não expõe uma API pública pra fonte do seletor de abas;
            # isso é só um ajuste cosmético (abas maiores/mais legíveis), então
            # se a versão instalada do customtkinter mudar esse atributo interno,
            # falha silenciosamente em vez de quebrar a janela inteira.
            self.tabview._segmented_button.configure(font=ctk.CTkFont(size=13, weight="bold"))
        except Exception:
            pass
        self._build_mapping_tab(self.tabview.add("  🎯  Mapeamento  "))
        self._build_settings_tab(self.tabview.add("  ⚙️  Configurações  "))

    # ==========================================================================
    # ABA DE MAPEAMENTO
    # ==========================================================================
    def _build_mapping_tab(self, parent):
        scroll = ctk.CTkScrollableFrame(parent, fg_color="transparent",
                                        scrollbar_button_color=ACCENT_PRIMARY,
                                        scrollbar_button_hover_color=ACCENT_PRIMARY_HOVER)
        scroll.pack(fill="both", expand=True, padx=PAD_XS, pady=PAD_XS)

        # Header + botões de ação
        header = ctk.CTkFrame(scroll, fg_color="transparent")
        header.pack(fill="x", padx=PAD_XS, pady=(PAD_SM, PAD_MD))

        title_col = ctk.CTkFrame(header, fg_color="transparent")
        title_col.pack(side="left", fill="y")
        kicker = ctk.CTkFrame(title_col, fg_color="transparent")
        kicker.pack(anchor="w")
        ctk.CTkFrame(kicker, fg_color=ACCENT_PRIMARY, width=4, height=20,
                     corner_radius=2).pack(side="left", padx=(0, 8))
        ctk.CTkLabel(kicker, text="Controle Visual",
                     font=ctk.CTkFont(size=17, weight="bold"),
                     text_color=TEXT_PRIMARY).pack(side="left")
        ctk.CTkLabel(title_col, text="Configure pelo controle físico ou clicando nos botões abaixo",
                     font=ctk.CTkFont(size=11),
                     text_color=TEXT_MUTED).pack(anchor="w", pady=(4, 0), padx=(12, 0))

        btn_row = ctk.CTkFrame(header, fg_color="transparent")
        btn_row.pack(side="right")

        # Botão Calibrar
        ctk.CTkButton(
            btn_row, text="🔧  Calibrar", width=126, height=38, corner_radius=8,
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=ACCENT_WARNING, hover_color="#d97706", text_color="#ffffff",
            command=self._open_calibration,
        ).pack(side="left", padx=(0, PAD_SM))

        # Botão Detectar
        self.detect_btn = ctk.CTkButton(
            btn_row, text="🔍  Detectar", width=106, height=38, corner_radius=8,
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=ACCENT_PRIMARY, hover_color=ACCENT_PRIMARY_HOVER,
            text_color="#ffffff", command=self._toggle_detection,
        )
        self.detect_btn.pack(side="left", padx=(0, PAD_SM))

        # Botão Restaurar Padrões WASD
        ctk.CTkButton(
            btn_row, text="🔄  Padrão WASD", width=134, height=38, corner_radius=8,
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=BG_INPUT, hover_color=ACCENT_PRIMARY, text_color=TEXT_PRIMARY,
            border_width=1, border_color=BORDER_COLOR_STRONG,
            command=self._restore_wasd_defaults,
        ).pack(side="left")

        # Diagrama do Controle
        controller_card = ctk.CTkFrame(scroll, fg_color=BG_CARD, corner_radius=14,
                                       border_width=2, border_color=BORDER_COLOR)
        controller_card.pack(fill="x", padx=PAD_XS, pady=(0, PAD_LG))
        self._build_controller_diagram(controller_card)

        # Barra do LoL HUD (Habilidades e Ações do Game)
        self._build_lol_hud(scroll)

        # Painel de detecção
        self._build_detection_panel(scroll)

        # Salvar
        ctk.CTkButton(
            scroll, text="💾  Salvar Mapeamento", height=46, corner_radius=10,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color=ACCENT_PRIMARY, hover_color=ACCENT_PRIMARY_HOVER,
            text_color="#ffffff", command=self._save_config,
        ).pack(pady=(PAD_LG, PAD_LG))

    def _build_controller_diagram(self, parent):
        diagram = ctk.CTkFrame(parent, fg_color="transparent")
        diagram.pack(padx=PAD_XL, pady=PAD_LG, fill="x")

        # Bumpers / Triggers (Agora L2 e R2 são mapeáveis e não bloqueados)
        bumpers = ctk.CTkFrame(diagram, fg_color="transparent")
        bumpers.pack(fill="x", pady=(0, PAD_MD))
        lb = ctk.CTkFrame(bumpers, fg_color="transparent")
        lb.pack(side="left", padx=(14, 0))
        self._make_ctrl_btn(lb, "L2", "L2", w=84, h=32).pack(pady=(0, PAD_XS))
        self._make_ctrl_btn(lb, "L1", "L1", w=84, h=32).pack()
        rb = ctk.CTkFrame(bumpers, fg_color="transparent")
        rb.pack(side="right", padx=(0, 14))
        self._make_ctrl_btn(rb, "R2", "R2", w=84, h=32).pack(pady=(0, PAD_XS))
        self._make_ctrl_btn(rb, "R1", "R1", w=84, h=32).pack()

        # Corpo
        body = ctk.CTkFrame(diagram, fg_color="transparent")
        body.pack(fill="x")
        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, weight=2)
        body.columnconfigure(2, weight=1)

        # D-Pad (Esquerda)
        dc = ctk.CTkFrame(body, fg_color="transparent")
        dc.grid(row=0, column=0, padx=PAD_MD, pady=PAD_SM, sticky="n")
        ctk.CTkLabel(dc, text="D-PAD", font=ctk.CTkFont(size=11, weight="bold"),
                     text_color=TEXT_SECONDARY).pack(pady=(0, PAD_SM))
        self._build_cross(dc, ("DPAD_UP", "↑"), ("DPAD_LEFT", "←"),
                          ("DPAD_RIGHT", "→"), ("DPAD_DOWN", "↓"))

        # Analógicos, Select, Start (Centro)
        sc = ctk.CTkFrame(body, fg_color="transparent")
        sc.grid(row=0, column=1, padx=PAD_MD, pady=PAD_SM)

        # Botões Select / Start
        center_btns = ctk.CTkFrame(sc, fg_color="transparent")
        center_btns.pack(pady=(0, PAD_MD))
        self._make_ctrl_btn(center_btns, "SELECT", "SELECT", w=76, h=32).pack(side="left", padx=6)
        self._make_ctrl_btn(center_btns, "START", "START", w=76, h=32).pack(side="left", padx=6)

        ctk.CTkLabel(sc, text="ANALÓGICOS & L3/R3", font=ctk.CTkFont(size=11, weight="bold"),
                     text_color=TEXT_SECONDARY).pack(pady=(0, PAD_SM))
        sr = ctk.CTkFrame(sc, fg_color="transparent")
        sr.pack()

        left_stick_frame = ctk.CTkFrame(sr, fg_color="transparent")
        left_stick_frame.pack(side="left", padx=PAD_MD)
        self.left_stick = AnalogStickWidget(left_stick_frame, "Esquerdo (WASD)")
        self.left_stick.pack()
        self._make_ctrl_btn(left_stick_frame, "L3", "L3", w=64, h=28).pack(pady=(PAD_SM, 0))

        right_stick_frame = ctk.CTkFrame(sr, fg_color="transparent")
        right_stick_frame.pack(side="left", padx=PAD_MD)
        self.right_stick = AnalogStickWidget(right_stick_frame, "Direito (Mira)")
        self.right_stick.pack()
        self._make_ctrl_btn(right_stick_frame, "R3", "R3", w=64, h=28).pack(pady=(PAD_SM, 0))

        # Face Buttons (Direita)
        fc = ctk.CTkFrame(body, fg_color="transparent")
        fc.grid(row=0, column=2, padx=PAD_MD, pady=PAD_SM, sticky="n")
        ctk.CTkLabel(fc, text="BOTÕES DE AÇÃO", font=ctk.CTkFont(size=11, weight="bold"),
                     text_color=TEXT_SECONDARY).pack(pady=(0, PAD_SM))
        self._build_cross(fc, ("TRIANGLE", "△"), ("SQUARE", "□"),
                          ("CIRCLE", "○"), ("CROSS", "✕"))

    def _build_cross(self, parent, top, left, right, bottom):
        g = ctk.CTkFrame(parent, fg_color="transparent")
        g.pack()
        self._make_ctrl_btn(g, top[0], top[1]).grid(row=0, column=1, padx=5, pady=5)
        self._make_ctrl_btn(g, left[0], left[1]).grid(row=1, column=0, padx=5, pady=5)
        self._make_ctrl_btn(g, right[0], right[1]).grid(row=1, column=2, padx=5, pady=5)
        self._make_ctrl_btn(g, bottom[0], bottom[1]).grid(row=2, column=1, padx=5, pady=5)

    def _make_ctrl_btn(self, parent, name, symbol, w=70, h=58, special=None):
        is_mappable = name in config.MAPPING
        frame = ctk.CTkFrame(parent, fg_color=BG_INPUT, corner_radius=10,
                             border_width=2, border_color=BORDER_COLOR, width=w, height=h)
        frame.pack_propagate(False)
        sym = ctk.CTkLabel(frame, text=symbol,
                           font=ctk.CTkFont(size=15 if len(symbol) <= 2 else 12, weight="bold"),
                           text_color=TEXT_PRIMARY)
        sym.pack(expand=True, fill="both", padx=2, pady=(6, 0))
        mapped_text = special or (self._format_mapped_key(config.MAPPING.get(name, "")) if is_mappable else "")
        key_lbl = ctk.CTkLabel(frame, text=mapped_text,
                               font=ctk.CTkFont(size=10, weight="bold"),
                               text_color=ACCENT_SECONDARY)
        key_lbl.pack(pady=(0, 6))

        if is_mappable and not special:
            for w_item in [frame, sym, key_lbl]:
                w_item.bind("<Button-1>", lambda e, n=name: self._show_remap_popup(n))
                w_item.configure(cursor="hand2")

        self.ctrl_buttons[name] = {"frame": frame, "sym_label": sym,
                                   "key_label": key_lbl, "special": special}
        return frame

    # ==========================================================================
    # BARRA DO LoL HUD
    # ==========================================================================
    def _build_lol_hud(self, parent):
        hud_card = ctk.CTkFrame(
            parent, fg_color="#0a0a16", corner_radius=14,
            border_width=2, border_color="#c8aa6e",
        )
        hud_card.pack(fill="x", padx=PAD_XS, pady=(0, PAD_LG))

        inner = ctk.CTkFrame(hud_card, fg_color="transparent")
        inner.pack(padx=PAD_LG, pady=PAD_MD, fill="x")

        header_row = ctk.CTkFrame(inner, fg_color="transparent")
        header_row.pack(fill="x", pady=(0, PAD_MD))
        ctk.CTkLabel(
            header_row, text="🛡️  Barra de Ações do League of Legends ( HUD )",
            font=ctk.CTkFont(size=14, weight="bold"), text_color="#e2c88f",
        ).pack(anchor="w")
        ctk.CTkLabel(
            header_row, text="Clique em um slot para associar a um botão do controle",
            font=ctk.CTkFont(size=11), text_color=TEXT_MUTED,
        ).pack(anchor="w", pady=(2, 0))

        # Duas linhas em vez de uma fileira única: 14 slots numa fileira só
        # estouravam a largura da janela e ficavam cortados. Cada linha
        # também ganhou um rótulo de grupo (antes só a cor diferenciava).
        row1 = ctk.CTkFrame(inner, fg_color="transparent")
        row1.pack(fill="x", pady=(0, PAD_MD))
        row2 = ctk.CTkFrame(inner, fg_color="transparent")
        row2.pack(fill="x")

        # Grupo 1: Habilidades Q-W-E-R do LoL WASD
        group_skills = self._hud_group(row1, "HABILIDADES")
        self._create_hud_slot(group_skills, "R-Click", "Hab. 1\n(MB2)", color="#1e293b")
        self._create_hud_slot(group_skills, "shift", "Hab. 2\n(Shift)", color="#1e293b")
        self._create_hud_slot(group_skills, "e", "Hab. 3\n(E)", color="#1e293b")
        self._create_hud_slot(group_skills, "r", "Ultimate\n(R)", color="#1e293b")

        # Grupo 2: Feitiços de Invocador do LoL WASD
        group_summoners = self._hud_group(row1, "FEITIÇOS")
        self._create_hud_slot(group_summoners, "q", "Feit. 1\n(Q)", color="#451a03")
        self._create_hud_slot(group_summoners, "f", "Feit. 2\n(F)", color="#451a03")

        # Grupo 3: Itens Ativos 1-2-3-4
        group_items = self._hud_group(row2, "ITENS")
        for key in ["1", "2", "3"]:
            self._create_hud_slot(group_items, key, f"Item\n{key}", color="#18181b")
        self._create_hud_slot(group_items, "4", "Trinket\n(4)", color="#022c22")

        # Grupo 4: Ações Extras (Loja, Recall, Clique Esquerdo, Modificador)
        group_utils = self._hud_group(row2, "AÇÕES")
        self._create_hud_slot(group_utils, "p", "Loja\n(P)", color="#2e1065")
        self._create_hud_slot(group_utils, "b", "Recall\n(B)", color="#172554")
        self._create_hud_slot(group_utils, "L-Click", "Ataque\n(Clique)", color="#7f1d1d")
        self._create_hud_slot(group_utils, "Ctrl", "Upar\nSkill", color="#3b0764")

    def _hud_group(self, parent, label_text):
        """Coluna com um rótulo pequeno acima dos slots — reforça o
        agrupamento que antes dependia só da cor de fundo dos slots."""
        col = ctk.CTkFrame(parent, fg_color="transparent")
        col.pack(side="left", padx=(0, PAD_LG))
        ctk.CTkLabel(col, text=label_text, font=ctk.CTkFont(size=9, weight="bold"),
                     text_color="#8a7550").pack(anchor="w", pady=(0, 4))
        row = ctk.CTkFrame(col, fg_color="transparent")
        row.pack()
        return row

    def _create_hud_slot(self, parent, key_code, label_text, color):
        """Cria um slot visual na barra do LoL."""
        slot = ctk.CTkFrame(
            parent, fg_color=color, corner_radius=8,
            border_width=1, border_color="#c8aa6e", width=60, height=60,
        )
        slot.pack(side="left", padx=3)
        slot.pack_propagate(False)

        lbl_key = ctk.CTkLabel(
            slot, text=label_text,
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color="#ffffff", justify="center",
        )
        lbl_key.pack(pady=(6, 0))

        lbl_btn = ctk.CTkLabel(
            slot, text="—",
            font=ctk.CTkFont(size=9, weight="bold"),
            text_color="#c8aa6e",
        )
        lbl_btn.pack(expand=True)

        for widget in [slot, lbl_key, lbl_btn]:
            widget.bind("<Button-1>", lambda e, k=key_code: self._show_hud_remap_popup(k))
            widget.configure(cursor="hand2")

        self.hud_slots[key_code] = {
            "frame": slot,
            "lbl_key": lbl_key,
            "lbl_btn": lbl_btn,
        }

    # --------------------------------------------------------------------------
    # Popup de remapeamento via HUD
    # --------------------------------------------------------------------------
    def _show_hud_remap_popup(self, key_code):
        """Abre popup para associar uma habilidade do LoL a um botão do controle."""
        if self.is_running:
            self._flash_status("⚠️  Pare o script antes de remapear", ACCENT_WARNING)
            return
        popup = ctk.CTkToplevel(self)
        popup.title(f"Configurar Slot {key_code.upper()}")
        popup.geometry("380x250")
        popup.configure(fg_color=BG_DARK)
        popup.resizable(False, False)
        popup.transient(self)
        popup.grab_set()

        popup.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() // 2) - 190
        y = self.winfo_y() + (self.winfo_height() // 2) - 125
        popup.geometry(f"+{x}+{y}")

        card = ctk.CTkFrame(popup, fg_color=BG_CARD, corner_radius=12)
        card.pack(fill="both", expand=True, padx=12, pady=12)
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=16, pady=16)

        ctk.CTkLabel(inner, text=f"Mapear Habilidade: {key_code.upper()}",
                     font=ctk.CTkFont(size=16, weight="bold"),
                     text_color="#c8aa6e").pack(anchor="w")

        ctk.CTkLabel(inner, text="Escolha qual botão do controle ativa essa ação no LoL:",
                     font=ctk.CTkFont(size=11), text_color=TEXT_MUTED).pack(anchor="w", pady=(2, 10))

        current_btn = "Nenhum"
        for btn, key in config.MAPPING.items():
            if key == key_code:
                current_btn = btn
                break

        mappable_buttons = [
            "SQUARE", "TRIANGLE", "CIRCLE", "CROSS",
            "L1", "R1", "L2", "R2", "DPAD_UP", "DPAD_RIGHT", "DPAD_DOWN", "DPAD_LEFT",
            "L3", "R3", "START", "SELECT"
        ]

        options = ["Nenhum"] + [BUTTON_LABELS.get(b, b) for b in mappable_buttons]
        friendly_current = BUTTON_LABELS.get(current_btn, "Nenhum") if current_btn != "Nenhum" else "Nenhum"
        var = ctk.StringVar(value=friendly_current)

        dropdown = ctk.CTkOptionMenu(
            inner, variable=var, values=options,
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=BG_INPUT, button_color=ACCENT_PRIMARY,
            button_hover_color=ACCENT_PRIMARY_HOVER,
            dropdown_fg_color=BG_CARD, dropdown_hover_color=ACCENT_PRIMARY,
            dropdown_text_color=TEXT_PRIMARY, text_color=ACCENT_SECONDARY,
            corner_radius=8, width=220, height=34,
        )
        dropdown.pack(fill="x", pady=(0, 16))

        bf = ctk.CTkFrame(inner, fg_color="transparent")
        bf.pack(fill="x")

        friendly_to_internal = {BUTTON_LABELS.get(b, b): b for b in mappable_buttons}

        def apply():
            selection = var.get()
            # 1. Limpa mapeamentos antigos desta tecla
            for b, k in list(config.MAPPING.items()):
                if k == key_code:
                    config.MAPPING[b] = ""

            # 2. Associa o novo botão selecionado
            if selection != "Nenhum":
                internal_btn = friendly_to_internal[selection]
                config.MAPPING[internal_btn] = key_code

            self._update_all_mappings_ui()
            popup.destroy()
            self._flash_status(f"✅  Ação {key_code.upper()} associada com sucesso!", ACCENT_SUCCESS)

        ctk.CTkButton(bf, text="✓  Salvar", width=120, height=34, corner_radius=8,
                      font=ctk.CTkFont(size=13, weight="bold"),
                      fg_color=ACCENT_SUCCESS, hover_color="#0d9668", text_color="#ffffff",
                      command=apply).pack(side="left", padx=(0, 8))
        ctk.CTkButton(bf, text="Cancelar", width=100, height=34, corner_radius=8,
                      font=ctk.CTkFont(size=13), fg_color=BG_INPUT,
                      hover_color=BG_CARD_HOVER, text_color=TEXT_SECONDARY,
                      border_width=1, border_color=BORDER_COLOR,
                      command=popup.destroy).pack(side="left")

    # ==========================================================================
    # PAINEL DE DETECÇÃO
    # ==========================================================================
    def _build_detection_panel(self, parent):
        self.detection_card = ctk.CTkFrame(parent, fg_color=BG_CARD, corner_radius=12,
                                           border_width=1, border_color=BORDER_COLOR)
        self.detection_card.pack(fill="x", padx=PAD_XS, pady=(0, PAD_LG))
        inner = ctk.CTkFrame(self.detection_card, fg_color="transparent")
        inner.pack(fill="x", padx=PAD_LG, pady=PAD_MD)
        ctk.CTkLabel(inner, text="📡  Último Input Detectado",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=TEXT_PRIMARY).pack(anchor="w")
        ctk.CTkLabel(inner, text="Clique em '🔍 Detectar' acima e mexa no controle",
                     font=ctk.CTkFont(size=11),
                     text_color=TEXT_MUTED).pack(anchor="w", pady=(2, 0))

        g = ctk.CTkFrame(inner, fg_color="transparent")
        g.pack(fill="x", pady=(PAD_MD, 0))
        g.columnconfigure(0, weight=1)
        g.columnconfigure(1, weight=1)
        g.columnconfigure(2, weight=1)
        g.columnconfigure(3, weight=1)

        self.det_code = self._build_det_chip(g, 0, "Código", TEXT_SECONDARY)
        self.det_button = self._build_det_chip(g, 1, "Botão", TEXT_SECONDARY)
        self.det_key = self._build_det_chip(g, 2, "Tecla", ACCENT_SECONDARY)
        self.det_state = self._build_det_chip(g, 3, "Estado", TEXT_SECONDARY)

    def _build_det_chip(self, parent, col, label_text, value_color):
        """'Chip' (rótulo + valor em destaque numa pastilha) usado nos 4
        campos do painel de detecção, no lugar do texto corrido anterior —
        preenche o espaço da seção de forma mais legível e com mais peso
        visual. Retorna o CTkLabel do valor para ser atualizado depois."""
        cell = ctk.CTkFrame(parent, fg_color="transparent")
        cell.grid(row=0, column=col, sticky="ew", padx=(0 if col == 0 else PAD_SM, 0))
        ctk.CTkLabel(cell, text=label_text.upper(), font=ctk.CTkFont(size=10, weight="bold"),
                     text_color=TEXT_MUTED).pack(anchor="w", pady=(0, 4))
        chip = ctk.CTkFrame(cell, fg_color=BG_INPUT, corner_radius=8, height=40,
                            border_width=1, border_color=BORDER_COLOR)
        chip.pack(fill="x")
        chip.pack_propagate(False)
        value_lbl = ctk.CTkLabel(chip, text="—", font=ctk.CTkFont(size=13, weight="bold"),
                                 text_color=value_color)
        value_lbl.pack(expand=True)
        return value_lbl

    # ==========================================================================
    # ABA DE CONFIGURAÇÕES
    # ==========================================================================
    def _build_settings_tab(self, parent):
        scroll = ctk.CTkScrollableFrame(parent, fg_color="transparent",
                                        scrollbar_button_color=ACCENT_PRIMARY,
                                        scrollbar_button_hover_color=ACCENT_PRIMARY_HOVER)
        scroll.pack(fill="both", expand=True, padx=PAD_XS, pady=PAD_XS)

        # Resolução
        self._section_header(scroll, "Resolução da Tela", "Necessário para calcular o centro da mira")
        rc = self._card(scroll)
        ri = ctk.CTkFrame(rc, fg_color="transparent")
        ri.pack(fill="x", padx=PAD_LG, pady=(PAD_MD, PAD_SM))
        ri.columnconfigure(1, weight=1)
        ri.columnconfigure(3, weight=1)

        ctk.CTkLabel(ri, text="Largura", font=ctk.CTkFont(size=12),
                     text_color=TEXT_SECONDARY).grid(row=0, column=0, padx=(0, PAD_SM), sticky="w")
        self.setting_vars["SCREEN_WIDTH"] = ctk.StringVar(value=str(config.SCREEN_WIDTH))
        ctk.CTkEntry(ri, textvariable=self.setting_vars["SCREEN_WIDTH"],
                     fg_color=BG_INPUT, border_color=BORDER_COLOR_STRONG, text_color=TEXT_PRIMARY,
                     font=ctk.CTkFont(size=13), corner_radius=8, height=38, width=120
                     ).grid(row=0, column=1, padx=(0, PAD_LG), sticky="w")

        ctk.CTkLabel(ri, text="Altura", font=ctk.CTkFont(size=12),
                     text_color=TEXT_SECONDARY).grid(row=0, column=2, padx=(0, PAD_SM), sticky="w")
        self.setting_vars["SCREEN_HEIGHT"] = ctk.StringVar(value=str(config.SCREEN_HEIGHT))
        ctk.CTkEntry(ri, textvariable=self.setting_vars["SCREEN_HEIGHT"],
                     fg_color=BG_INPUT, border_color=BORDER_COLOR_STRONG, text_color=TEXT_PRIMARY,
                     font=ctk.CTkFont(size=13), corner_radius=8, height=38, width=120
                     ).grid(row=0, column=3, sticky="w")

        rb = ctk.CTkFrame(rc, fg_color="transparent")
        rb.pack(fill="x", padx=PAD_LG, pady=(PAD_SM, PAD_MD))
        ctk.CTkButton(rb, text="🖥  Detectar automaticamente", width=196, height=30, corner_radius=6,
                      font=ctk.CTkFont(size=11, weight="bold"), fg_color=ACCENT_SECONDARY,
                      hover_color="#0891b2", text_color="#ffffff",
                      command=self._detect_resolution).pack(side="left", padx=(0, PAD_SM))
        for label, w, h in [("1920×1080", 1920, 1080), ("2560×1440", 2560, 1440), ("1366×768", 1366, 768)]:
            ctk.CTkButton(rb, text=label, width=104, height=30, corner_radius=6,
                          font=ctk.CTkFont(size=11), fg_color=BG_INPUT, hover_color=ACCENT_PRIMARY,
                          text_color=TEXT_SECONDARY, border_width=1, border_color=BORDER_COLOR_STRONG,
                          command=lambda _w=w, _h=h: self._set_res(_w, _h)).pack(side="left", padx=(0, PAD_SM))

        # --- Inversão de Analógicos ---
        self._section_header(scroll, "Inversão de Eixos dos Analógicos", "Configure caso o seu boneco ou mira andem ao contrário")
        inv_card = self._card(scroll)
        inv_inner = ctk.CTkFrame(inv_card, fg_color="transparent")
        inv_inner.pack(fill="x", padx=PAD_LG, pady=PAD_MD)
        inv_inner.columnconfigure(0, weight=1)
        inv_inner.columnconfigure(1, weight=1)

        # Analógico Esquerdo (WASD)
        left_inv_frame = ctk.CTkFrame(inv_inner, fg_color=BG_INPUT, corner_radius=8)
        left_inv_frame.grid(row=0, column=0, sticky="nsew", padx=(0, PAD_SM))
        left_inv_inner = ctk.CTkFrame(left_inv_frame, fg_color="transparent")
        left_inv_inner.pack(fill="both", expand=True, padx=PAD_MD, pady=PAD_SM)
        ctk.CTkLabel(left_inv_inner, text="Analógico Esquerdo (WASD)", font=ctk.CTkFont(size=12, weight="bold"), text_color=TEXT_PRIMARY).pack(anchor="w", pady=(0, 6))

        self.inv_lx_var = tk.BooleanVar(value=config.CONTROLLER_LAYOUT.get("INVERT_LX", False))
        ctk.CTkCheckBox(left_inv_inner, text="Inverter Horizontal (X)", variable=self.inv_lx_var, font=ctk.CTkFont(size=11), text_color=TEXT_SECONDARY, fg_color=ACCENT_PRIMARY).pack(anchor="w", pady=3)

        self.inv_ly_var = tk.BooleanVar(value=config.CONTROLLER_LAYOUT.get("INVERT_LY", True))
        ctk.CTkCheckBox(left_inv_inner, text="Inverter Vertical (Y)", variable=self.inv_ly_var, font=ctk.CTkFont(size=11), text_color=TEXT_SECONDARY, fg_color=ACCENT_PRIMARY).pack(anchor="w", pady=3)

        # Analógico Direito (Mira)
        right_inv_frame = ctk.CTkFrame(inv_inner, fg_color=BG_INPUT, corner_radius=8)
        right_inv_frame.grid(row=0, column=1, sticky="nsew", padx=(PAD_SM, 0))
        right_inv_inner = ctk.CTkFrame(right_inv_frame, fg_color="transparent")
        right_inv_inner.pack(fill="both", expand=True, padx=PAD_MD, pady=PAD_SM)
        ctk.CTkLabel(right_inv_inner, text="Analógico Direito (Mira)", font=ctk.CTkFont(size=12, weight="bold"), text_color=TEXT_PRIMARY).pack(anchor="w", pady=(0, 6))

        self.inv_rx_var = tk.BooleanVar(value=config.CONTROLLER_LAYOUT.get("INVERT_RX", False))
        ctk.CTkCheckBox(right_inv_inner, text="Inverter Horizontal (X)", variable=self.inv_rx_var, font=ctk.CTkFont(size=11), text_color=TEXT_SECONDARY, fg_color=ACCENT_PRIMARY).pack(anchor="w", pady=3)

        self.inv_ry_var = tk.BooleanVar(value=config.CONTROLLER_LAYOUT.get("INVERT_RY", True))
        ctk.CTkCheckBox(right_inv_inner, text="Inverter Vertical (Y)", variable=self.inv_ry_var, font=ctk.CTkFont(size=11), text_color=TEXT_SECONDARY, fg_color=ACCENT_PRIMARY).pack(anchor="w", pady=3)

        # Mira
        self._section_header(scroll, "Configurações da Mira", "Raio do círculo de mira e retorno elástico ao centro")
        ac = self._card(scroll)
        ai = ctk.CTkFrame(ac, fg_color="transparent")
        ai.pack(fill="x", padx=PAD_LG, pady=PAD_MD)
        ctk.CTkLabel(ai, text="Raio da Mira (pixels)", font=ctk.CTkFont(size=12),
                     text_color=TEXT_SECONDARY).pack(anchor="w")
        sf = ctk.CTkFrame(ai, fg_color="transparent")
        sf.pack(fill="x", pady=(6, 0))
        self.aim_lbl = ctk.CTkLabel(sf, text=str(config.AIM_RADIUS), width=54,
                                    font=ctk.CTkFont(size=18, weight="bold"),
                                    text_color=ACCENT_SECONDARY)
        self.aim_lbl.pack(side="right", padx=(PAD_SM, 0))
        self.aim_slider = ctk.CTkSlider(sf, from_=50, to=600, number_of_steps=55,
                                        progress_color=ACCENT_PRIMARY, button_color=ACCENT_SECONDARY,
                                        button_hover_color="#22d3ee", fg_color=BG_INPUT,
                                        command=lambda v: self.aim_lbl.configure(text=str(int(v))))
        self.aim_slider.set(config.AIM_RADIUS)
        self.aim_slider.pack(fill="x", side="left", expand=True)

        ctk.CTkFrame(ai, fg_color=BORDER_COLOR, height=1).pack(fill="x", pady=PAD_MD)

        # Retorno Elástico ao Centro (animação ao soltar o analógico direito)
        ctk.CTkLabel(ai, text="Retorno Elástico ao Centro (ms)", font=ctk.CTkFont(size=12),
                     text_color=TEXT_SECONDARY).pack(anchor="w")
        rf = ctk.CTkFrame(ai, fg_color="transparent")
        rf.pack(fill="x", pady=(6, 0))
        self.return_lbl = ctk.CTkLabel(rf, text=str(config.AIM_RETURN_MS), width=54,
                                       font=ctk.CTkFont(size=18, weight="bold"),
                                       text_color=ACCENT_SECONDARY)
        self.return_lbl.pack(side="right", padx=(PAD_SM, 0))
        self.return_slider = ctk.CTkSlider(rf, from_=0, to=300, number_of_steps=30,
                                           progress_color=ACCENT_PRIMARY, button_color=ACCENT_SECONDARY,
                                           button_hover_color="#22d3ee", fg_color=BG_INPUT,
                                           command=lambda v: self.return_lbl.configure(text=str(int(v))))
        self.return_slider.set(config.AIM_RETURN_MS)
        self.return_slider.pack(fill="x", side="left", expand=True)

        # Deadzone
        self._section_header(scroll, "Zona Morta do Analógico", "Ignora movimentos leves para evitar drift")
        dc = self._card(scroll)
        di = ctk.CTkFrame(dc, fg_color="transparent")
        di.pack(fill="x", padx=PAD_LG, pady=PAD_MD)
        df = ctk.CTkFrame(di, fg_color="transparent")
        df.pack(fill="x")
        self.dz_lbl = ctk.CTkLabel(df, text=f"{config.DEADZONE:.2f}", width=54,
                                   font=ctk.CTkFont(size=18, weight="bold"),
                                   text_color=ACCENT_SECONDARY)
        self.dz_lbl.pack(side="right", padx=(PAD_SM, 0))
        self.dz_slider = ctk.CTkSlider(df, from_=0.05, to=0.5, number_of_steps=45,
                                       progress_color=ACCENT_PRIMARY, button_color=ACCENT_SECONDARY,
                                       button_hover_color="#22d3ee", fg_color=BG_INPUT,
                                       command=lambda v: self.dz_lbl.configure(text=f"{round(v,2):.2f}"))
        self.dz_slider.set(config.DEADZONE)
        self.dz_slider.pack(fill="x", side="left", expand=True)

        # Dicas
        tf = ctk.CTkFrame(scroll, fg_color=BG_CARD, corner_radius=12,
                          border_width=1, border_color=ACCENT_PRIMARY)
        tf.pack(fill="x", padx=PAD_XS, pady=(PAD_LG, PAD_SM))
        ti = ctk.CTkFrame(tf, fg_color="transparent")
        ti.pack(fill="x", padx=PAD_LG, pady=PAD_MD)
        ctk.CTkLabel(ti, text="💡  Dicas", font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=ACCENT_PRIMARY).pack(anchor="w")
        ctk.CTkLabel(ti, text="•  Ação 'Ctrl' serve para upar habilidades (segure o botão + botão da habilidade)\n"
                              "•  Ação 'R-Click' simula o clique direito (Ataque Básico / Movimentação)\n"
                              "•  Analógico esquerdo = Movimentação (WASD)\n"
                              "•  Analógico direito = Mira (mouse proporcional com auto-retorno ao centro)\n"
                              "•  Retorno Elástico: ao soltar o analógico direito, a mira volta suavemente ao\n"
                              "    centro no tempo configurado (0 ms = volta instantânea, como antes)\n"
                              "•  Se a mira ou andar estiverem invertidos, ajuste acima nas inversões de analógico",
                     font=ctk.CTkFont(size=12), text_color=TEXT_SECONDARY,
                     anchor="w", justify="left").pack(fill="x", pady=(8, 0))

        ctk.CTkButton(scroll, text="💾  Salvar Configurações", height=46, corner_radius=10,
                      font=ctk.CTkFont(size=14, weight="bold"),
                      fg_color=ACCENT_PRIMARY, hover_color=ACCENT_PRIMARY_HOVER,
                      text_color="#ffffff", command=self._save_config).pack(pady=(PAD_LG, PAD_LG))

    # ==========================================================================
    # STATUS BAR
    # ==========================================================================
    def _build_status_bar(self):
        sb = ctk.CTkFrame(self, fg_color=BG_CARD, corner_radius=0, height=40)
        sb.pack(fill="x", side="bottom")
        sb.pack_propagate(False)
        ctk.CTkFrame(self, fg_color=BORDER_COLOR_STRONG, height=1,
                     corner_radius=0).pack(fill="x", side="bottom")
        inner = ctk.CTkFrame(sb, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=PAD_LG)
        self.status_dot = ctk.CTkLabel(inner, text="●", font=ctk.CTkFont(size=10),
                                       text_color=TEXT_MUTED, width=16)
        self.status_dot.pack(side="left")
        self.status_label = ctk.CTkLabel(inner, text="Parado",
                                         font=ctk.CTkFont(size=11, weight="bold"), text_color=TEXT_MUTED)
        self.status_label.pack(side="left", padx=(4, 0))
        ctk.CTkLabel(inner, text=f"Config: {os.path.basename(config.CONFIG_FILE)}",
                     font=ctk.CTkFont(size=11), text_color=TEXT_MUTED).pack(side="right")

    # ==========================================================================
    # HELPERS
    # ==========================================================================
    def _section_header(self, parent, title, subtitle=""):
        f = ctk.CTkFrame(parent, fg_color="transparent")
        f.pack(fill="x", padx=PAD_XS, pady=(PAD_LG, PAD_SM))
        kicker = ctk.CTkFrame(f, fg_color="transparent")
        kicker.pack(fill="x")
        ctk.CTkFrame(kicker, fg_color=ACCENT_PRIMARY, width=4, height=18,
                     corner_radius=2).pack(side="left", padx=(0, 8))
        ctk.CTkLabel(kicker, text=title, font=ctk.CTkFont(size=16, weight="bold"),
                     text_color=TEXT_PRIMARY, anchor="w").pack(side="left", fill="x")
        if subtitle:
            ctk.CTkLabel(f, text=subtitle, font=ctk.CTkFont(size=11),
                         text_color=TEXT_MUTED, anchor="w").pack(fill="x", padx=(12, 0), pady=(3, 0))

    def _card(self, parent):
        c = ctk.CTkFrame(parent, fg_color=BG_CARD, corner_radius=12,
                         border_width=1, border_color=BORDER_COLOR)
        c.pack(fill="x", padx=PAD_XS, pady=(0, PAD_SM))
        return c

    def _set_res(self, w, h):
        self.setting_vars["SCREEN_WIDTH"].set(str(w))
        self.setting_vars["SCREEN_HEIGHT"].set(str(h))

    def _detect_resolution(self):
        """Preenche os campos de resolução com a resolução real detectada via
        Win32 GetSystemMetrics, em vez de depender só de presets/digitação
        manual (fonte do próprio user_config.json ter uma resolução digitada
        errado, 1360x768, que não bate com nenhum preset do app)."""
        res = _get_system_resolution()
        if res:
            self._set_res(*res)
            self._flash_status(f"🖥  Resolução detectada: {res[0]}×{res[1]}", ACCENT_SUCCESS)
        else:
            self._flash_status("⚠️  Não foi possível detectar a resolução automaticamente", ACCENT_WARNING)

    def _flash_status(self, text, color):
        self.status_label.configure(text=text, text_color=color)
        self.status_dot.configure(text_color=color)

    # ==========================================================================
    # CALIBRAÇÃO
    # ==========================================================================
    def _open_calibration(self):
        """Abre o assistente de calibração (bloqueado enquanto o controle
        está rodando; reentrante-seguro — um duplo-clique não abre dois
        assistentes concorrentes lendo o mesmo gamepad)."""
        if self.detecting:
            self._stop_detection()
        if self.is_running:
            self._flash_status("⚠️  Pare o script antes de calibrar", ACCENT_WARNING)
            return
        if self._calibration_wizard is not None:
            try:
                if self._calibration_wizard.winfo_exists():
                    self._calibration_wizard.lift()
                    self._calibration_wizard.focus_force()
                    return
            except Exception:
                pass
        self._calibration_wizard = CalibrationWizard(self)

    # ==========================================================================
    # DETECÇÃO (usa mapas dinâmicos)
    # ==========================================================================
    def _toggle_detection(self):
        """Liga/desliga o painel de detecção ao vivo de input do gamepad."""
        if self.detecting:
            self._stop_detection()
        else:
            self._start_detection()

    def _start_detection(self):
        if self.is_running:
            self._flash_status("⚠️  Pare o script antes de detectar", ACCENT_WARNING)
            return
        self.detecting = True
        # Event NOVO a cada início (não reutilizar+limpar o mesmo): um
        # _detection_loop órfão da execução anterior — ainda bloqueado em
        # get_gamepad() segurando o lock — continua observando o Event ANTIGO
        # (já setado) e encerra, em vez de ressuscitar ao ver um flag "limpo".
        self.detect_stop = threading.Event()
        self.detect_btn.configure(text="⏹  Parar", fg_color=ACCENT_DANGER, hover_color="#dc2626")
        self._flash_status("🔍  Detectando inputs...", ACCENT_SECONDARY)
        threading.Thread(target=self._detection_loop, daemon=True).start()
        self._process_detection_queue()

    def _stop_detection(self):
        self.detecting = False
        self.detect_stop.set()
        self.detect_btn.configure(text="🔍  Detectar", fg_color=ACCENT_PRIMARY,
                                  hover_color=ACCENT_PRIMARY_HOVER)
        self._flash_status("Detecção parada", TEXT_MUTED)
        for name in self.ctrl_buttons:
            self._dim_btn(name)
        self.left_stick.update_position(0, 0)
        self.right_stick.update_position(0, 0)

    def _detection_loop(self):
        # Captura o Event local: _start_detection cria um Event NOVO a cada
        # início (para não ressuscitar um leitor órfão da execução anterior),
        # então este laço deve observar o Event com que começou, não o
        # self.detect_stop que pode já ter sido trocado por baixo dele.
        stop = self.detect_stop
        try:
            from inputs import get_gamepad
        except ImportError:
            self.event_queue.put(("__error__", "Biblioteca 'inputs' não encontrada"))
            return

        # Mesmo lock global usado pelo CalibrationWizard — evita duas threads
        # lendo o gamepad ao mesmo tempo (ex.: calibração aberta logo após
        # parar a detecção, antes da thread anterior sair do get_gamepad()
        # bloqueante). Espera o lock em vez de exibir erro fatal após 3s: o
        # leitor anterior o solta assim que seu get_gamepad() retorna.
        # Desistimos apenas se a detecção for parada antes de conseguir o lock.
        while not stop.is_set():
            if _gamepad_reader_lock.acquire(timeout=0.5):
                break
        else:
            return
        try:
            while not stop.is_set():
                try:
                    events = get_gamepad()
                    for ev in events:
                        if ev.ev_type == "Sync":
                            continue
                        if stop.is_set():
                            break
                        self.event_queue.put(ev)
                except Exception as e:
                    self.event_queue.put(("__error__", str(e)))
                    break
        finally:
            _gamepad_reader_lock.release()

    def _process_detection_queue(self):
        try:
            for _ in range(50):
                event = self.event_queue.get_nowait()
                if isinstance(event, tuple) and event[0] == "__error__":
                    self._flash_status(f"❌  {event[1]}", ACCENT_DANGER)
                    self._stop_detection()
                    return
                self._handle_event(event)
        except queue.Empty:
            pass
        if self.detecting:
            self.after(12, self._process_detection_queue)

    def _handle_event(self, event):
        code = event.code
        state = event.state

        # Botões
        if event.ev_type == "Key" and code in self._btn_code_map:
            btn = self._btn_code_map[code]
            if state == 1:
                self._glow_btn(btn)
                mapped = config.MAPPING.get(btn, "?")
                self._update_det(code, BUTTON_LABELS.get(btn, btn), mapped.upper(), "● Pressionado")
            else:
                self._dim_btn(btn)
                self._update_det(code, BUTTON_LABELS.get(btn, btn), "", "○ Solto")

        # D-Pad Y
        elif code == self._dpad_y_code:
            self._dim_btn("DPAD_UP")
            self._dim_btn("DPAD_DOWN")
            if state == self._dpad_up_val:
                self._glow_btn("DPAD_UP")
                m = config.MAPPING.get("DPAD_UP", "?")
                self._update_det(code, "↑ D-Pad Cima", m.upper(), "● Pressionado")
            elif state == self._dpad_down_val:
                self._glow_btn("DPAD_DOWN")
                m = config.MAPPING.get("DPAD_DOWN", "?")
                self._update_det(code, "↓ D-Pad Baixo", m.upper(), "● Pressionado")
            else:
                self._update_det(code, "D-Pad Vertical", "", "○ Solto")

        # D-Pad X
        elif code == self._dpad_x_code:
            self._dim_btn("DPAD_LEFT")
            self._dim_btn("DPAD_RIGHT")
            if state == self._dpad_left_val:
                self._glow_btn("DPAD_LEFT")
                m = config.MAPPING.get("DPAD_LEFT", "?")
                self._update_det(code, "← D-Pad Esquerda", m.upper(), "● Pressionado")
            elif state == self._dpad_right_val:
                self._glow_btn("DPAD_RIGHT")
                m = config.MAPPING.get("DPAD_RIGHT", "?")
                self._update_det(code, "→ D-Pad Direita", m.upper(), "● Pressionado")
            else:
                self._update_det(code, "D-Pad Horizontal", "", "○ Solto")

        # L2
        elif code == self._l2_code:
            pressed = state > 128 if 0 <= state <= 255 else abs(state) > 16000
            if pressed:
                self._glow_btn("L2")
                m = config.MAPPING.get("L2", "?")
                self._update_det(code, "L2 / LT", m.upper(), "● Pressionado")
            else:
                self._dim_btn("L2")
                self._update_det(code, "L2 / LT", "", "○ Solto")

        # R2
        elif code == self._r2_code:
            pressed = state > 128 if 0 <= state <= 255 else abs(state) > 16000
            if pressed:
                self._glow_btn("R2")
                m = config.MAPPING.get("R2", "?")
                self._update_det(code, "R2 / RT", m.upper(), "● Pressionado")
            else:
                self._dim_btn("R2")
                self._update_det(code, "R2 / RT", "", "○ Solto")

        # Analógico Esquerdo
        elif code == self._axis_lx:
            v = state / 32768.0
            if self._invert_lx: v = -v
            self.analog_state["lx"] = v
            self.left_stick.update_position(self.analog_state["lx"], self.analog_state["ly"])
        elif code == self._axis_ly:
            v = state / 32768.0
            if self._invert_ly: v = -v
            self.analog_state["ly"] = v
            self.left_stick.update_position(self.analog_state["lx"], self.analog_state["ly"])

        # Analógico Direito
        elif code == self._axis_rx:
            v = state / 32768.0
            if self._invert_rx: v = -v
            self.analog_state["rx"] = v
            self.right_stick.update_position(self.analog_state["rx"], self.analog_state["ry"])
        elif code == self._axis_ry:
            v = state / 32768.0
            if self._invert_ry: v = -v
            self.analog_state["ry"] = v
            self.right_stick.update_position(self.analog_state["rx"], self.analog_state["ry"])

    def _glow_btn(self, name):
        if name in self.ctrl_buttons:
            b = self.ctrl_buttons[name]
            b["frame"].configure(fg_color=BG_GLOW, border_color=ACCENT_PRIMARY)
            b["sym_label"].configure(text_color="#ffffff")

    def _dim_btn(self, name):
        if name in self.ctrl_buttons:
            b = self.ctrl_buttons[name]
            b["frame"].configure(fg_color=BG_INPUT, border_color=BORDER_COLOR)
            b["sym_label"].configure(text_color=TEXT_PRIMARY)

    def _update_det(self, code, button, key, state_text):
        self.det_code.configure(text=code)
        self.det_button.configure(text=button)
        self.det_key.configure(text=key or "—")
        self.det_state.configure(text=state_text,
                                 text_color=ACCENT_SUCCESS if "●" in state_text else TEXT_MUTED)
        self.detection_card.configure(
            border_color=ACCENT_PRIMARY if "●" in state_text else BORDER_COLOR)

    # ==========================================================================
    # POPUP DE REMAP (DO DIAGRAMA DO CONTROLE)
    # ==========================================================================
    def _show_remap_popup(self, btn_name):
        if self.is_running:
            self._flash_status("⚠️  Pare o script antes de remapear", ACCENT_WARNING)
            return
        popup = ctk.CTkToplevel(self)
        popup.title("Remapear Botão")
        popup.geometry("340x240")
        popup.configure(fg_color=BG_DARK)
        popup.resizable(False, False)
        popup.transient(self)
        popup.grab_set()
        popup.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() // 2) - 170
        y = self.winfo_y() + (self.winfo_height() // 2) - 120
        popup.geometry(f"+{x}+{y}")

        card = ctk.CTkFrame(popup, fg_color=BG_CARD, corner_radius=12)
        card.pack(fill="both", expand=True, padx=12, pady=12)
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=16, pady=16)

        ctk.CTkLabel(inner, text=BUTTON_LABELS.get(btn_name, btn_name),
                     font=ctk.CTkFont(size=16, weight="bold"),
                     text_color=TEXT_PRIMARY).pack(anchor="w")
        ctk.CTkLabel(inner, text=BUTTON_DESCRIPTIONS.get(btn_name, ""),
                     font=ctk.CTkFont(size=11),
                     text_color=TEXT_MUTED).pack(anchor="w", pady=(0, 12))
        ctk.CTkLabel(inner, text="Nova tecla/ação:", font=ctk.CTkFont(size=12),
                     text_color=TEXT_SECONDARY).pack(anchor="w", pady=(0, 4))

        var = ctk.StringVar(value=config.MAPPING.get(btn_name, "—"))
        options = ["—", "Ctrl", "R-Click", "L-Click"] + AVAILABLE_KEYS
        ctk.CTkOptionMenu(inner, variable=var, values=options,
                          font=ctk.CTkFont(size=13, weight="bold"),
                          fg_color=BG_INPUT, button_color=ACCENT_PRIMARY,
                          button_hover_color=ACCENT_PRIMARY_HOVER,
                          dropdown_fg_color=BG_CARD, dropdown_hover_color=ACCENT_PRIMARY,
                          dropdown_text_color=TEXT_PRIMARY, text_color=ACCENT_SECONDARY,
                          corner_radius=8, width=200, height=34).pack(fill="x", pady=(0, 16))

        bf = ctk.CTkFrame(inner, fg_color="transparent")
        bf.pack(fill="x")

        def apply():
            selected = var.get()
            new_value = "" if selected == "—" else selected
            # Limpa qualquer outro botão já associado a essa mesma tecla/ação
            # antes de aplicar, espelhando o dedup de _show_hud_remap_popup —
            # sem isso, dois botões físicos podiam ficar mapeados para a
            # mesma tecla e o runtime (main.py) via um deles ser solto
            # prematuramente enquanto o outro ainda estava pressionado.
            if new_value:
                for b, k in list(config.MAPPING.items()):
                    if b != btn_name and k == new_value:
                        config.MAPPING[b] = ""
            config.MAPPING[btn_name] = new_value
            self._update_all_mappings_ui()
            popup.destroy()
            self._flash_status(f"✅  {BUTTON_LABELS.get(btn_name, btn_name)} → {selected.upper()}",
                               ACCENT_SUCCESS)

        ctk.CTkButton(bf, text="✓  Aplicar", width=120, height=34, corner_radius=8,
                      font=ctk.CTkFont(size=13, weight="bold"),
                      fg_color=ACCENT_SUCCESS, hover_color="#0d9668", text_color="#ffffff",
                      command=apply).pack(side="left", padx=(0, 8))
        ctk.CTkButton(bf, text="Cancelar", width=100, height=34, corner_radius=8,
                      font=ctk.CTkFont(size=13), fg_color=BG_INPUT,
                      hover_color=BG_CARD_HOVER, text_color=TEXT_SECONDARY,
                      border_width=1, border_color=BORDER_COLOR,
                      command=popup.destroy).pack(side="left")

    # ==========================================================================
    # SALVAR CONFIGURAÇÃO
    # ==========================================================================
    def _save_config(self):
        """Lê os widgets da aba Configurações + o estado atual de config.MAPPING/
        CONTROLLER_LAYOUT e persiste tudo em user_config.json."""
        try:
            sw = int(self.setting_vars["SCREEN_WIDTH"].get())
            sh = int(self.setting_vars["SCREEN_HEIGHT"].get())
        except (ValueError, KeyError):
            sw, sh = config.SCREEN_WIDTH, config.SCREEN_HEIGHT

        # Coletar inversões e salvar na estrutura do layout
        config.CONTROLLER_LAYOUT["INVERT_LX"] = self.inv_lx_var.get()
        config.CONTROLLER_LAYOUT["INVERT_LY"] = self.inv_ly_var.get()
        config.CONTROLLER_LAYOUT["INVERT_RX"] = self.inv_rx_var.get()
        config.CONTROLLER_LAYOUT["INVERT_RY"] = self.inv_ry_var.get()

        data = {
            "SCREEN_WIDTH": sw, "SCREEN_HEIGHT": sh,
            "AIM_RADIUS": int(self.aim_slider.get()),
            "DEADZONE": round(self.dz_slider.get(), 2),
            "AIM_RETURN_MS": int(self.return_slider.get()),
            "POLL_RATE": config.POLL_RATE,
            "MAPPING": dict(config.MAPPING),
            # MODIFIER_BTN/ATTACK_BTN propositalmente não são incluídos aqui:
            # nenhum widget da GUI os altera e nenhum consumidor (main.py,
            # wasd_logic.py, aim_math.py) os lê — são um ajuste "morto" que
            # só ficava sendo lido/regravado sem efeito nenhum. Omitir do
            # round-trip não muda comportamento (config.apply_config/
            # load_config já usam DEFAULTS como fallback quando a chave não
            # está presente no JSON).
            "CONTROLLER_LAYOUT": dict(config.CONTROLLER_LAYOUT),
        }
        config.apply_config(data)
        config.save_config()
        self._flash_status("✅  Configurações salvas!", ACCENT_SUCCESS)

    def _restore_wasd_defaults(self):
        """Restaura o mapeamento de botões para o padrão LoL WASD.

        Nota: config.save_config() chamado sem argumentos serializa TODA a
        configuração atual em memória (resolução, mira, deadzone, layout do
        controle etc.), não apenas o mapeamento — então este botão, apesar
        do nome, sempre grava o estado completo em disco imediatamente.
        """
        if self.is_running:
            self._flash_status("⚠️  Pare o script antes de remapear", ACCENT_WARNING)
            return
        config.MAPPING = dict(config.DEFAULTS["MAPPING"])
        config.save_config()
        self._update_all_mappings_ui()
        self._flash_status("🔄  Padrão WASD do LoL restaurado!", ACCENT_SUCCESS)

    # ==========================================================================
    # START / STOP SCRIPT
    # ==========================================================================
    def _toggle_script(self):
        if self.is_running:
            self._stop_script()
        else:
            self._start_script()

    def _start_script(self):
        """Salva a config atual e inicia o loop de controle (main.main) em
        uma thread de segundo plano."""
        if self.detecting:
            self._stop_detection()
        self._save_config()
        # Espera a execução anterior terminar seu cleanup() (soltar
        # WASD/Ctrl/mouse) antes de começar a próxima, para as duas não se
        # sobreporem soltando/segurando input ao mesmo tempo.
        if self._controller_thread is not None and self._controller_thread.is_alive():
            self._controller_thread.join(timeout=1.5)
        # Event NOVO a cada início (não reutilizar+limpar o mesmo): um leitor de
        # controle de main.py da execução anterior pode ter sobrevivido ao join
        # (bloqueado dentro de get_gamepad() esperando um último evento). Se
        # limpássemos o mesmo Event que ele ainda observa, ele voltaria a
        # injetar input em paralelo com o novo leitor. Com um Event novo, o
        # leitor órfão continua vendo o Event ANTIGO (ainda setado) e encerra.
        stop_event = threading.Event()
        self.stop_event = stop_event
        self.is_running = True
        self.start_btn.configure(text="⏹  PARAR", fg_color=ACCENT_DANGER, hover_color="#dc2626")
        self.detect_btn.configure(state="disabled", fg_color=BG_INPUT)
        # Sem privilégio de admin, o UIPI do Windows descarta silenciosamente o
        # input sintético quando o LoL/Vanguard roda elevado — o usuário da GUI
        # não vê o aviso que main.py só imprime no stdout. Surface aqui.
        try:
            is_admin = bool(ctypes.windll.shell32.IsUserAnAdmin())
        except Exception:
            is_admin = True
        if is_admin:
            self._flash_status("▶  Rodando — controle ativo", ACCENT_SUCCESS)
        else:
            self._flash_status(
                "⚠️  Rodando SEM admin — rode como Administrador se os comandos não funcionarem no jogo",
                ACCENT_WARNING)
        self._controller_thread = threading.Thread(
            target=self._run_controller, args=(stop_event,), daemon=True)
        self._controller_thread.start()

    def _stop_script(self):
        """Sinaliza para main.main() parar (via stop_event) e restaura a UI.
        Não bloqueia esperando a thread terminar — quem precisa disso (ex.:
        fechar a janela) deve dar join() em self._controller_thread."""
        self.stop_event.set()
        self.is_running = False
        self.start_btn.configure(text="▶  INICIAR", fg_color=ACCENT_SUCCESS, hover_color="#0d9668")
        self._flash_status("Parado", TEXT_MUTED)
        self.detect_btn.configure(state="normal", fg_color=ACCENT_PRIMARY)

    def _run_controller(self, stop_event):
        # Não usar importlib.reload(config)/reload(main) aqui: main.main()
        # já chama config.load_config() por conta própria a cada execução, e
        # reload() re-executa o módulo do zero em memória compartilhada —
        # nesse meio-tempo ele reseta config.MAPPING/CONTROLLER_LAYOUT/etc.
        # para os hardcoded DEFAULTS antes de load_config() re-ler o arquivo,
        # o que é uma corrida de dados se a thread da GUI ler config.* nesse
        # instante (ex.: popups de remap, callbacks de detecção). reload()
        # também não é thread-safe e não recarrega módulos importados
        # transitivamente (aim_math/wasd_logic).
        try:
            import main
            main.main(stop_event=stop_event)
        except Exception as e:
            print(f"[GUI] Erro: {e}")
        finally:
            self.after(0, lambda: self._on_controller_exit(stop_event))

    def _on_controller_exit(self, stop_event):
        """Restaura a UI quando main.main() termina por conta própria (ex.:
        controle desconectado). Só age se ESTA execução ainda for a atual —
        uma execução antiga que só terminou depois de o usuário já ter
        iniciado uma nova não deve parar a nova (seu stop_event não é mais o
        vigente)."""
        if stop_event is not self.stop_event:
            return
        if self.is_running:
            self._stop_script()

    def _on_close(self):
        if self.is_running:
            self._stop_script()
            # Threads daemon são mortas abruptamente quando o interpretador
            # sai, sem chance de rodar o cleanup() (soltar WASD/Ctrl/mouse)
            # de main.py — espera brevemente a thread do controle terminar
            # antes de destruir a janela e deixar o processo sair.
            if self._controller_thread is not None:
                self._controller_thread.join(timeout=1.5)
        if self.detecting:
            self._stop_detection()
        # Fecha o assistente de calibração aberto para que SEU próprio cleanup
        # rode (seta detect_stop, cancela os jobs after() pendentes, solta o
        # grab e libera o _gamepad_reader_lock) em vez de depender da
        # destruição implícita do filho enquanto a thread leitora ainda segura
        # o lock bloqueada em get_gamepad().
        wiz = self._calibration_wizard
        if wiz is not None:
            try:
                if wiz.winfo_exists():
                    wiz._cancel()
            except Exception:
                pass
        self.destroy()


# ==============================================================================
# ENTRY POINT
# ==============================================================================
if __name__ == "__main__":
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("dark-blue")
    app = LoLControllerApp()
    app.mainloop()
