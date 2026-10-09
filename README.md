# 🎛️ AlsaMixer

Aplicação para gerenciamento e controle de áudio via interface gráfica/script integrado ao ALSA.

---

## 📸 Demonstração

![Interface Principal](https://via.placeholder.com/800x450.png?text=Preview+Principal)
*Visão geral da interface do sistema.*
![Interface Principal](https://via.placeholder.com/800x450.png?text=Preview+Principal)
*Visão geral da interface do sistema.*
![Interface Principal](https://via.placeholder.com/800x450.png?text=Preview+Principal)
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
