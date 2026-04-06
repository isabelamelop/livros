# Telegram Book Search (FastAPI + Telethon + HTML)

Projeto fullstack simples que envia uma consulta para um bot do Telegram (como usuário normal) e exibe a resposta na web.

## Estrutura

- `backend/main.py`
- `backend/requirements.txt`
- `frontend/index.html`
- `.gitignore`

## Pré-requisitos

- Python 3.10+
- Conta Telegram já logada no celular
- `API_ID` e `API_HASH` do Telegram (https://my.telegram.org)

## Variáveis de ambiente

Crie um arquivo local `backend/.env` a partir do template:

```powershell
cd backend
Copy-Item .env.example .env
```

Depois edite `backend/.env` com seus valores:

```env
API_ID=123456
API_HASH=seu_api_hash
BOT_USERNAME=nome_do_bot_sem_@
SESSION_NAME=user
RESPONSE_TIMEOUT=10
```

O arquivo `.env` não deve ser enviado para o GitHub (já está no `.gitignore`).

## Rodando o backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Na primeira execução, o Telethon pode pedir autenticação (telefone/código) no terminal. Isso cria um arquivo `.session` (já ignorado no git).

## Rodando o frontend

Abra `frontend/index.html` no navegador.

Por padrão, o frontend chama `http://localhost:8000/search`.

## Endpoint principal

`POST /search`

Body:

```json
{ "query": "nome do livro" }
```

Resposta:

```json
{ "query": "nome do livro", "response": "texto retornado pelo bot" }
```

## Deploy opcional (Render)

O arquivo `render.yaml` já foi incluído para facilitar deploy do backend no Render.
