# ==============================================================================
# CONFIGURAÇÕES DO CONTROLE DE LEAGUE OF LEGENDS
# ==============================================================================
import json
import os

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "user_config.json")

# --- Layout padrão XInput (como o Windows reconhece a maioria dos controles) ---
DEFAULT_CONTROLLER_LAYOUT = {
    # Botões de face e ombros → event code do 'inputs'
    "SQUARE": "BTN_WEST",
    "TRIANGLE": "BTN_NORTH",
    "CIRCLE": "BTN_EAST",
    "CROSS": "BTN_SOUTH",
    "L1": "BTN_TL",
    "R1": "BTN_TR",
    # Novos botões
    "L3": "BTN_THUMBL",
    "R3": "BTN_THUMBR",
    "START": "BTN_START",
    "SELECT": "BTN_SELECT",
    # Gatilhos
    "L2": "ABS_Z",
    "R2": "ABS_RZ",
    # D-Pad
    "DPAD_Y_CODE": "ABS_HAT0Y",
    "DPAD_X_CODE": "ABS_HAT0X",
    "DPAD_UP_VAL": -1,
    "DPAD_DOWN_VAL": 1,
    "DPAD_LEFT_VAL": -1,
    "DPAD_RIGHT_VAL": 1,
    # Analógicos — eixos
    "AXIS_LX": "ABS_X",
    "AXIS_LY": "ABS_Y",
    "AXIS_RX": "ABS_RX",
    "AXIS_RY": "ABS_RY",
    # Inversão de eixos
    "INVERT_LX": False,
    "INVERT_LY": True,   # XInput padrão: cima é positivo, precisamos inverter
    "INVERT_RX": False,
    "INVERT_RY": True,
}

# --- Valores Padrão ---
DEFAULTS = {
    "SCREEN_WIDTH": 1920,
    "SCREEN_HEIGHT": 1080,
    "AIM_RADIUS": 300,
    "DEADZONE": 0.2,
    "POLL_RATE": 0.01,
    "MAPPING": {
        "SQUARE": "R-Click",  # Habilidade 1 (MB2 / Right Click no LoL WASD)
        "TRIANGLE": "shift",  # Habilidade 2 (LShift no LoL WASD)
        "CIRCLE": "e",        # Habilidade 3 (E no LoL WASD)
        "CROSS": "r",         # Habilidade 4 (R no LoL WASD)
        "L1": "q",            # Feitiço 1 (Q no LoL WASD)
        "R1": "f",            # Feitiço 2 (F no LoL WASD)
        "DPAD_UP": "1",
        "DPAD_RIGHT": "2",
        "DPAD_DOWN": "3",
        "DPAD_LEFT": "4",
        "L3": "p",            # Loja (P)
        "R3": "",             # Livre
        "START": "escape",
        "SELECT": "b",        # Recall (B)
        "L2": "Ctrl",         # Modificador
        "R2": "L-Click",      # Clique Esquerdo (para selecionar e comprar itens na Loja / Ataque Básico)
    },
    "MODIFIER_BTN": "L2",
    "ATTACK_BTN": "R2",
    "CONTROLLER_LAYOUT": dict(DEFAULT_CONTROLLER_LAYOUT),
}

# --- Variáveis ativas (usadas pelo script) ---
SCREEN_WIDTH = DEFAULTS["SCREEN_WIDTH"]
SCREEN_HEIGHT = DEFAULTS["SCREEN_HEIGHT"]
AIM_RADIUS = DEFAULTS["AIM_RADIUS"]
DEADZONE = DEFAULTS["DEADZONE"]
POLL_RATE = DEFAULTS["POLL_RATE"]
MAPPING = dict(DEFAULTS["MAPPING"])
MODIFIER_BTN = DEFAULTS["MODIFIER_BTN"]
ATTACK_BTN = DEFAULTS["ATTACK_BTN"]
CONTROLLER_LAYOUT = dict(DEFAULT_CONTROLLER_LAYOUT)


