import streamlit as st
import os
import sys


def mostrar_menu():
    current_script = os.path.basename(sys.modules["__main__"].__file__)

    # Define las rutas esperadas
    paginas = {
        "📊 Seguimiento Backlog": "seguimiento.py",
        "📋 Resumen Backlog": "pages/resumen.py",
    }

    # Usar el script actual para seleccionar la opción predeterminada
    for nombre, archivo in paginas.items():
        if current_script == os.path.basename(archivo):
            opcion_actual = nombre
            break
    else:
        opcion_actual = "Seguimiento Backlog"  # Fallback si no lo detecta

    with st.sidebar:
        opcion = st.selectbox(
            label="📁 Navegar a:",
            options=list(paginas.keys()),
            index=list(paginas.keys()).index(opcion_actual),
            key="menu_navegacion",
        )

    # Redirigir solo si cambió la opción
    if opcion != opcion_actual:
        st.switch_page(paginas[opcion])
