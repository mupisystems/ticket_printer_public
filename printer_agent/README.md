# Agente de Impressão - Meu Atendimento

Aplicativo para Windows que recebe comandos do servidor Meu Atendimento e imprime os tickets automaticamente na impressora térmica do totem.

## Como instalar

### Opção 1: Executável (recomendado)

1. Baixe o arquivo `printer_agent.exe` da pasta de releases
2. Copie para uma pasta no computador do totem (ex: `C:\MeuAtendimento\`)
3. Execute o `printer_agent.exe`

### Opção 2: Rodar com Python (desenvolvimento)

1. Instale o [Python 3.10+](https://www.python.org/downloads/)
2. Abra o terminal na pasta `printer_agent`
3. Instale as dependências:
   ```
   pip install -r requirements.txt
   ```
4. Execute:
   ```
   python main.py
   ```

## Como configurar

Ao executar, o agente aparece como um ícone na **bandeja do sistema** (perto do relógio do Windows).

1. Clique com o **botão direito** no ícone
2. Clique em **Configurações**
3. Preencha os campos:

| Campo | O que colocar |
|-------|---------------|
| **Ambiente** | Selecione o servidor correto (Produção Brasil, Produção US, Homologação ou Localhost para testes) |
| **Token** | O código UUID do totem (veja abaixo como encontrar) |
| **Impressora** | Selecione a impressora térmica na lista. Clique em "Atualizar" se ela não aparecer |
| **Conectar automaticamente** | Marque para o agente conectar sozinho ao abrir |

4. Clique em **Salvar**

O ícone na bandeja ficará **verde** quando conectado com sucesso.

### Onde encontrar o Token

1. Acesse o **painel administrativo** do Meu Atendimento
2. Vá até o cadastro do **Totem**
3. Copie o campo **identificador** (é um código UUID, ex: `a1b2c3d4-e5f6-7890-abcd-ef1234567890`)

## Como usar

Depois de configurado, o agente funciona automaticamente:

- Quando um cliente retira uma senha no totem, o ticket é impresso na impressora térmica
- Se a conexão cair, o agente reconecta sozinho
- O ícone na bandeja mostra o status:
  - **Verde** = conectado
  - **Vermelho** = desconectado
  - **Amarelo** = conectando

### Menu do ícone (botão direito)

- **Configurações** — abre a janela de configuração
- **Reconectar** — força uma nova conexão com o servidor
- **Impressão de Teste** — imprime um ticket de teste para verificar a impressora
- **Sair** — fecha o agente

## Solução de problemas

| Problema | O que fazer |
|----------|-------------|
| Ícone vermelho | Verifique se o ambiente e o token estão corretos nas configurações |
| "Autenticação falhou" | O token está errado ou o totem está inativo no painel. Verifique o cadastro do totem |
| Impressora não aparece na lista | Verifique se a impressora está ligada e instalada no Windows. Clique em "Atualizar" |
| Ticket não imprime | Verifique se a impressora selecionada é a correta e se tem papel |
| Agente não reconecta | Se o token está errado, o agente para de tentar. Corrija o token e clique em "Reconectar" |

## Requisitos

- Windows 10 ou 11
- Impressora térmica (ex: Epson TM-T20II, Elgin i9, ou compatível)
- Conexão com a internet
