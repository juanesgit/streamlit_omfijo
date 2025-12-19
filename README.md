# Streamlit Producción - Seguimiento O&M Fijo CCOT R3

## Descripción
Aplicación Streamlit para el seguimiento de backlog O&M Fijo (CCOT R3). Incluye soporte para variables de entorno y despliegue con Docker Compose.

## Requisitos
- Python 3.9+ (desarrollo local)
- Docker y Docker Compose (para contenedores)

## Configuración
- Variables de entorno (usadas por la app):
  - `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`, `DB_NAME`
- Local (opción 1): usar `.streamlit/secrets.toml` (no se versiona)
- Docker (opción 2): usar variables de entorno en `docker-compose.yml` o un archivo `.env` (no se versiona)

## Desarrollo local
```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run seguimiento.py
```

## Docker
- Construir y levantar en segundo plano:
```powershell
docker compose up -d --build
```
- Ver logs y parar:
```powershell
docker compose logs -f
docker compose down
```
- Acceder: http://localhost:8501

## Despliegue (sin registry)
1. En el servidor de producción: instalar Docker y Docker Compose.
2. Clonar el repositorio: `git clone <repo>` y entrar al proyecto.
3. Crear `.env` con:
```
DB_USER=ccot
DB_PASSWORD=ccot
DB_HOST=10.108.34.32
DB_PORT=33063
DB_NAME=ccot
```
4. `docker compose up -d --build`
5. Verificar en `http://<IP_SERVER>:8501`

## Git: guía de inicialización
```powershell
# Dentro de la carpeta del proyecto
git init
# Config opcional de usuario (si aplica)
# git config user.name "Tu Nombre"
# git config user.email "tu@correo.com"

# Crear primer commit
git add .
git commit -m "chore: initial commit (streamlit + docker + config)"

# Establecer rama principal como 'main'
git branch -M main

# Agregar remoto (GitHub/GitLab/Bitbucket)
# Reemplaza <URL_REPO> por tu URL SSH o HTTPS
git remote add origin <URL_REPO>

# Publicar
git push -u origin main
```

## Buenas prácticas
- No subir secretos: `.env` y `.streamlit/secrets.toml` están en `.gitignore`.
- Usar `.dockerignore` para reducir el contexto de build.
- Añadir `restart: unless-stopped` en `docker-compose.yml` para resiliencia.
- Opcional: configurar un proxy (Nginx/Traefik) con TLS si expones públicamente.
- Etiquetar versiones con tags (`git tag v1.0.0 && git push --tags`).
