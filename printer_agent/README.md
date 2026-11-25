# Agente de Impressão — Meu Atendimento Virtual

Aplicativo para Windows que recebe as senhas retiradas no totem (via servidor Meu Atendimento Virtual) e imprime na impressora térmica, automaticamente. Fica ativo na bandeja do sistema, perto do relógio.

---

## Instalação

1. Baixe e execute o [`AgenteImpressao-Setup.exe`](https://github.com/mupisystems/ticket_printer_public/releases/latest/download/AgenteImpressao-Setup.exe).
2. Siga o assistente (não pede senha de administrador; instala só para o usuário atual).
   - **Criar atalho na área de trabalho** e **Iniciar junto com o Windows** vêm marcados.
3. Ao terminar, o agente abre a **configuração guiada**:

| Passo | O que acontece |
|-------|----------------|
| **Conexão** | Cole a **Chave do Totem/Agente de Impressão** (painel → Configurações → Painéis e Totens → Impressão de Senhas → Chaves de Impressão). Ela é validada na hora no servidor de produção. |
| **Impressora** | Lista as impressoras com o status de cada uma (pronta, offline…) e permite imprimir um ticket de teste. |
| **Comprovante** | 6 modelos (Reduzido, Destaque, Compacto, Senha gigante, Faixa escura, Moldura) com prévia de como sai no papel, logo opcional no topo (PNG/JPG, 3 tamanhos, convertido para preto e branco) e botão para imprimir um exemplo. Bobina de 80 ou 58 mm. |
| **Concluir** | Resumo do que foi configurado; qualquer item pode ser alterado. |

**Suporte técnico:** o cliente não escolhe servidor (o padrão é Produção – Meu Atendimento Virtual). Para apontar para Awaitra, homologação, localhost ou um endereço personalizado, pressione **Ctrl+Shift+S** na janela do agente: a escolha de servidor aparece na etapa de conexão e em Configurações.

Uma nova versão do instalador fecha o agente em execução, remove instalações em outra pasta e as versões antigas em `.exe` avulso (com os atalhos delas), e **mantém a configuração**. Na primeira abertura o app mostra as boas-vindas do início, já preenchidas. O `main.exe` da primeira geração não é removido (nome genérico): apague-o manualmente.

---

## Uso

- Clique no ícone da bandeja para abrir o **painel**:
  - **Visão geral** — status em destaque ("Pronto para imprimir", "Sem conexão"…), servidor, impressora, tickets impressos hoje e atividade recente.
  - **Configurações** — chave, bobina, impressora, comprovante e inicialização com o Windows.
  - **Registros** — eventos em tempo real, com filtro de avisos/erros e botão para copiar (útil para o suporte).
- Fechar a janela **não** desliga o agente; para encerrar, use **Sair** no menu da bandeja.
- Menu da bandeja (botão direito): **Configurações/Abrir**, **Reconectar**, **Impressão de Teste**, **Sair**.

Configuração, log e estatísticas ficam em `%APPDATA%\MeuAtendimento\` (a chave é cifrada com o DPAPI do Windows).

---

## Desenvolvimento

Requer Python 3.10+ (64 bits) e o Microsoft Edge WebView2 (já incluso no Windows 10/11 atualizado).

```bash
pip install -r requirements.txt
python main.py          # abre o agente com a janela
python dev.py           # reinicia sozinho ao salvar .py ou arquivos de ui/
```

- `PRINTER_AGENT_DEBUG=1` abre as ferramentas de desenvolvedor na janela.
- Para mexer só no visual, sirva a pasta `ui/` e abra no navegador com dados simulados:
  ```bash
  cd ui && python -m http.server 8765
  # http://127.0.0.1:8765/index.html?mock             → primeiro uso (assistente)
  # http://127.0.0.1:8765/index.html?mock=configured  → painel
  ```

### Estrutura

| Arquivo | Papel |
|---------|-------|
| `main.py` | Entrada: bandeja, conexão WebSocket, janela (instância única) |
| `app_window.py` | Janela pywebview e ponte Python ↔ interface (classe `Api`) |
| `ui/` | Interface: `index.html`, `styles.css`, `app.js` (JavaScript puro, sem build), `dev-mock.js` (só para `?mock`) |
| `websocket_client.py` | Conexão com o servidor, reconexão e deduplicação de jobs |
| `printer_service.py`, `ticket_formatter.py` | Impressão ESC/POS e modelos de comprovante |
| `installer/` | Script do Inno Setup e gerador das imagens do instalador |

### Prévia com os dados reais da conta

O servidor hoje não informa, na conexão, como é o ticket da conta (cabeçalho, rodapé, se usa QR Code). O agente aprende isso com o **primeiro ticket recebido** (`%APPDATA%\MeuAtendimento\ticket_sample.json`) e, a partir daí, a prévia e a impressão de exemplo usam o cabeçalho, o rodapé e o QR Code reais. Antes disso, a prévia usa dados fictícios e tem um botão **QR Code** para ver com e sem.

**Sugestão para o backend:** se a resposta de autenticação incluir o formato do ticket, o agente já usa na conexão (sem esperar o primeiro ticket):

```json
{"type": "auth_ok", "ticket": {"header": "Clínica Vida", "footer": "Obrigado!", "qrcode": true}}
```

O log do agente registra quais campos chegam na autenticação ("Resposta de autenticação do servidor traz: …").

---

## Build

Na pasta `printer_agent`:

| Comando | Gera |
|---------|------|
| `build_exe.bat` (ou `.\build_exe.ps1`) | `dist\AgenteImpressao\AgenteImpressao.exe` (pasta com `_internal\`) |
| `build_installer.bat` | `dist\installer\AgenteImpressao-Setup-<versão>.exe` (reaproveita o build se existir) |
| `build_installer.bat --rebuild` (ou `.\build_exe.ps1 -Installer`) | Os dois, do zero |

- O instalador requer o [Inno Setup 6](https://jrsoftware.org/isdl.php).
- A versão vem de `APP_VERSION` em `config.py` (somente números, ex.: `2.3.0`); atualize também `version_info.txt`.
- Antes de publicar, coloque `installer\MicrosoftEdgeWebview2Setup.exe` ([bootstrapper oficial da Microsoft](https://go.microsoft.com/fwlink/p/?LinkId=2124703), fora do git): ele é embutido e instala o WebView2 em máquinas que não o tenham. Sem WebView2 o agente continua imprimindo pela bandeja, mas a janela não abre.
- `ISCC /DTestBuild=<pasta>` gera um instalador de teste isolado (outro identificador, não encerra processos, só limpa a `<pasta>`).

### Publicar uma versão

Os executáveis não ficam no repositório: são publicados em [Releases](https://github.com/mupisystems/ticket_printer_public/releases).

1. Atualize `APP_VERSION` e `version_info.txt`, gere o instalador e teste.
2. Copie `dist\installer\AgenteImpressao-Setup-<versão>.exe` como **`AgenteImpressao-Setup.exe`**: o nome fixo mantém o link `releases/latest/download/AgenteImpressao-Setup.exe` válido em todas as versões.
3. Crie a Release `v<versão>` com esse arquivo.

---

## Solução de problemas

| Problema | Ação |
|----------|------|
| "Chave recusada" | Conferir a chave em Configurações (painel → Impressão de Senhas → Chaves de Impressão) |
| "Sem conexão com o servidor" | Verificar a internet do totem; o agente reconecta sozinho, ou use **Reconectar** |
| Impressora "Offline" / não aparece | Ligar a impressora, conectar o cabo e clicar em **Atualizar lista** |
| Ticket não imprime | Ver o status da impressora na Visão geral e fazer um **Imprimir teste** |
| Janela em branco | Instalar o Microsoft Edge WebView2 Runtime |

---

## Requisitos

- Windows 10 ou 11 (64 bits) com Microsoft Edge WebView2 (o instalador instala se faltar)
- Impressora térmica de 80 ou 58 mm (homologada: Epson TM-T20X)
- Conexão com a internet
