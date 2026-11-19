# Guia de Instalação e Configuração Local

Este guia detalha o passo a passo para configurar a biblioteca **Tradeiros** localmente na sua máquina.

> [!CAUTION]
> **AVISO DE SEGURANÇA:** Por motivos de segurança, recomendamos fortemente o uso de uma **API-KEY configurada como SOMENTE LEITURA (Read-Only)**. Nunca utilize chaves com permissão de saque (Withdraw) ou transferência em ferramentas de visualização.

> [!NOTE]
> **Exchanges Suportadas:** Atualmente, a biblioteca suporta a exchange **OKX**. O suporte para **Bitget** e **Bybit** está em desenvolvimento e será disponibilizado nos próximos releases.

---

### 1. Pré-requisitos

Certifique-se de ter o **Python 3.8 ou superior** instalado na sua máquina. Para verificar, abra o terminal e execute:

```bash
python --version
```

Caso não tenha o Python instalado, faça o download em [python.org](https://python.org).

<!-- IMAGEM: terminal mostrando python --version -->

---

### 2. Criar a Pasta do Projeto

Crie uma pasta para o projeto e acesse-a pelo terminal:

```bash
mkdir tradeiros
cd tradeiros
```

<!-- IMAGEM: explorer ou terminal mostrando a pasta criada -->

---

### 3. Criar Ambiente Virtual (Recomendado)

O ambiente virtual isola as dependências do projeto, evitando conflitos com outras bibliotecas Python instaladas no sistema.

```bash
python -m venv .venv
```

Ative o ambiente:

```bash
# Windows
.venv\Scripts\activate

# Linux/macOS
source .venv/bin/activate
```

O terminal exibirá o nome do ambiente `(.venv)` no início da linha, indicando que está ativo.

<!-- IMAGEM: terminal com venv ativado -->

---

### 4. Instalar a Biblioteca

Com o ambiente virtual ativo, instale a biblioteca diretamente do **PyPI**:

```bash
pip install tradeiros --pre --upgrade
```

| Parâmetro | Função |
|-----------|--------|
| `--pre` | Instala versões pré-release (alpha/beta). Necessário enquanto a biblioteca estiver em fase de testes. |
| `--upgrade` | Garante que a versão mais recente seja instalada, mesmo que já exista uma versão anterior. |

> [!NOTE]
> Enquanto a biblioteca estiver em fase de testes (alpha/beta), a flag `--pre` é **obrigatória** para receber as últimas correções e funcionalidades. Após o lançamento da versão estável, este parâmetro não será mais necessário.

<!-- IMAGEM: terminal mostrando instalação concluída -->

---

### 5. Configurar o Arquivo `.env`

Crie um arquivo chamado `.env` na pasta do projeto com as credenciais da sua exchange. Use o bloco de notas ou qualquer editor de texto:

```
OKX_API_KEY=sua_key
OKX_API_SECRET=seu_secret
OKX_PASSPHRASE=sua_passphrase
```

Substitua `sua_key`, `seu_secret` e `sua_passphrase` pelos valores reais da sua conta.

> [!IMPORTANT]
> O arquivo `.env` contém informações sensíveis. **Nunca compartilhe** este arquivo e certifique-se de que ele está listado no `.gitignore` caso utilize versionamento de código.

---

### 6. Testar a Instalação

Crie um arquivo Python (ex: `teste.py`) na pasta do projeto com o seguinte conteúdo:

```python
from tradeiros import Tradeiros

# Inicializa a carteira (sufixo vazio = credenciais padrão do .env)
t = Tradeiros("okx")

# Atualiza os dados da exchange
df = t.atualizar()

# Exibe o patrimônio total
print(f"Patrimônio: $ {t.patrimonio():,.2f}")
print(df)

```

Execute no terminal:

```bash
python teste.py
```

> [!TIP]
> A biblioteca também suporta **múltiplas carteiras** no mesmo `.env`. Para configurar uma segunda carteira, adicione as credenciais com o sufixo `_AGRESSIVA`:
> ```
> OKX_API_KEY_AGRESSIVA=sua_key
> OKX_API_SECRET_AGRESSIVA=seu_secret
> OKX_PASSPHRASE_AGRESSIVA=sua_passphrase
> ```

<!-- IMAGEM: terminal exibindo o resultado do teste (patrimônio e gráficos) -->

---

### 7. Uso com Jupyter (Opcional)

Para uma experiência mais visual com tabelas e gráficos interativos, instale o **JupyterLab** no mesmo ambiente virtual:

```bash
pip install jupyterlab
jupyter lab
```

O navegador abrirá automaticamente. Crie um novo notebook e utilize o mesmo código do passo 6.

<!-- IMAGEM: jupyter lab aberto com tabela e gráficos -->

---

> [!TIP]
> Para ambiente de desenvolvimento e visualização, o **Jupyter Notebook** oferece tabelas formatadas e gráficos inline que facilitam a leitura do DataFrame de ordens gerado pela biblioteca.
