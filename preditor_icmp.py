import os
import re
import subprocess
import time
from datetime import datetime


def disparar_ping(host):
    """Executa o ping nativo do Windows aceitando respostas em Português e Inglês."""
    try:
        comando = ["ping", "-n", "1", "-w", "1000", host]
        resultado = subprocess.run(
            comando, capture_output=True, text=True, timeout=2
        )

        if resultado.returncode == 0:
            # Captura 'tempo=12ms' ou 'time=12ms'
            match = re.search(
                r"(?:tempo|time)[=<](\d+)ms", resultado.stdout, re.IGNORECASE
            )
            if match:
                return float(match.group(1))
            elif (
                "tempo<1ms" in resultado.stdout.lower()
                or "time<1ms" in resultado.stdout.lower()
            ):
                return 0.5
        return None
    except Exception:
        return None



def calcular_jitter_rfc3550(rtts):
  """Calcula o Jitter suavizado de acordo com a RFC 3550."""
  rtts_validos = [r for r in rtts if r is not None]
  if len(rtts_validos) < 2:
    return 0.0

  jitter = 0.0
  for i in range(1, len(rtts_validos)):
    diferenca = abs(rtts_validos[i] - rtts_validos[i - 1])
    jitter += (diferenca - jitter) / 16.0
  return round(jitter, 2)


def classificar_status(perda_percentual, jitter, rtt_medio):
  """Classifica a saúde do link com base nos limiares do projeto."""
  if perda_percentual > 2.0 or rtt_medio is None:
    return "COM FALHA", "🔴"
  elif perda_percentual > 0.0 or jitter > 20.0:
    return "EM RISCO", "🟡"
  else:
    return "ESTÁVEL", "🟢"


def obter_caminho_salvamento(nome_arquivo="preditor_falhas_log.csv"):
  """Localiza a pasta correta da Área de Trabalho no Windows ou usa a pasta do próprio projeto."""
  try:
    import winreg

    key = winreg.OpenKey(
        winreg.HKEY_CURRENT_USER,
        r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders",
    )
    desktop, _ = winreg.QueryValueEx(key, "Desktop")
    winreg.CloseKey(key)
    caminho_desktop = os.path.expandvars(desktop)
    if os.path.exists(caminho_desktop):
      return os.path.join(caminho_desktop, nome_arquivo)
  except Exception:
    pass

  # Fallback: se não encontrar o registro, salva na própria pasta do projeto PyCharm
  return os.path.join(os.getcwd(), nome_arquivo)


def executar_monitoramento(
    host_alvo="8.8.8.8", tamanho_rajada=10, intervalo_rajadas=3
):
  print("=" * 65)
  print(f"🚀 INICIANDO PREDITOR DE FALHAS ICMP — HOST ALVO: {host_alvo}")
  print("=" * 65)

  arquivo_log = obter_caminho_salvamento("preditor_falhas_log.csv")

  # Garante que os diretórios pai existam antes de criar o arquivo
  os.makedirs(os.path.dirname(arquivo_log), exist_ok=True)

  # Prepara o cabeçalho do CSV se não existir
  if not os.path.exists(arquivo_log):
    with open(arquivo_log, "w", encoding="utf-8") as f:
      f.write("Horario,Host,RTT_Medio_ms,Jitter_ms,Perda_Pct,Status\n")

  try:
    while True:
      horario_atual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
      respostas = []

      print(
          f"\n[{horario_atual}] Coletando rajada de {tamanho_rajada} pings..."
      )

      for _ in range(tamanho_rajada):
        rtt = disparar_ping(host_alvo)
        respostas.append(rtt)
        time.sleep(0.5)

      # Cálculo das métricas da rajada
      pings_sucesso = [r for r in respostas if r is not None]
      total_enviados = len(respostas)
      total_perdidos = total_enviados - len(pings_sucesso)
      perda_pct = round((total_perdidos / total_enviados) * 100, 1)

      rtt_medio = (
          round(sum(pings_sucesso) / len(pings_sucesso), 2)
          if pings_sucesso
          else None
      )
      jitter = calcular_jitter_rfc3550(respostas)

      status, icone = classificar_status(perda_pct, jitter, rtt_medio)

      # Exibição no Terminal
      rtt_str = f"{rtt_medio} ms" if rtt_medio is not None else "TIMEOUT"
      print(f" -> Status: {icone} {status}")
      print(
          f" -> RTT Médio: {rtt_str} | Jitter: {jitter} ms | Perda:"
          f" {perda_pct}%"
      )

      # Gravação no Log
      with open(arquivo_log, "a", encoding="utf-8") as f:
        f.write(
            f"{horario_atual},{host_alvo},{rtt_medio},{jitter},{perda_pct},{status}\n"
        )

      print(f" -> Registro salvo em: {arquivo_log}")
      time.sleep(intervalo_rajadas)

  except KeyboardInterrupt:
    print("\n\n⏹️ Monitoramento encerrado pelo usuário.")


if __name__ == "__main__":
  IP_ALVO = "8.8.8.8"
  executar_monitoramento(host_alvo=IP_ALVO)
