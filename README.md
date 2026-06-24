# 🩺 Kit Médico Caseiro

Guia doméstico de **sintomas → medicação** (dose, frequência, máximo diário e
quando ir ao médico). Pensado como um "kit de sobrevivência" para cuidar de nós
e dos nossos em casa, antes de ser preciso ir ao médico.

Aplicação web simples (Flask), página única, em português, com pesquisa por
sintoma ou medicamento (ignora acentos). Corre no **porto 8001**.

> ⚠️ **Aviso:** É apenas um guia de referência. **Não substitui** o médico nem o
> farmacêutico. As doses indicadas são para **adultos saudáveis** e podem não se
> aplicar ao seu caso. Em crianças, gravidez/amamentação, doenças crónicas ou
> medicação habitual, **pergunte sempre** e leia o **folheto informativo (bula)**.
> Emergência: **112** · Linha SNS 24: **808 24 24 24**.

## Sintomas cobertos
Dor de cabeça, febre, dor de corpo/muscular, dor de dentes, dor de garganta,
constipação/gripe, tosse (com expetoração e seca), congestão nasal, alergia/
comichão, diarreia, náuseas/vómitos, azia/refluxo, cólicas, queimadura solar e
ligeira, feridas/cortes e picadas de inseto.

## Correr localmente
```bash
pip install -r requirements.txt
python app.py        # http://localhost:8001
```

## Correr com Docker (no Raspberry Pi)
```bash
docker compose up -d --build
# Aceder em http://<ip-do-pi>:8001
```
