# 🎛️ AlsaMixer

O **AlsaMixer GUI** é uma interface gráfica moderna desenvolvida em Python com **CustomTkinter** para gerenciar o subsistema de áudio Linux (**ALSA**). A aplicação entrega uma experiência visual inspirada no clássico utilitário de terminal `alsamixer`, unindo controle granular de hardware a recursos nativos de desktop.

---

### ✨ Funcionalidades

* **Gerenciamento de Placas de Som:** detecção automática e seleção de dispositivos físicos listados em `/proc/asound/cards`.
* **Abas Especializadas:**
  * **Saída (Playback):** ajuste de volume e mudo para caixas/fones e saídas digitais **S/PDIF** (`IEC958`).
  * **Entrada (Capture):** controle de ganho, microfones e captura.
  * **Opções:** chaves e enumerações do hardware (ex.: *Auto-Mute Mode*, *Input Source*).
* **Controles em Colunas:**
  * Sliders verticais com escala perceptual (`amixer -M`, mapeamento logarítmico real).
  * Checkbox de mudo integrado ao switch de hardware (`mute/unmute` e `nocap/cap`).
  * Chaves dedicadas ON/OFF para saídas digitais e toggles simples.
* **Navegação & Scroll:** colunas lado a lado com rolagem horizontal no painel e ajuste fino de volume (±3%) diretamente pela roda do mouse sobre os sliders.
* **Bandeja do Sistema (System Tray):**
  * Suporte a execução em segundo plano via tray icon (`pystray`).
  * Fechar para a bandeja, inicialização minimizada e garantia de instância única via socket Unix.
* **Sincronização em Tempo Real:** *polling* automático (2s) com *debounce* (~60 ms) ao mover sliders, refletindo mudanças externas sem congelar a interface.
* **Gerenciamento Multi-Monitor:** memorização inteligente de tamanho, posição física real (offset de decorações do gerenciador de janelas) e prevenção de saltos de tela ao aplicar escalas.
* **Personalização Completa:** temas Claro/Escuro/Sistema, escala de DPI da interface e persistência atômica das preferências em `$XDG_CONFIG_HOME/alsamixer-gui/settings.json`.

---

## 📸 Demonstração

![Interface Principal](https://raw.githubusercontent.com/cesarhfborges/alsamixer_gui/refs/heads/master/images/printscreen-01.png)
*Visão geral da interface do sistema.*
![Interface Principal](https://raw.githubusercontent.com/cesarhfborges/alsamixer_gui/refs/heads/master/images/printscreen-03.png)
*Visão geral da interface do sistema.*
![Interface Principal](https://raw.githubusercontent.com/cesarhfborges/alsamixer_gui/refs/heads/master/images/printscreen-04.png)
*Visão geral da interface do sistema.*
![Interface Principal](https://raw.githubusercontent.com/cesarhfborges/alsamixer_gui/refs/heads/master/images/printscreen-02.png)
*Visão geral da interface do sistema.*

# 🚀 Configuração do Ambiente Virtual (venv) e Dependências

Este guia prático explica como configurar o ambiente virtual, ativar o `venv`, instalar as dependências do projeto e atualizar o arquivo de requerimentos.

---

## 📦 1. Criar o Ambiente Virtual (venv)

No terminal, navegue até a pasta raiz do seu projeto e execute o comando abaixo para criar o ambiente virtual (substitua `.venv` pelo nome que desejar, embora `.venv` seja o padrão recomendado):

```bash
python3 -m venv .venv
```

---

## ⚡ 2. Ativar o Ambiente Virtual

Você precisa ativar o ambiente virtual **toda vez** que abrir um novo terminal para trabalhar no projeto.

* **No Linux / macOS:**
  ```bash
  source .venv/bin/activate
  ```

* **No Windows (Prompt de Comando - CMD):**
  ```cmd
  .venv\Scripts\activate.bat
  ```

* **No Windows (PowerShell):**
  ```powershell
  .venv\Scripts\Activate.ps1
  ```

>💡 **Como saber se funcionou?** O nome do seu ambiente `(.venv)` aparecerá no início da linha do seu terminal.

---

## 📥 3. Instalar as Dependências (`requirements.txt`)

Com o ambiente virtual **ativado**, atualize o gerenciador de pacotes (`pip`) e instale todas as bibliotecas necessárias listadas no projeto:

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

---

## 🔄 4. Atualizar o `requirements.txt` (Gerar novas dependências)

Se você instalar alguma biblioteca nova durante o desenvolvimento (ex: `pip install requests`) e quiser salvá-la no arquivo de requerimentos para que outras pessoas possam usá-la, execute:

```bash
pip freeze > requirements.txt
```

---

## 🛑 Desativar o Ambiente Virtual

Quando terminar de trabalhar no projeto e quiser sair do ambiente virtual, basta digitar:

```bash
deactivate
```
