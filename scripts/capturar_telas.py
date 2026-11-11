"""Gera as imagens do README a partir da aplicação rodando.

    1) streamlit run app.py --server.port 8518 --server.headless true
    2) python scripts/capturar_telas.py            (ou BASE=http://localhost:8519 python ...)

Abre o Chrome sem janela, espera cada página terminar de desenhar (o rodapé é o
último elemento a aparecer) e captura a página inteira, na altura exata do conteúdo.
Só usa o Chrome já instalado e bibliotecas que vêm com o Streamlit (tornado).
"""

from __future__ import annotations

import asyncio
import base64
import json
import os
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path
from urllib.parse import quote

from tornado.websocket import websocket_connect

BASE = os.getenv("BASE", "http://localhost:8518")
CHROME = os.getenv("CHROME", r"C:\Program Files\Google\Chrome\Application\chrome.exe")
PORTA = 9333
LARGURA = 1320
DESTINO = Path(__file__).resolve().parents[1] / "docs" / "img"

# nome do arquivo -> caminho na aplicação
TELAS = {
    "painel": "",
    "consumo": "?aba=consumo",
    "clientes": "?aba=clientes",
    "operacao": "?aba=entrega",
    "assistente": "?pergunta=" + quote("Em que horários o prazo de entrega falha mais?"),
}

PRONTA = """(() => {
  // a página com campo de conversa usa outro contêiner de rolagem
  const principal = document.querySelector('[data-testid="stMain"], [data-testid="stAppScrollToBottomContainer"]');
  const ocupada = document.querySelector('[data-testid="stSkeleton"], [data-testid="stSpinner"]');
  if (!principal || ocupada || !document.querySelector('.pr-rodape')) return 0;
  return principal.scrollHeight;
})()"""


class Aba:
    def __init__(self, ws):
        self.ws, self.n = ws, 0

    async def cmd(self, metodo: str, **params):
        self.n += 1
        await self.ws.write_message(json.dumps({"id": self.n, "method": metodo, "params": params}))
        while True:
            msg = json.loads(await self.ws.read_message())
            if msg.get("id") == self.n:
                return msg.get("result", {})

    async def js(self, expressao: str):
        r = await self.cmd("Runtime.evaluate", expression=expressao, returnByValue=True)
        return r.get("result", {}).get("value")


async def capturar(aba: Aba, nome: str, caminho: str) -> bool:
    await aba.cmd("Emulation.setDeviceMetricsOverride", width=LARGURA, height=1000,
                  deviceScaleFactor=1, mobile=False)
    await aba.cmd("Page.navigate", url=f"{BASE}/{caminho}")
    altura, estavel = 0, 0
    for _ in range(120):  # até 60 s; pronta = mesma altura em 4 leituras seguidas
        await asyncio.sleep(0.5)
        atual = await aba.js(PRONTA) or 0
        estavel = estavel + 1 if atual and atual == altura else 0
        altura = atual
        if estavel >= 4:
            break
    else:
        print(f"FALHOU {nome}.png (a página não terminou de carregar)")
        return False
    await aba.cmd("Emulation.setDeviceMetricsOverride", width=LARGURA, height=int(altura),
                  deviceScaleFactor=1, mobile=False)
    await asyncio.sleep(2.5)  # gráficos e fontes se ajustam à nova altura
    png = await aba.cmd("Page.captureScreenshot", format="png")
    (DESTINO / f"{nome}.png").write_bytes(base64.b64decode(png["data"]))
    print(f"ok     {nome}.png ({LARGURA}x{int(altura)})")
    return True


async def main() -> int:
    DESTINO.mkdir(parents=True, exist_ok=True)
    perfil = tempfile.mkdtemp(prefix="chrome-capturas-")
    chrome = subprocess.Popen(
        [CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", f"--remote-debugging-port={PORTA}",
         "--remote-allow-origins=*", f"--user-data-dir={perfil}", f"--window-size={LARGURA},1000", "about:blank"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(40):
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{PORTA}/json/list", timeout=2) as r:
                    alvo = next(t for t in json.load(r) if t["type"] == "page")
                break
            except Exception:
                await asyncio.sleep(0.5)
        else:
            print("Não consegui abrir o Chrome. Defina CHROME com o caminho do executável.")
            return 1
        aba = Aba(await websocket_connect(alvo["webSocketDebuggerUrl"], max_message_size=2**28))
        await aba.cmd("Page.enable")
        nomes = sys.argv[1:] or list(TELAS)
        resultados = [await capturar(aba, n, TELAS[n]) for n in nomes]
        return 0 if all(resultados) else 1
    finally:
        chrome.terminate()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
