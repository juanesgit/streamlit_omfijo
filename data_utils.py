import pandas as pd
import numpy as np


def postprocess_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    df["DIAS"] = pd.to_numeric(df.get("DIAS"), errors="coerce").round(1)
    df["FECHA_CREACION"] = pd.to_datetime(df.get("FECHA_CREACION"), errors="coerce")
    df["FECHA_INICIO_WF"] = pd.to_datetime(df.get("FECHA_INICIO_WF"), errors="coerce")
    df["TotalSegundos"] = (df["FECHA_INICIO_WF"] - df["FECHA_CREACION"]).dt.total_seconds()
    df["TotalSegundos"] = df["TotalSegundos"].fillna(0)
    df["Horas"] = (df["TotalSegundos"] // 3600).astype(int)
    df["Minutos"] = ((df["TotalSegundos"] % 3600) // 60).astype(int)
    df["INICIO(H)"] = np.where(
        (df["Horas"] == 0) & (df["Minutos"] == 0),
        "",
        df["Horas"].astype(str).str.zfill(2) + ":" + df["Minutos"].astype(str).str.zfill(2),
    )
    df.drop(columns=["TotalSegundos", "Horas", "Minutos"], inplace=True)
    if set(["INICIADO", "PENDIENTE", "SUSPENDIDO", "CANCELADO"]).issubset(df.columns):
        df["REPRO"] = (
            df[["INICIADO", "PENDIENTE", "SUSPENDIDO", "CANCELADO"]]
            .fillna(0)
            .sum(axis=1)
            .astype(int)
        )
    df.columns = df.columns.astype(str)
    df = df.reset_index(drop=True)
    return df
