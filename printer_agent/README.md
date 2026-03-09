# Agente de Impressão — Meu Atendimento

Aplicativo para Windows que recebe comandos do servidor Meu Atendimento e imprime os tickets na impressora térmica do totem.

---

## Instalação

### Executável (recomendado)

1. Baixe `App de Impressão.exe` (pasta [releases](.) ou gere com o build abaixo).
2. Copie para uma pasta no totem (ex: `C:\MeuAtendimento\`).
3. Execute `App de Impressão.exe`.

### Python (desenvolvimento)

1. Instale [Python 3.10+](https://www.python.org/downloads/).
2. No terminal, na pasta `printer_agent`:
   ```bash
   pip install -r requirements.txt
   python main.py
   ```
3. **Modo desenvolvimento** (reinicia ao salvar código):
   ```bash
   python dev.py
   ```

---

## Build do executável

Na pasta `printer_agent`:

- **PowerShell:** `.\build_exe.ps1` ou `.\build_exe.bat`
- **CMD:** `build_exe.bat`

Ou manualmente:

```bash
pip install -r requirements.txt
pyinstaller printer_agent.spec
```

O exe será gerado em `dist\App de Impressão.exe`.

**Arquivos ignorados no build:** `build/`, `dist/`, `*.exe` (veja `.gitignore`). Após o build, pode apagar a pasta `build\` para liberar espaço.

---

## Assets (imagens)

Coloque na pasta `printer_agent`:

| Arquivo           | Uso                                |
|-------------------|------------------------------------|
| `app.ico`         | Ícone do executável (opcional). Se não existir, o build gera a partir de `tray_icon.png` |
| `tray_icon.png`   | Ícone na bandeja do sistema        |
| `logo.png`        | Logo no cabeçalho da janela de configuração |

---

## Configuração

1. Execute o agente; o ícone aparece na **bandeja do sistema** (perto do relógio).
2. Clique com o **botão direito** no ícone → **Configurações**.
3. Preencha:

| Campo | Descrição |
|-------|-----------|
| **Ambiente** | Produção Brasil, Produção US, Homologação ou Localhost |
| **Token** | UUID do totem (painel → Totem → identificador) |
| **Impressora** | Impressora térmica; use "Atualizar" se não listar |
| **Modelo de comprovante** | Reduzido, Destaque (SENHA primeiro) ou Compacto |
| **Conectar automaticamente** | Marque para conectar ao iniciar |

4. **Salvar**. Use **Testar Conexão** para reconectar; o status na janela atualiza sozinho.

---

## Uso

- Senha retirada no totem → ticket impresso na impressora configurada.
- Ícone **verde** = conectado; **vermelho** = desconectado; **laranja** = conectando.
- Menu (botão direito): **Configurações**, **Reconectar**, **Impressão de Teste**, **Sair**.

---

## Solução de problemas

| Problema | Ação |
|----------|------|
| Ícone vermelho | Conferir ambiente e token nas configurações |
| "Autenticação falhou" | Token incorreto ou totem inativo no painel |
| Impressora não aparece | Ligar impressora, clicar em "Atualizar" |
| Ticket não imprime | Conferir impressora selecionada e papel |
| Status não atualiza na janela | Clicar em "Testar Conexão"; o status atualiza em seguida |

---

## Requisitos

- Windows 10 ou 11
- Impressora térmica (ex.: Epson TM-T20II, Elgin i9 ou compatível)
- Conexão com a internet
