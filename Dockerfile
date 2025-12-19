FROM python:3.10

WORKDIR /app

# Copiar todo el proyecto (incluye la carpeta streamlit_O&M)
COPY . /app

# Instalar dependencias
RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 8501

# Ejecutar dash.py dentro de la carpeta streamlit_O&M
CMD ["streamlit", "run", "seguimiento.py", "--server.port=8501", "--server.address=0.0.0.0"]




