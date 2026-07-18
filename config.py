# ==============================================================================
# CONFIGURAÇÕES DO CONTROLE DE LEAGUE OF LEGENDS
# ==============================================================================
import json
import logging
import os
import shutil

logger = logging.getLogger(__name__)

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
    # Duração (ms) da animação de retorno elástico da mira ao centro quando o
    # analógico direito é solto. 0 = teleporte instantâneo (comportamento
    # antigo). Ver aim_math.update_aim().
    "AIM_RETURN_MS": 120,
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


class AppConfig:
    """Fonte única de verdade para o estado de configuração da aplicação.

    Antes, cada valor de configuração (SCREEN_WIDTH, MAPPING, ...) era uma
    variável solta no nível do módulo, mutada diretamente por main.py,
    gui.py etc. Isso tornava difícil garantir que leitura/escrita ficassem
    consistentes entre si (ex.: carregar do disco, aplicar um dict parcial,
    serializar de volta) — cada operação reimplementava sua própria lógica
    de merge com os DEFAULTS.

    Esta classe concentra esse estado e a lógica de merge/serialização.
    As variáveis de módulo abaixo (SCREEN_WIDTH, MAPPING, CONTROLLER_LAYOUT,
    ...) continuam existindo e são mantidas em sincronia com a instância
    singleton (`_config`) por load_config()/save_config()/get_current_config()/
    apply_config(), que são a interface pública deste módulo e continuam
    funcionando exatamente como antes para quem já as importa
    (main.py, aim_math.py, wasd_logic.py, gui.py).
    """

    def __init__(self):
        self.reset_to_defaults()

    def reset_to_defaults(self):
        self.screen_width = DEFAULTS["SCREEN_WIDTH"]
        self.screen_height = DEFAULTS["SCREEN_HEIGHT"]
        self.aim_radius = DEFAULTS["AIM_RADIUS"]
        self.deadzone = DEFAULTS["DEADZONE"]
        self.aim_return_ms = DEFAULTS["AIM_RETURN_MS"]
        self.poll_rate = DEFAULTS["POLL_RATE"]
        self.mapping = dict(DEFAULTS["MAPPING"])
        self.modifier_btn = DEFAULTS["MODIFIER_BTN"]
        self.attack_btn = DEFAULTS["ATTACK_BTN"]
        self.controller_layout = dict(DEFAULT_CONTROLLER_LAYOUT)

    def load_from_disk(self):
        """Carrega o estado a partir de CONFIG_FILE, fazendo merge com os defaults.

        Se o arquivo não existir, cria um novo a partir dos DEFAULTS.
        Se o arquivo existir mas não puder ser lido/parseado (JSON corrompido,
        erro de IO), a leitura é tratada como uma falha *transiente*: o
        estado em memória não é tocado e o arquivo em disco não é
        sobrescrito, apenas uma cópia de segurança é feita ao lado dele.
        Isso evita destruir a calibração/mapeamento salvos do usuário por
        causa de um glitch de leitura pontual (ex.: arquivo sendo lido no
        meio de uma escrita concorrente feita pela GUI).
        """
        if not os.path.exists(CONFIG_FILE):
            self.reset_to_defaults()
            self.save_to_disk()
            return True

        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, IOError, OSError) as exc:
            logger.warning(
                "Falha ao ler %s (%s). Mantendo a configuração atual em "
                "memória e preservando o arquivo em disco (não será "
                "sobrescrito com os valores padrão).",
                CONFIG_FILE, exc,
            )
            self._backup_corrupt_file()
            return False

        self.screen_width = data.get("SCREEN_WIDTH", DEFAULTS["SCREEN_WIDTH"])
        self.screen_height = data.get("SCREEN_HEIGHT", DEFAULTS["SCREEN_HEIGHT"])
        self.aim_radius = data.get("AIM_RADIUS", DEFAULTS["AIM_RADIUS"])
        self.deadzone = data.get("DEADZONE", DEFAULTS["DEADZONE"])
        self.aim_return_ms = data.get("AIM_RETURN_MS", DEFAULTS["AIM_RETURN_MS"])
        self.poll_rate = data.get("POLL_RATE", DEFAULTS["POLL_RATE"])

        # Carregar mapping fazendo merge com os defaults
        saved_mapping = data.get("MAPPING", {})
        merged_mapping = dict(DEFAULTS["MAPPING"])
        merged_mapping.update(saved_mapping)
        self.mapping = merged_mapping

        self.modifier_btn = data.get("MODIFIER_BTN", DEFAULTS["MODIFIER_BTN"])
        self.attack_btn = data.get("ATTACK_BTN", DEFAULTS["ATTACK_BTN"])

        # Carregar layout com merge dos defaults para campos faltantes
        saved_layout = data.get("CONTROLLER_LAYOUT", {})
        merged_layout = dict(DEFAULT_CONTROLLER_LAYOUT)
        merged_layout.update(saved_layout)
        self.controller_layout = merged_layout
        return True

    def _backup_corrupt_file(self):
        """Copia o arquivo de config corrompido para um .bak, sem apagar o original."""
        backup_path = CONFIG_FILE + ".bak"
        try:
            shutil.copyfile(CONFIG_FILE, backup_path)
            logger.warning("Backup do config corrompido salvo em %s", backup_path)
        except OSError:
            logger.exception(
                "Não foi possível fazer backup do config corrompido em %s", CONFIG_FILE
            )

    def save_to_disk(self, data=None):
        payload = data if data is not None else self.as_dict()
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=4, ensure_ascii=False)

    def as_dict(self):
        """Retorna um dicionário com todas as configurações atuais."""
        return {
            "SCREEN_WIDTH": self.screen_width,
            "SCREEN_HEIGHT": self.screen_height,
            "AIM_RADIUS": self.aim_radius,
            "DEADZONE": self.deadzone,
            "AIM_RETURN_MS": self.aim_return_ms,
            "POLL_RATE": self.poll_rate,
            "MAPPING": dict(self.mapping),
            "MODIFIER_BTN": self.modifier_btn,
            "ATTACK_BTN": self.attack_btn,
            "CONTROLLER_LAYOUT": dict(self.controller_layout),
        }

    def apply(self, data):
        """Aplica um dicionário (possivelmente parcial) de configurações."""
        self.screen_width = data.get("SCREEN_WIDTH", self.screen_width)
        self.screen_height = data.get("SCREEN_HEIGHT", self.screen_height)
        self.aim_radius = data.get("AIM_RADIUS", self.aim_radius)
        self.deadzone = data.get("DEADZONE", self.deadzone)
        self.aim_return_ms = data.get("AIM_RETURN_MS", self.aim_return_ms)
        self.poll_rate = data.get("POLL_RATE", self.poll_rate)
        self.mapping = data.get("MAPPING", self.mapping)
        self.modifier_btn = data.get("MODIFIER_BTN", self.modifier_btn)
        self.attack_btn = data.get("ATTACK_BTN", self.attack_btn)
        if "CONTROLLER_LAYOUT" in data:
            layout = dict(DEFAULT_CONTROLLER_LAYOUT)
            layout.update(data["CONTROLLER_LAYOUT"])
            self.controller_layout = layout


