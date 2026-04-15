# Agendador — Backend

Backend Django do projeto Agendador.

## Pré-requisitos

- Python 3.12+
- [UV](https://docs.astral.sh/uv/) — gerenciador de pacotes
- Docker + Docker Compose (para PostgreSQL e Redis)

## Setup inicial

```bash
# 1. Instalar o UV (se não tiver)
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. Criar o ambiente virtual e instalar dependências
uv sync --dev

# 3. Copiar o arquivo de variáveis de ambiente
cp .env.example .env
# Editar .env conforme necessário

# 4. Subir PostgreSQL e Redis com Docker
docker compose up -d

# 5. Rodar as migrações
uv run python manage.py migrate

# 6. Criar superusuário (opcional)
uv run python manage.py createsuperuser

# 7. Iniciar o servidor de desenvolvimento
uv run python manage.py runserver
```

O servidor estará disponível em: http://localhost:8000

## Comandos úteis

```bash
# Rodar os testes
uv run pytest

# Rodar testes com cobertura
uv run pytest --cov

# Verificar tipos com MyPy
uv run mypy .

# Lint e formato com Ruff
uv run ruff check .
uv run ruff format .

# Fazer migrações
uv run python manage.py makemigrations
uv run python manage.py migrate

# Iniciar Celery worker (em outro terminal)
uv run celery -A config worker -l info -Q high_priority,notifications,default

# Iniciar Celery Beat (agendador de tarefas periódicas)
uv run celery -A config beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler
```

## Estrutura de pastas

```
backend/
├── apps/                    # Apps Django (lógica de negócio)
│   ├── accounts/            # Usuários, autenticação, OTP
│   ├── providers/           # Perfil de prestadores
│   ├── services/            # Serviços oferecidos
│   ├── appointments/        # Agendamentos
│   ├── notifications/       # WhatsApp, email, SMS
│   ├── reviews/             # Avaliações
│   └── webhooks/            # Recepção de webhooks externos
├── config/                  # Configurações Django + Celery
│   └── settings/
│       ├── base.py          # Configurações compartilhadas
│       ├── development.py   # Dev local
│       └── production.py    # Produção
├── core/                    # Utilitários sem lógica de negócio
│   ├── exceptions.py        # Handler de exceções customizado
│   ├── pagination.py        # Cursor pagination
│   ├── permissions.py       # Permissões DRF customizadas
│   └── urls.py              # Health check
└── tests/                   # Testes (espelha estrutura de apps/)
```
