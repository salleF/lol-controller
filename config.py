# ==============================================================================
# CONFIGURAÇÕES DO CONTROLE DE LEAGUE OF LEGENDS
# ==============================================================================

# Resolução da sua tela (Necessário para a mira calcular o centro da tela)
SCREEN_WIDTH = 1920
SCREEN_HEIGHT = 1080

# Distância do círculo da mira ao redor do seu campeão (em pixels)
# Aumente se quiser que a mira fique mais longe, diminua para ficar mais perto.
AIM_RADIUS = 300

# Sensibilidade e Zonas Mortas
DEADZONE = 0.2  # Ignora movimentos muito leves no analógico (evita drift)
POLL_RATE = 0.01  # Tempo de espera entre cada leitura do controle (em segundos)

# ==============================================================================
# MAPEAMENTO DE BOTÕES (PlayStation / Xbox)
# ==============================================================================

# Botões de Ação
MAPPING = {
    "SQUARE": "q",      # Quadrado / X no Xbox
    "TRIANGLE": "w",    # Triângulo / Y no Xbox
    "CIRCLE": "e",      # Bolinha / B no Xbox
    "CROSS": "r",       # X / A no Xbox
    "R1": "d",          # Feitiço 1
    "L1": "f",          # Feitiço 2
    "DPAD_UP": "1",     # Item 1
    "DPAD_RIGHT": "2",  # Item 2
    "DPAD_DOWN": "3",   # Item 3
    "DPAD_LEFT": "4",   # Item 4
}

# Modificadores e Cliques
MODIFIER_BTN = "L2"     # L2 pressionado + Botão de Habilidade = Upa a Habilidade (Ctrl + Tecla)
ATTACK_BTN = "R2"       # R2 vai simular o Clique Direito (Ataque Básico / Interagir)