# --- Instância singleton que guarda o estado real ---
_config = AppConfig()

# --- Variáveis ativas (mantidas por compatibilidade — usadas diretamente por
#      main.py, aim_math.py, wasd_logic.py e gui.py) ---
SCREEN_WIDTH = _config.screen_width
SCREEN_HEIGHT = _config.screen_height
AIM_RADIUS = _config.aim_radius
DEADZONE = _config.deadzone
AIM_RETURN_MS = _config.aim_return_ms
POLL_RATE = _config.poll_rate
MAPPING = _config.mapping
MODIFIER_BTN = _config.modifier_btn
ATTACK_BTN = _config.attack_btn
CONTROLLER_LAYOUT = _config.controller_layout


def _sync_globals_from_state():
    """Copia o estado de `_config` para as variáveis de módulo públicas."""
    global SCREEN_WIDTH, SCREEN_HEIGHT, AIM_RADIUS, DEADZONE, AIM_RETURN_MS, POLL_RATE
    global MAPPING, MODIFIER_BTN, ATTACK_BTN, CONTROLLER_LAYOUT
    SCREEN_WIDTH = _config.screen_width
    SCREEN_HEIGHT = _config.screen_height
    AIM_RADIUS = _config.aim_radius
    DEADZONE = _config.deadzone
    AIM_RETURN_MS = _config.aim_return_ms
    POLL_RATE = _config.poll_rate
    MAPPING = _config.mapping
    MODIFIER_BTN = _config.modifier_btn
    ATTACK_BTN = _config.attack_btn
    CONTROLLER_LAYOUT = _config.controller_layout


def _sync_state_from_globals():
    """Copia as variáveis de módulo públicas de volta para `_config`.

    gui.py ainda escreve diretamente em algumas dessas variáveis (ex.:
    `config.MAPPING[btn] = key` ou `config.CONTROLLER_LAYOUT = layout`) sem
    passar por apply_config(). Isso é lido aqui antes de qualquer leitura/
    escrita "oficial" (save_config/get_current_config/apply_config) para que
    esse caminho legado continue funcionando exatamente como antes.
    """
    _config.screen_width = SCREEN_WIDTH
    _config.screen_height = SCREEN_HEIGHT
    _config.aim_radius = AIM_RADIUS
    _config.deadzone = DEADZONE
    _config.aim_return_ms = AIM_RETURN_MS
    _config.poll_rate = POLL_RATE
    _config.mapping = MAPPING
    _config.modifier_btn = MODIFIER_BTN
    _config.attack_btn = ATTACK_BTN
    _config.controller_layout = CONTROLLER_LAYOUT


def load_config():
    """
    Carrega as configurações do user_config.json.
    Se o arquivo não existir, usa os valores padrão e cria o arquivo.
    """
    _config.load_from_disk()
    _sync_globals_from_state()


def save_config(data=None):
    """Salva as configurações no user_config.json."""
    if data is None:
        _sync_state_from_globals()
        data = _config.as_dict()
    _config.save_to_disk(data)


def get_current_config():
    """Retorna um dicionário com todas as configurações atuais."""
    _sync_state_from_globals()
    return _config.as_dict()


def apply_config(data):
    """Aplica um dicionário de configurações nas variáveis globais."""
    _sync_state_from_globals()
    _config.apply(data)
    _sync_globals_from_state()


# Carregar configurações ao importar o módulo
load_config()
