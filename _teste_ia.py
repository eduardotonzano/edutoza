"""Teste manual do resumo por IA: manda 1 noticia de exemplo ao Gemini e imprime o
resultado. So serve para confirmar que GEMINI_API_KEY + o modelo funcionam.
Rodar: python _teste_ia.py
"""
import os, requests
from resumo_ia import preencher_resumos, ATIVADO, MODELO

print(f"IA ativada: {ATIVADO} | modelo: {MODELO}")

# Lista os modelos que ESTA chave aceita para generateContent (diagnostico).
chave = os.environ.get("GEMINI_API_KEY", "")
try:
    r = requests.get("https://generativelanguage.googleapis.com/v1beta/models",
                     params={"key": chave}, timeout=30)
    if r.status_code == 200:
        print("--- modelos disponiveis para generateContent ---")
        for m in r.json().get("models", []):
            if "generateContent" in m.get("supportedGenerationMethods", []):
                print(" ", m["name"].replace("models/", ""))
        print("--- fim da lista ---")
    else:
        print(f"ListModels HTTP {r.status_code}: {r.text[:200]}")
except Exception as e:
    print("ListModels erro:", str(e)[:120])

exemplo = [{
    "nome": "Suzano",
    "titulo": "Suzano giant pulp mill to exceed nominal capacity",
    "corpo": ("Suzano's new Ribas do Rio Pardo pulp mill is expected to exceed its "
              "nominal annual production capacity of 2.55 million tonnes, the company said, "
              "as ramp-up runs ahead of schedule and unit costs fall."),
    "resumo_ia": "", "impacto": "",
}]
n = preencher_resumos(exemplo)
print(f"resumos gerados: {n}")
print("RESUMO IA:", exemplo[0]["resumo_ia"] or "(vazio)")
print("IMPACTO  :", exemplo[0]["impacto"] or "(vazio)")
