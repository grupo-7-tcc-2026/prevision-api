from fastapi import FastAPI
import joblib
import pandas as pd
import sys

app = FastAPI()
app = FastAPI()

try:
    modelo = joblib.load('modelo.pkl')
    print("Modelo carregado com sucesso!")
except Exception as e:
    print(f"Erro fatal ao carregar o modelo: {e}")
    sys.exit(1) # Fecha o programa se o modelo não carregar

@app.get("/distritos")
def get_distritos():
    df = pd.read_csv("data/trusted_district.csv", delimiter="|")
    return df.to_dict(orient="records")

@app.post("/prever")
def prever_risco(dados: dict):
    df = pd.DataFrame([dados])
    df['data_hora'] = pd.to_datetime(df['data_hora'])
    df['mes'] = df['data_hora'].dt.month
    df['hora'] = df['data_hora'].dt.hour
    df_matriz = df.drop(['distrito', 'regiao', 'data_hora'], axis=1)
    prob = modelo.predict_proba(df_matriz)[0][1]

    # Lógica de risco que discutimos
    risco = "Sem risco de Alagamento" if prob < 0.49 else ("Baixo" if prob < 0.5 else ("Médio" if prob < 0.7 else "Alto"))
    return {"probabilidade": float(prob), "nivel_risco": risco}