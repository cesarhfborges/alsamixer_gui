# Plano de Implementação — GUI para o ALSA Mixer

## Objetivo

Interface gráfica (CustomTkinter) que replica o essencial do `alsamixer`:

1. **Seleção da placa de som** (dispositivos físicos listados em `/proc/asound/cards`).
2. Para a placa selecionada, **abas separadas**:
   - **Saída (Playback)** — controles com volume/mudo de reprodução, incluindo
     saídas digitais **S/PDIF** (`IEC958` no ALSA), como no alsamixer.
   - **Entrada (Capture)** — controles com volume/mudo de captura.
   - **Opções** — opções do sistema (enumerações, ex.: *Auto-Mute Mode*, *Input Source*).
3. Cada controle é uma **coluna** (faixa) com o valor atual, **slider vertical
   (0–100%)**, **checkbox "Mudo"** (quando o hardware suporta) e o nome. As colunas
   ficam lado a lado com **rolagem horizontal**. Controles só com chave (S/PDIF)
   mostram ON/OFF no lugar do slider.

## Arquitetura (camadas)

```
src/
├── core/
│   ├── models.py          # Dataclasses: SoundCard, MixerControl, Direction
│   ├── amixer_parser.py   # Funções puras: parse de /proc/asound/cards e `amixer scontents`
│   ├── layout.py          # Classificação: Section, ControlKind, ControlSpec, build_layout()
│   ├── interfaces.py      # AudioController e ControlActions (ABCs), MixerError
│   └── linux_mixer.py     # AlsaMixerController — implementação via `amixer`
├── gui/
│   ├── control_widgets.py # ControlView (base, coluna) + Volume/Enum + ControlViewFactory
│   ├── control_panel.py   # ControlPanel — colunas com rolagem horizontal, igual para todas as abas
│   ├── actions.py         # CardActions — liga ControlActions à placa atual + tratamento de erro
│   ├── main_window.py     # Janela: select de placa + abas + tema + recarregar + polling
│   └── theme_manager.py   # (existente)
└── main.py                # Composição (injeção do controller na GUI)
tests/                     # unittest (sem dependências extras) + fixtures reais do amixer
```

### Princípios SOLID aplicados

- **S** — cada módulo tem uma responsabilidade: parser só interpreta texto,
  `layout` só classifica, `linux_mixer` só executa comandos, `CardActions` só
  despacha ações/erros, `ControlPanel` só lista controles, a janela só compõe.
- **O** — novos tipos de controle: criar uma subclasse de `ControlView` e
  `factory.register(ControlKind.X, MinhaView)`; janela e painéis não mudam.
- **L** — toda `ControlView` é intercambiável: mesmo construtor
  `(master, spec, actions)` e mesmos métodos `render()` / `update_state()`.
- **I** — os widgets dependem só de `ControlActions` (3 métodos, sem placa);
  a janela depende de `AudioController`.
- **D** — a GUI recebe `AudioController` e (opcionalmente) a `ControlViewFactory`
  por injeção; os testes usam um controller falso.

### Criação uniforme dos controles visuais

```python
spec = ControlSpec(control, ControlKind.VOLUME, Direction.PLAYBACK)
view = factory.create(master, spec, actions)   # mesmo método para qualquer tipo
```

`ControlView` aplica *template method*: a base cria o rótulo do nome e o grid
comum, chama `_build_widgets()` e `_render()` — únicos pontos que cada tipo
implementa.

## Decisões técnicas