def load_config():
    """
    Carrega as configurações do user_config.json.
    Se o arquivo não existir, usa os valores padrão e cria o arquivo.
    """
    global SCREEN_WIDTH, SCREEN_HEIGHT, AIM_RADIUS, DEADZONE, POLL_RATE
    global MAPPING, MODIFIER_BTN, ATTACK_BTN, CONTROLLER_LAYOUT

    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            SCREEN_WIDTH = data.get("SCREEN_WIDTH", DEFAULTS["SCREEN_WIDTH"])
            SCREEN_HEIGHT = data.get("SCREEN_HEIGHT", DEFAULTS["SCREEN_HEIGHT"])
            AIM_RADIUS = data.get("AIM_RADIUS", DEFAULTS["AIM_RADIUS"])
            DEADZONE = data.get("DEADZONE", DEFAULTS["DEADZONE"])
            POLL_RATE = data.get("POLL_RATE", DEFAULTS["POLL_RATE"])
            
            # Carregar mapping fazendo merge com os defaults
            saved_mapping = data.get("MAPPING", {})
            MAPPING = dict(DEFAULTS["MAPPING"])
            MAPPING.update(saved_mapping)

            MODIFIER_BTN = data.get("MODIFIER_BTN", DEFAULTS["MODIFIER_BTN"])
            ATTACK_BTN = data.get("ATTACK_BTN", DEFAULTS["ATTACK_BTN"])
            
            # Carregar layout com merge dos defaults para campos faltantes
            saved_layout = data.get("CONTROLLER_LAYOUT", {})
            CONTROLLER_LAYOUT = dict(DEFAULT_CONTROLLER_LAYOUT)
            CONTROLLER_LAYOUT.update(saved_layout)
        except (json.JSONDecodeError, IOError):
            save_config(DEFAULTS)
    else:
        save_config(DEFAULTS)


def save_config(data=None):
    """Salva as configurações no user_config.json."""
    if data is None:
        data = get_current_config()
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


def get_current_config():
    """Retorna um dicionário com todas as configurações atuais."""
    return {
        "SCREEN_WIDTH": SCREEN_WIDTH,
        "SCREEN_HEIGHT": SCREEN_HEIGHT,
        "AIM_RADIUS": AIM_RADIUS,
        "DEADZONE": DEADZONE,
        "POLL_RATE": POLL_RATE,
        "MAPPING": dict(MAPPING),
        "MODIFIER_BTN": MODIFIER_BTN,
        "ATTACK_BTN": ATTACK_BTN,
        "CONTROLLER_LAYOUT": dict(CONTROLLER_LAYOUT),
    }


def apply_config(data):
    """Aplica um dicionário de configurações nas variáveis globais."""
    global SCREEN_WIDTH, SCREEN_HEIGHT, AIM_RADIUS, DEADZONE, POLL_RATE
    global MAPPING, MODIFIER_BTN, ATTACK_BTN, CONTROLLER_LAYOUT

    SCREEN_WIDTH = data.get("SCREEN_WIDTH", SCREEN_WIDTH)
    SCREEN_HEIGHT = data.get("SCREEN_HEIGHT", SCREEN_HEIGHT)
    AIM_RADIUS = data.get("AIM_RADIUS", AIM_RADIUS)
    DEADZONE = data.get("DEADZONE", DEADZONE)
    POLL_RATE = data.get("POLL_RATE", POLL_RATE)
    MAPPING = data.get("MAPPING", MAPPING)
    MODIFIER_BTN = data.get("MODIFIER_BTN", MODIFIER_BTN)
    ATTACK_BTN = data.get("ATTACK_BTN", ATTACK_BTN)
    if "CONTROLLER_LAYOUT" in data:
        layout = dict(DEFAULT_CONTROLLER_LAYOUT)
        layout.update(data["CONTROLLER_LAYOUT"])
        CONTROLLER_LAYOUT = layout


# Carregar configurações ao importar o módulo
load_config()
