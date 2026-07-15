from inputs import get_gamepad
import time

def main():
    print("Iniciando modo debug do controle (Usando biblioteca 'inputs')...")
    print("Mexa nos botões e analógicos. Aperte Ctrl+C no terminal para sair.")
    print("-" * 50)

    try:
        while True:
            # get_gamepad() bloqueia a execução até que um evento ocorra no controle
            events = get_gamepad()
            for event in events:
                # Ignora o evento Sync (apenas separador de pacotes)
                if event.ev_type != 'Sync':
                    print(f"Tipo: {event.ev_type:15} | Código: {event.code:20} | Valor: {event.state}")
            
    except KeyboardInterrupt:
        print("\nSaindo...")
    except Exception as e:
        print(f"\nErro ao ler o controle: {e}")
        print("Verifique se o controle está conectado.")

if __name__ == "__main__":
    main()
