from fastapi import FastAPI
import joblib
import pandas as pd
import sys
from datetime import date, timedelta, datetime
from service.meteo_service import MeteoService
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4200"], # Ou ["*"] para liberar geral
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
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

@app.get("/prever-distrito/{distrito}")
def prever_distrito(distrito: str):
    df = pd.read_csv("data/trusted_district.csv", delimiter="|")
    df_drenagem = pd.read_csv(
        "data/trusted_drainage.csv", delimiter=";")
    linha = df[df['nome'] == distrito].iloc[0]
    lat = linha['lat']
    long = linha['long']
    data_atual = date.today()
    response = MeteoService(lat,long, data_atual, data_atual).get()
    clima_atual = MeteoService(lat,long, data_atual, data_atual).get_current()
    df_final = pd.DataFrame()
    df_resp = pd.DataFrame(response)
    df_resp['date'] = pd.to_datetime(df_resp['date'])
    df_final['mes'] = df_resp['date'].dt.month
    df_final['hora'] = df_resp['date'].dt.hour
    df_final['mm_chuva'] = df_resp['precipitation']
    df_final['lat'] = lat
    df_final['long'] = long
    qt_trechos = (
        df_drenagem.loc[
            df_drenagem['nome_distrito'] == distrito,
            'qt_trechos_drenagem'
        ].iloc[0]
    )
    df_final['qt_trechos_drenagem'] = qt_trechos
    colunas_modelo = [
        'qt_trechos_drenagem',
        'mm_chuva',
        'mes',
        'hora'
    ]
    df_final = df_final[colunas_modelo]
    probs = modelo.predict_proba(df_final)[:, 1]

    df_final['prob_alagamento'] = probs
    risco_dia = 0.7 * probs.max() + 0.3 * probs.mean()
    horarios = df_final[['hora', 'prob_alagamento']].to_dict(orient='records')

    return {
    "data": data_atual,
    "data_hora_captura": datetime.now(),
    "clima_atual": clima_atual,
    "probabilidade_dia": float(risco_dia),
    "nivel_risco": "Sem risco de Alagamento" if risco_dia < 0.49 else ("Baixo" if risco_dia < 0.5 else ("Médio" if risco_dia < 0.7 else "Alto")),
    "horarios": horarios
    # "horarios": df_final['hora'],
    # "probs": df_final['prob_alagamento']
}

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