| Tema | Decisão |
|---|---|
| Backend | `amixer` (alsa-utils) via `subprocess`, sem shell, argumentos em lista. |
| Escala de volume | `amixer -M` (mapeada/perceptual, igual ao `alsamixer`) para leitura e escrita. |
| Classificação Saída/Entrada | Capabilities `pvolume/pswitch` → Saída; `cvolume/cswitch` → Entrada; controle com ambos aparece nas duas abas. `volume`/`switch` genéricos: heurística por nome (Mic/Capture/Boost/Input → Entrada). |
| Mudo | Switch ALSA `on` = som ativo. Checkbox "Mudo" marcado ⇔ switch `off`. Playback: `mute/unmute`; Capture: `nocap/cap`. |
| Canais | Exibe a média dos canais; ajuste aplica a todos (comportamento "travado" do alsamixer). |
| Nomes | `IEC958` é exibido como `S/PDIF` (mesmo mapeamento do alsamixer); o amixer continua recebendo o nome real. |
| Rolagem | Roda do mouse rola o painel na horizontal; sobre um slider, ajusta o volume (±3%). |
| Tema | Detecção: `color-scheme` (GNOME/freedesktop) → nome do tema GTK (Cinnamon/GNOME/MATE, ex.: `Mint-L-Dark-Blue`) → `darkdetect`. Widgets usam cores explícitas (par claro/escuro) do tema, pois `"transparent"` dentro de `CTkScrollableFrame` não acompanha a troca de modo. |
| Responsividade | Escrita de volume com *debounce* (~60 ms) ao arrastar o slider. |
| Sincronização | *Polling* a cada 2 s para refletir mudanças externas (teclas de volume, outros apps), ignorando linhas em interação. |
| Erros | `MixerError` exibida na barra de status, sem derrubar a aplicação. |

## Etapas

1. **Modelos + parser** (`models.py`, `amixer_parser.py`).
2. **Controller real** (`linux_mixer.py`) e nova interface (`interfaces.py`).
3. **Widgets** de controle e **janela principal** com select + abas.
4. **Testes automatizados** (`tests/`): parser com fixtures reais, montagem de
   comandos do controller com runner falso, *smoke test* da GUI com controller falso.
5. **Teste prático** no hardware real: leitura de todas as placas e escrita/
   restauração de um controle inofensivo.
6. **Review** do código e ajustes.

## Como executar

```bash
source .venv/bin/activate
python main.py                       # ou: python src/main.py
python -m unittest discover -s tests -t . -v
```

Requisitos de sistema: `alsa-utils` (comando `amixer`) e `python3-tk`.

## Configurações e arquivo de estado

Arquivo JSON em `$XDG_CONFIG_HOME/alsamixer-gui/settings.json`
(padrão `~/.config/alsamixer-gui/settings.json`), gravado de forma atômica
(arquivo temporário + `os.replace`). Arquivo ausente, corrompido ou com valores
inválidos → os padrões são usados para os campos inválidos.

```jsonc
{
  "version": 1,
  "settings": {
    "theme": "System",            // System | Dark | Light
    "ui_scale": 1.0,              // 0.9 | 1.0 | 1.1 | 1.25 | 1.5
    "default_card": "PCH",        // id da placa (/proc/asound/cards) ou "" = última utilizada
    "default_tab": "",            // Saída | Entrada | Opções ou "" = última utilizada
    "poll_interval_ms": 2000,     // 0 = atualização automática desligada
    "wheel_step": 3,              // % por giro da roda sobre o slider
    "remember_window": true,
    "last_card": "PCH",           // estado: gravado automaticamente
    "last_tab": "Saída",          // estado
    "window_geometry": "960x620"  // estado (só o tamanho)
  }
}
```

| Ponto configurável | Por quê |
|---|---|
| Tema | Movido da janela principal para a tela de Configurações. |
| Escala da interface | Textos/selects maiores em telas de alta resolução. |
| Placa de som padrão | Dispositivo exibido ao abrir. Usa o **id** da placa (ex.: `PCH`), estável mesmo quando o índice muda ao conectar/desconectar USB. Se a placa não estiver presente, cai na última usada e depois na primeira. |
| Aba inicial | Saída/Entrada/Opções ou a última utilizada. |
| Lembrar tamanho da janela | Restaura o tamanho (a posição fica a cargo do gerenciador de janelas). |
| Atualização automática | Intervalo do polling (ou desligado). |
| Passo da roda do mouse | Sensibilidade do ajuste de volume pela roda. |

Arquitetura:
- `src/core/settings.py` — `AppSettings` (dados + validação + regras `initial_card`/`initial_tab`),
  `SettingsRepository` (ABC), `JsonSettingsRepository` e `InMemorySettingsRepository` (testes).
- `src/gui/settings_dialog.py` — campos declarativos (`SettingField`) e um único método
  `_add_field()` que cria qualquer linha da tela. Nova configuração = atributo em
  `AppSettings` + um `SettingField` em `build_fields()`.
- `AlsamixerGUI.apply_settings()` aplica tudo em tempo de execução (tema, escala, polling,
  passo da roda via `ViewOptions` compartilhado pela `ControlViewFactory`).
