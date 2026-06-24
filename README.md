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

## 🆘 Deploy do zero (se o Raspberry Pi morrer)

Num Raspberry Pi novo com **Raspberry Pi OS (64-bit)** e SSH ligado:

1. Atualizar o sistema e instalar o Docker:
   ```bash
   sudo apt update && sudo apt upgrade -y
   curl -fsSL https://get.docker.com | sh
   sudo usermod -aG docker $USER && newgrp docker   # usar o docker sem sudo
   ```
2. Clonar este repositório e arrancar:
   ```bash
   git clone https://github.com/rafaeljhr/medicine.git
   cd medicine
   docker compose up -d --build
   ```
3. Aceder em **http://<ip-do-pi>:8001** (descobre o IP com `hostname -I`).

O serviço tem `restart: unless-stopped` e o Docker arranca no boot, por isso volta
a subir sozinho após reinícios ou falhas de energia.

### Backup / reposição dos dados
O inventário (medicamentos/validades) fica num volume Docker chamado `medicine_data`.

```bash
# backup -> cria backup.tar.gz na pasta atual
docker run --rm -v medicine_data:/data -v "$PWD":/backup alpine tar czf /backup/backup.tar.gz -C /data .

# repor a partir de backup.tar.gz
docker run --rm -v medicine_data:/data -v "$PWD":/backup alpine tar xzf /backup/backup.tar.gz -C /data
```

### Atualizar para a versão mais recente
```bash
cd medicine && git pull && docker compose up -d --build
```
