"""Kit de Sobrevivência Médico — guia doméstico de sintomas → medicação.

Aplicação web (Flask), em português, para uso doméstico. Separadores:
  • Sintomas — o que tomar para cada sintoma (dose, frequência, máximos).
  • Medicamentos — ficha de cada medicamento de venda livre + avisos.
  • Pediátrico — calculadora de dose por peso (paracetamol / ibuprofeno).
  • Primeiros Socorros — passos rápidos para emergências comuns.
  • Inventário — o que tens em casa e validades (guardado no servidor).

NÃO substitui aconselhamento médico/farmacêutico. Corre no porto 8001.
"""

import json
import os
import tempfile
import unicodedata
import uuid
from pathlib import Path

from flask import Flask, jsonify, render_template_string, request

app = Flask(__name__)

DATA_DIR = Path(os.environ.get("DATA_DIR", Path(__file__).with_name("data")))
DATA_DIR.mkdir(parents=True, exist_ok=True)
INV_FILE = DATA_DIR / "inventory.json"


# --- Medicamentos (doses para ADULTOS saudáveis salvo indicação) -------------
MEDS = {
    "paracetamol": {
        "nome": "Paracetamol — Ben-u-ron", "substancia": "Paracetamol",
        "classe": "Analgésico e antipirético",
        "dose": "500–1000 mg por toma", "freq": "a cada 6–8 h", "max": "máx. 3 g por dia",
        "notas": "1ª escolha para dor ligeira a moderada e febre. Com ou sem comida.",
        "avisos": "Não tomar com outros medicamentos que contenham paracetamol (muitos "
                  "antigripais têm). Cuidado com doença do fígado e álcool.",
        "ped": "15 mg/kg por toma, a cada 6 h (máx. 4 tomas/dia).",
    },
    "ibuprofeno": {
        "nome": "Ibuprofeno — Brufen / Nurofen", "substancia": "Ibuprofeno",
        "classe": "Anti-inflamatório (AINE)",
        "dose": "200–400 mg por toma", "freq": "a cada 6–8 h",
        "max": "máx. 1200 mg por dia (sem receita)",
        "notas": "Útil quando há inflamação: dor muscular, dentária, menstrual, febre. "
                 "Sempre com ou após comida.",
        "avisos": "Evitar com úlcera/azia, problemas renais ou cardíacos, asma agravada por "
                  "AINEs e na gravidez (sobretudo 3º trimestre). Não combinar com outros AINEs.",
        "ped": "10 mg/kg por toma, a cada 8 h. A partir dos 3 meses e >5–6 kg.",
    },
    "aspirina": {
        "nome": "Ácido acetilsalicílico — Aspirina", "substancia": "Ácido acetilsalicílico (AAS)",
        "classe": "Analgésico / antipirético / anti-inflamatório",
        "dose": "500 mg por toma", "freq": "a cada 4–6 h", "max": "máx. 3 g por dia",
        "notas": "Alternativa para dor/febre em adultos. Tomar com comida.",
        "avisos": "NÃO dar a menores de 16 anos (risco de síndrome de Reye). Maior risco de "
                  "hemorragia — em geral prefira paracetamol ou ibuprofeno.",
    },
    "fluimucil": {
        "nome": "Acetilcisteína — Fluimucil", "substancia": "Acetilcisteína",
        "classe": "Mucolítico (fluidifica o catarro)",
        "dose": "600 mg (ou 200 mg 3x/dia)", "freq": "1x/dia, de manhã",
        "max": "conforme a apresentação",
        "notas": "Para tosse COM expetoração/catarro. Beba bastante água.",
        "avisos": "Não usar em tosse seca. Não tomar ao fim do dia. Não combinar com antitússicos.",
    },
    "antitussico": {
        "nome": "Antitússico — Dextrometorfano (xarope)", "substancia": "Dextrometorfano",
        "classe": "Suprime a tosse seca",
        "dose": "conforme rótulo (ex.: 15 mg)", "freq": "a cada 6–8 h", "max": "conforme rótulo",
        "notas": "Apenas para tosse SECA e irritativa que perturba o descanso.",
        "avisos": "Não usar em tosse com expetoração nem com mucolíticos.",
    },
    "biafine": {
        "nome": "Biafine — emulsão cutânea", "substancia": "Trolamina",
        "classe": "Tópico para queimaduras / vermelhidão",
        "dose": "camada generosa, massajar", "freq": "1–3x/dia", "max": "—",
        "notas": "Queimaduras solares ligeiras, eritema e escoriações superficiais em pele intacta.",
        "avisos": "Não aplicar em feridas a sangrar, infetadas ou queimaduras graves.",
    },
    "antihistaminico": {
        "nome": "Anti-histamínico — Cetirizina / Loratadina", "substancia": "Cetirizina ou Loratadina",
        "classe": "Anti-histamínico (alergias)",
        "dose": "10 mg", "freq": "1x/dia", "max": "1 comprimido/dia",
        "notas": "Alergias, rinite, urticária, comichão e picadas. Pouco sedativos.",
        "avisos": "A cetirizina pode dar alguma sonolência — cuidado a conduzir.",
        "ped": "Existem soluções pediátricas (ex.: cetirizina em gotas) — confirme dose por idade/peso na bula.",
    },
    "loperamida": {
        "nome": "Loperamida — Imodium", "substancia": "Loperamida", "classe": "Antidiarreico",
        "dose": "4 mg ao início, depois 2 mg após cada dejeção líquida",
        "freq": "conforme necessidade", "max": "máx. 8 mg/dia (sem receita)",
        "notas": "Diarreia aguda. Acompanhar sempre com líquidos / soro de reidratação.",
        "avisos": "NÃO usar se houver febre alta ou sangue nas fezes, nem em crianças pequenas sem médico.",
    },
    "soro_oral": {
        "nome": "Soro de reidratação oral — Dioralyte / Redrate", "substancia": "Sais de reidratação",
        "classe": "Reidratação",
        "dose": "1 saqueta dissolvida em água", "freq": "após cada dejeção/vómito",
        "max": "conforme necessidade",
        "notas": "Essencial em diarreia e vómitos, sobretudo em crianças e idosos.",
        "avisos": "Se não conseguir reter líquidos ou houver sinais de desidratação, procure médico.",
    },
    "antiacido": {
        "nome": "Antiácido — Gaviscon / Kompensan", "substancia": "Alginato / sais antiácidos",
        "classe": "Antiácido (alívio rápido)",
        "dose": "conforme rótulo", "freq": "após refeições e ao deitar", "max": "conforme rótulo",
        "notas": "Alívio rápido de azia e refluxo ocasionais.",
        "avisos": "Se for frequente (>2x/semana) ou persistente, fale com médico.",
    },
    "omeprazol": {
        "nome": "Omeprazol", "substancia": "Omeprazol", "classe": "Protetor gástrico (IBP)",
        "dose": "20 mg", "freq": "1x/dia antes do pequeno-almoço", "max": "até 14 dias sem receita",
        "notas": "Para azia/refluxo frequentes; efeito ao fim de 1–3 dias.",
        "avisos": "Se persistir após 14 dias, consulte o médico.",
    },
    "buscopan": {
        "nome": "Butilescopolamina — Buscopan", "substancia": "Butilescopolamina",
        "classe": "Antiespasmódico",
        "dose": "10–20 mg (1–2 comp.)", "freq": "até 3x/dia", "max": "conforme rótulo",
        "notas": "Cólicas abdominais e menstruais.",
        "avisos": "Não usar em dor abdominal intensa e persistente sem avaliação.",
    },
    "diclofenac_gel": {
        "nome": "Diclofenac gel — Voltaren Emulgel", "substancia": "Diclofenac (tópico)",
        "classe": "Anti-inflamatório tópico",
        "dose": "fina camada, massajar", "freq": "3–4x/dia", "max": "—",
        "notas": "Dores musculares e articulares, contusões e entorses ligeiras.",
        "avisos": "Pele intacta; lavar as mãos depois; evitar sol na zona aplicada.",
    },
    "garganta": {
        "nome": "Pastilhas/Spray para a garganta — Strepsils", "substancia": "Anti-séptico/anestésico local",
        "classe": "Alívio da dor de garganta",
        "dose": "1 pastilha", "freq": "a cada 2–3 h", "max": "conforme rótulo",
        "notas": "Alívio local da irritação e dor de garganta.",
        "avisos": "Se febre alta, placas de pus ou >5 dias, ver médico.",
    },
    "nasal": {
        "nome": "Soro fisiológico + Descongestionante — Nasex", "substancia": "Cloreto de sódio / Xilometazolina",
        "classe": "Congestão nasal",
        "dose": "lavagem com soro; spray se necessário", "freq": "soro: várias vezes; spray: 1–2x/dia",
        "max": "spray: máx. 5–7 dias",
        "notas": "Comece pela lavagem com soro/água do mar.",
        "avisos": "Não use o spray mais de uma semana (efeito de ressalto piora a congestão).",
    },
    "antissetico": {
        "nome": "Antisséptico — Betadine / Clorohexidina", "substancia": "Iodopovidona / Clorohexidina",
        "classe": "Limpeza de feridas",
        "dose": "limpar e desinfetar", "freq": "1–2x/dia até cicatrizar", "max": "—",
        "notas": "Cortes e feridas superficiais: lavar com água, desinfetar e cobrir.",
        "avisos": "Feridas profundas, sujas, mordeduras ou que não param de sangrar → médico (e tétano).",
    },
    "hidrocortisona": {
        "nome": "Hidrocortisona creme 1%", "substancia": "Hidrocortisona (tópico)",
        "classe": "Corticoide tópico fraco",
        "dose": "fina camada", "freq": "1–2x/dia, poucos dias", "max": "—",
        "notas": "Comichão, picadas de inseto, dermatite e irritação ligeira.",
        "avisos": "Não usar na cara nem zonas extensas por longos períodos sem médico; não em pele infetada.",
    },
}


SINTOMAS = [
    {"sintoma": "Dor de cabeça", "icone": "🤕", "meds": ["paracetamol", "ibuprofeno"],
     "nota": "Descanse, hidrate-se e reduza ecrãs/ruído.",
     "medico_se": "for súbita e muito intensa (a pior de sempre), com febre alta e pescoço rígido, "
                  "após pancada na cabeça, ou com alterações da visão, fala ou força."},
    {"sintoma": "Febre", "icone": "🌡️", "meds": ["paracetamol", "ibuprofeno"],
     "nota": "Hidrate-se bem, descanse, roupa leve.",
     "medico_se": "passar dos 39–40 °C sem ceder, durar +3 dias, ou houver falta de ar, confusão ou "
                  "manchas na pele. Em bebés <3 meses, qualquer febre."},
    {"sintoma": "Dor de corpo / muscular", "icone": "💪", "meds": ["paracetamol", "ibuprofeno", "diclofenac_gel"],
     "nota": "Repouso e calor local ajudam.",
     "medico_se": "for após lesão grave, com inchaço importante, ou não melhorar em alguns dias."},
    {"sintoma": "Dor de dentes", "icone": "🦷", "meds": ["ibuprofeno", "paracetamol"],
     "nota": "Bochechos com água morna e sal podem aliviar.",
     "medico_se": "houver inchaço da face ou febre → dentista/médico."},
    {"sintoma": "Dor de garganta", "icone": "😣", "meds": ["garganta", "ibuprofeno", "paracetamol"],
     "nota": "Líquidos mornos, repouso da voz.",
     "medico_se": "houver dificuldade em engolir/respirar, placas de pus, febre alta, ou +5–7 dias."},
    {"sintoma": "Constipação / Gripe", "icone": "🤧", "meds": ["paracetamol", "nasal", "garganta", "fluimucil"],
     "nota": "Repouso, líquidos e paciência (5–7 dias).",
     "medico_se": "houver falta de ar, dor no peito, ou febre alta persistente."},
    {"sintoma": "Tosse com expetoração", "icone": "🫁", "meds": ["fluimucil"],
     "nota": "Beba muita água para soltar o catarro.",
     "medico_se": "houver sangue, falta de ar, ou durar +2–3 semanas."},
    {"sintoma": "Tosse seca", "icone": "🌬️", "meds": ["antitussico"],
     "nota": "Mel (em adultos) e ar húmido ajudam.",
     "medico_se": "for persistente, com falta de ar ou perda de peso."},
    {"sintoma": "Congestão nasal", "icone": "👃", "meds": ["nasal", "antihistaminico"],
     "nota": "Lavagem nasal com soro é o 1º passo.",
     "medico_se": "durar +10 dias ou houver dor facial/febre (sinusite)."},
    {"sintoma": "Alergia / Comichão", "icone": "🌼", "meds": ["antihistaminico", "hidrocortisona"],
     "nota": "Afaste-se do que provoca a alergia.",
     "medico_se": "houver inchaço da boca/garganta ou dificuldade em respirar → 112 já."},
    {"sintoma": "Diarreia", "icone": "🚽", "meds": ["soro_oral", "loperamida"],
     "nota": "Hidratação é o mais importante. Dieta leve.",
     "medico_se": "houver sangue nas fezes, febre alta, sinais de desidratação, ou +3 dias."},
    {"sintoma": "Náuseas / Vómitos", "icone": "🤢", "meds": ["soro_oral"],
     "nota": "Líquidos aos golinhos e comida leve.",
     "medico_se": "forem persistentes, com sangue, dor abdominal intensa ou desidratação."},
    {"sintoma": "Azia / Refluxo", "icone": "🔥", "meds": ["antiacido", "omeprazol"],
     "nota": "Evite refeições pesadas, álcool e deitar logo após comer.",
     "medico_se": "for frequente, houver dificuldade a engolir, perda de peso ou dor no peito."},
    {"sintoma": "Cólicas abdominais / menstruais", "icone": "🩸", "meds": ["buscopan", "ibuprofeno"],
     "nota": "Calor local (saco de água quente) ajuda muito.",
     "medico_se": "a dor for intensa e persistente, com febre ou vómitos."},
    {"sintoma": "Queimadura solar", "icone": "☀️", "meds": ["biafine", "ibuprofeno", "antihistaminico"],
     "nota": "Arrefeça a pele, hidrate-se, evite mais sol.",
     "medico_se": "houver bolhas extensas, febre, ou queimadura grande/em crianças."},
    {"sintoma": "Queimadura ligeira", "icone": "🔥", "meds": ["biafine", "paracetamol"],
     "nota": "Água corrente 10–20 min. NÃO use gelo nem rebente bolhas.",
     "medico_se": "for profunda, extensa, na cara/mãos/genitais, ou com bolhas grandes."},
    {"sintoma": "Feridas / Cortes", "icone": "🩹", "meds": ["antissetico"],
     "nota": "Lavar, desinfetar, comprimir se sangrar e cobrir.",
     "medico_se": "for profunda, não parar de sangrar, ou for mordedura → médico (e tétano)."},
    {"sintoma": "Picadas de inseto", "icone": "🦟", "meds": ["hidrocortisona", "antihistaminico"],
     "nota": "Lave a zona; gelo num pano reduz o inchaço.",
     "medico_se": "houver reação alérgica grave (inchaço da boca/garganta, falta de ar) → 112."},
]


PRIMEIROS_SOCORROS = [
    {"titulo": "Engasgamento", "icone": "🫁", "passos": [
        "Incentive a pessoa a tossir com força.",
        "Se não respira/fala: 5 pancadas firmes entre as omoplatas com a base da mão.",
        "Depois 5 compressões abdominais (manobra de Heimlich). Alterne 5 e 5.",
        "Bebé <1 ano: 5 pancadas nas costas + 5 compressões no peito (nunca Heimlich).",
        "Se ficar inconsciente: deite, ligue 112 e inicie compressões (RCP)."],
     "e112": "não desobstruir ou a pessoa perder a consciência."},
    {"titulo": "Hemorragia / corte profundo", "icone": "🩸", "passos": [
        "Pressione diretamente a ferida com um pano limpo.",
        "Eleve o membro acima do nível do coração, se possível.",
        "Se ensopar, ponha mais panos por cima — não retire os de baixo.",
        "Não retire objetos cravados; estabilize-os à volta."],
     "e112": "o sangue sair em jato, não parar, ou a ferida for grande/profunda."},
    {"titulo": "Desmaio", "icone": "😵", "passos": [
        "Deite a pessoa e eleve-lhe as pernas ~30 cm.",
        "Afrouxe a roupa apertada e garanta ar fresco.",
        "Ao recuperar, levante-a devagar."],
     "e112": "não recuperar em 1–2 min, houver dor no peito, traumatismo, ou for grávida."},
    {"titulo": "Reação alérgica grave (anafilaxia)", "icone": "⚠️", "passos": [
        "Sinais: inchaço da boca/garganta, falta de ar, urticária generalizada, tonturas.",
        "Use JÁ a caneta de adrenalina (EpiPen) na parte de fora da coxa, se tiver.",
        "Ligue 112 imediatamente.",
        "Deite com pernas elevadas (ou sentado se faltar o ar)."],
     "e112": "suspeitar de anafilaxia — ligue de imediato, mesmo após a adrenalina."},
    {"titulo": "Paragem cardíaca (RCP)", "icone": "🫀", "passos": [
        "Não responde e não respira normalmente → ligue 112 em alta-voz.",
        "Compressões no centro do peito: 100–120/min, ~5–6 cm de profundidade.",
        "Deixe o peito subir entre compressões; não pare.",
        "Use o DAE (desfibrilhador) assim que houver um."],
     "e112": "sempre — antes de começar as compressões."},
    {"titulo": "Convulsão", "icone": "⚡", "passos": [
        "Proteja a cabeça e afaste objetos perigosos.",
        "NÃO segure a pessoa nem ponha nada na boca.",
        "Quando possível, vire-a de lado. Cronometre a duração."],
     "e112": "durar +5 min, repetir, for a primeira vez, ou houver lesão/grávida."},
    {"titulo": "Queimadura", "icone": "🔥", "passos": [
        "Água corrente fria 10–20 min (nunca gelo).",
        "Retire anéis/relógios antes de inchar.",
        "Não rebente bolhas; cubra com pano limpo ou película aderente."],
     "e112": "for extensa, profunda, na cara/mãos/genitais, ou elétrica/química."},
    {"titulo": "Intoxicação / ingestão", "icone": "💊", "passos": [
        "NÃO provoque o vómito.",
        "Guarde a embalagem do que foi ingerido para identificar.",
        "Ligue ao CIAV (Centro de Informação Antivenenos): 800 250 250."],
     "e112": "estiver inconsciente, com convulsões ou dificuldade respiratória."},
    {"titulo": "Traumatismo / entorse", "icone": "🦴", "passos": [
        "RICE: Repouso, Gelo (envolto em pano), Compressão e Elevação.",
        "Não force nem alinhe o membro.",
        "Imobilize como estiver, se houver suspeita de fratura."],
     "e112": "houver deformidade, não conseguir apoiar/mover, ou dormência."},
]


def _fold(text):
    return "".join(c for c in unicodedata.normalize("NFD", text.lower())
                   if unicodedata.category(c) != "Mn")


def _sintomas():
    out = []
    for s in SINTOMAS:
        meds = [dict(MEDS[k], key=k) for k in s["meds"] if k in MEDS]
        terms = [s["sintoma"]] + [m["nome"] for m in meds] + [m["substancia"] for m in meds]
        out.append({**s, "meds": meds, "search": _fold(" ".join(terms))})
    return out


def _meds_ref():
    return [dict(v, key=k, search=_fold(v["nome"] + " " + v["substancia"] + " " + v["classe"]))
            for k, v in MEDS.items()]


def _socorros():
    return [dict(s, search=_fold(s["titulo"] + " " + " ".join(s["passos"]))) for s in PRIMEIROS_SOCORROS]


# --- Inventário (persistido em /data) ----------------------------------------
def read_inv():
    try:
        data = json.loads(INV_FILE.read_text())
        return data if isinstance(data, list) else []
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def write_inv(items):
    with tempfile.NamedTemporaryFile("w", dir=INV_FILE.parent, delete=False) as tmp:
        json.dump(items, tmp, ensure_ascii=False, indent=2)
        tmp_name = tmp.name
    os.replace(tmp_name, INV_FILE)


@app.route("/api/inventory")
def api_inventory():
    return jsonify(read_inv())


@app.route("/api/inventory/add", methods=["POST"])
def api_inventory_add():
    d = request.get_json(silent=True) or request.form
    nome = (d.get("nome") or "").strip()
    if not nome:
        return jsonify({"ok": False, "erro": "Indique o nome do medicamento."}), 400
    validade = (d.get("validade") or "").strip()
    try:
        qty = max(1, int(d.get("qty") or 1))
    except (TypeError, ValueError):
        qty = 1
    items = read_inv()
    items.append({"id": uuid.uuid4().hex[:10], "nome": nome, "validade": validade, "qty": qty})
    write_inv(items)
    return jsonify(items)


@app.route("/api/inventory/delete", methods=["POST"])
def api_inventory_delete():
    d = request.get_json(silent=True) or request.form
    item_id = (d.get("id") or "").strip()
    items = [it for it in read_inv() if it.get("id") != item_id]
    write_inv(items)
    return jsonify(items)


PAGE = r"""<!doctype html>
<html lang="pt">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Kit Médico Caseiro</title>
  <link rel="icon" type="image/svg+xml" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' rx='7' fill='%231f9d57'/%3E%3Cpath d='M13 6h6v7h7v6h-7v7h-6v-7H6v-6h7z' fill='%23fff'/%3E%3C/svg%3E">
  <style>
    :root {
      --bg:#eef1f6; --card:#fff; --text:#16202e; --muted:#67748a; --border:#e2e7ef;
      --shadow:0 1px 3px rgba(20,30,50,.08),0 1px 2px rgba(20,30,50,.04);
      --accent:#1f9d57; --accent-bg:#1f9d5715; --red:#d24b3a; --red-bg:#d24b3a16;
      --amber:#c98a12; --amber-bg:#c98a1216;
    }
    @media (prefers-color-scheme: dark) {
      :root { --bg:#0e131b; --card:#19212c; --text:#e8eef6; --muted:#90a0b6; --border:#28323f;
        --shadow:0 1px 2px rgba(0,0,0,.4); --accent:#34c884; --accent-bg:#34c8841f; --red:#ef6a59;
        --red-bg:#ef6a591f; --amber:#e0a93b; --amber-bg:#e0a93b1f; }
    }
    * { box-sizing:border-box; }
    body { margin:0; background:var(--bg); color:var(--text); line-height:1.5;
      font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif; }
    .wrap { max-width:1100px; margin:0 auto; padding:1.1rem 1rem 3rem; }
    header h1 { margin:.2rem 0 .1rem; font-size:1.5rem; }
    header p { margin:0; color:var(--muted); font-size:.9rem; }
    .disclaimer { background:var(--red-bg); border:1px solid var(--red); border-radius:12px;
      padding:.7rem .9rem; margin:.9rem 0; font-size:.86rem; }
    .disclaimer b { color:var(--red); }
    .tabs { display:flex; gap:.4rem; flex-wrap:wrap; margin:.6rem 0 1rem; position:sticky; top:0;
      background:var(--bg); padding:.5rem 0; z-index:5; }
    .tab { font-size:.9rem; font-weight:700; padding:.5rem .85rem; border-radius:999px; cursor:pointer;
      border:1px solid var(--border); background:var(--card); color:var(--muted); }
    .tab.on { background:var(--accent); color:#fff; border-color:var(--accent); }
    .search { width:100%; padding:.7rem .9rem; font-size:1rem; border-radius:12px;
      border:1px solid var(--border); background:var(--card); color:var(--text);
      box-shadow:var(--shadow); margin:0 0 1rem; }
    .grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(330px,1fr)); gap:.8rem; }
    .card { background:var(--card); border:1px solid var(--border); border-radius:14px;
      box-shadow:var(--shadow); padding:.85rem .95rem; }
    .top { display:flex; align-items:center; gap:.5rem; }
    .top .ico { font-size:1.4rem; }
    .top h3 { margin:0; font-size:1.08rem; }
    .nota { color:var(--muted); font-size:.84rem; margin:.35rem 0 .5rem; }
    .med { border-top:1px solid var(--border); padding:.5rem 0 .2rem; }
    .med .n { font-weight:700; font-size:.92rem; }
    .d { display:flex; flex-wrap:wrap; gap:.3rem; margin:.3rem 0; }
    .pill { font-size:.74rem; font-weight:700; padding:.12rem .5rem; border-radius:999px;
      background:var(--accent-bg); color:var(--accent); border:1px solid var(--accent); }
    .pill.max { background:var(--amber-bg); color:var(--amber); border-color:var(--amber); }
    .pill.ped { background:transparent; }
    .obs { font-size:.8rem; color:var(--muted); }
    .flag { margin-top:.6rem; font-size:.82rem; background:var(--amber-bg); border:1px solid var(--amber);
      border-radius:10px; padding:.4rem .55rem; }
    .flag b { color:var(--amber); }
    .warn { font-size:.83rem; color:var(--red); margin-top:.35rem; }
    .sub { color:var(--muted); font-size:.82rem; }
    .empty { color:var(--muted); padding:1rem; }
    ol.passos { margin:.4rem 0 .2rem; padding-left:1.1rem; font-size:.88rem; }
    ol.passos li { margin:.2rem 0; }
    .e112 { margin-top:.5rem; font-size:.82rem; background:var(--red-bg); border:1px solid var(--red);
      border-radius:10px; padding:.4rem .55rem; }
    .e112 b { color:var(--red); }
    .calc { display:flex; flex-direction:column; gap:.6rem; max-width:520px; }
    .calc label { font-size:.86rem; font-weight:600; }
    .calc input { width:100%; padding:.55rem .7rem; font-size:1rem; border-radius:10px;
      border:1px solid var(--border); background:var(--bg); color:var(--text); }
    .res { font-size:.95rem; }
    .res .big { font-size:1.2rem; font-weight:800; color:var(--accent); }
    .btn { padding:.55rem .9rem; border-radius:10px; border:1px solid var(--accent); cursor:pointer;
      background:var(--accent); color:#fff; font-weight:700; font-size:.9rem; }
    .btn.ghost { background:transparent; color:var(--accent); }
    .row { display:flex; gap:.5rem; flex-wrap:wrap; align-items:end; }
    .field { display:flex; flex-direction:column; gap:.2rem; }
    .field input { padding:.55rem .7rem; font-size:1rem; border-radius:10px; border:1px solid var(--border);
      background:var(--card); color:var(--text); }
    .inv-group { margin-bottom:.7rem; }
    .inv-group h4 { margin:.2rem 0 .35rem; font-size:1rem; }
    .inv-item { display:flex; align-items:center; gap:.5rem; padding:.35rem .55rem; border-radius:10px;
      border:1px solid var(--border); background:var(--card); margin:.25rem 0; }
    .inv-item .v { font-weight:700; font-size:.84rem; padding:.1rem .5rem; border-radius:999px;
      border:1px solid var(--border); }
    .v.ok { color:var(--accent); border-color:var(--accent); background:var(--accent-bg); }
    .v.soon { color:var(--amber); border-color:var(--amber); background:var(--amber-bg); }
    .v.exp { color:var(--red); border-color:var(--red); background:var(--red-bg); }
    .v.none { color:var(--muted); }
    .inv-item .x { margin-left:auto; cursor:pointer; color:var(--muted); border:none; background:none;
      font-size:1.1rem; line-height:1; padding:.1rem .35rem; }
    .inv-item .x:hover { color:var(--red); }
    .quick { font-size:.74rem; font-weight:700; padding:.1rem .45rem; border-radius:999px; cursor:pointer;
      border:1px solid var(--border); background:transparent; color:var(--muted); margin-top:.4rem; }
    .quick:hover { border-color:var(--accent); color:var(--accent); }
    .hide { display:none; }
    footer { margin-top:2rem; text-align:center; color:var(--muted); font-size:.82rem; }
    .em { color:var(--red); font-weight:700; }
  </style>
</head>
<body>
<div class="wrap">
  <header>
    <h1>🩺 Kit Médico Caseiro</h1>
    <p>O que tomar em casa, doses pediátricas, primeiros socorros e o teu inventário.</p>
  </header>

  <div class="disclaimer">
    <b>⚠️ Aviso:</b> guia de referência, <b>não substitui</b> o médico ou farmacêutico. Doses para
    <b>adultos saudáveis</b> salvo indicação. As <b>doses pediátricas</b> são por peso e aproximadas —
    confirme sempre na <b>bula</b> e com profissional. Emergência: <span class="em">112</span> ·
    SNS 24: <b>808 24 24 24</b> · Antivenenos (CIAV): <b>800 250 250</b>.
  </div>

  <div class="tabs">
    <div class="tab on" data-tab="sintomas">🤒 Sintomas</div>
    <div class="tab" data-tab="medicamentos">💊 Medicamentos</div>
    <div class="tab" data-tab="pediatrico">🧒 Pediátrico</div>
    <div class="tab" data-tab="socorros">🚑 1ºs Socorros</div>
    <div class="tab" data-tab="inventario">🧰 Inventário</div>
  </div>

  <input id="q" class="search" type="search" autocomplete="off"
         placeholder="🔎 Pesquisar (ignora acentos)…">

  <!-- SINTOMAS -->
  <section id="sec-sintomas">
    <div class="grid">
      {% for s in sintomas %}
      <div class="card filt" data-search="{{ s.search }}">
        <div class="top"><span class="ico">{{ s.icone }}</span><h3>{{ s.sintoma }}</h3></div>
        {% if s.nota %}<div class="nota">{{ s.nota }}</div>{% endif %}
        {% for m in s.meds %}
        <div class="med">
          <div class="n">{{ m.nome }}</div>
          <div class="d">
            <span class="pill">{{ m.dose }}</span>
            <span class="pill">{{ m.freq }}</span>
            {% if m.max and m.max != '—' %}<span class="pill max">{{ m.max }}</span>{% endif %}
          </div>
          <div class="obs">{{ m.notas }}</div>
        </div>
        {% endfor %}
        <div class="flag"><b>Procure médico se:</b> {{ s.medico_se }}</div>
      </div>
      {% endfor %}
    </div>
  </section>

  <!-- MEDICAMENTOS -->
  <section id="sec-medicamentos" class="hide">
    <div class="grid">
      {% for m in meds %}
      <div class="card filt" data-search="{{ m.search }}">
        <div class="n" style="font-weight:700">{{ m.nome }}</div>
        <div class="sub">{{ m.classe }} · {{ m.substancia }}</div>
        <div class="d">
          <span class="pill">{{ m.dose }}</span>
          <span class="pill">{{ m.freq }}</span>
          {% if m.max and m.max != '—' %}<span class="pill max">{{ m.max }}</span>{% endif %}
        </div>
        {% if m.ped %}<div class="obs">🧒 Pediátrico: {{ m.ped }}</div>{% endif %}
        <div class="obs">{{ m.notas }}</div>
        <div class="warn">⚠️ {{ m.avisos }}</div>
        <button class="quick" data-add="{{ m.nome }}">＋ tenho em casa</button>
      </div>
      {% endfor %}
    </div>
  </section>

  <!-- PEDIATRICO -->
  <section id="sec-pediatrico" class="hide">
    <div class="card calc">
      <div><b>🧒 Calculadora de dose por peso</b></div>
      <div class="sub">As doses pediátricas são pelo <b>peso</b>, não pela idade. Insira o peso da
        criança. Opcionalmente, a concentração do xarope (vem na bula/frasco) para ver os mL.</div>
      <div class="field"><label>Peso da criança (kg)</label>
        <input id="peso" type="number" min="1" max="120" step="0.5" placeholder="ex.: 14"></div>
      <div class="row">
        <div class="field"><label>Conc. paracetamol (mg/mL)</label>
          <input id="cpar" type="number" step="1" placeholder="ex.: 40"></div>
        <div class="field"><label>Conc. ibuprofeno (mg/mL)</label>
          <input id="cibu" type="number" step="1" placeholder="ex.: 20"></div>
      </div>
      <div id="calcout" class="res sub">Insira o peso para calcular.</div>
      <div class="flag"><b>Importante:</b> use sempre a seringa/copo do próprio medicamento. Não exceder
        o máximo diário. <b>Ibuprofeno</b> só a partir dos 3 meses e &gt;5–6 kg. Em bebés pequenos ou
        com dúvidas, contacte o pediatra/farmacêutico ou a SNS 24 (808 24 24 24).</div>
    </div>
  </section>

  <!-- SOCORROS -->
  <section id="sec-socorros" class="hide">
    <div class="grid">
      {% for s in socorros %}
      <div class="card filt" data-search="{{ s.search }}">
        <div class="top"><span class="ico">{{ s.icone }}</span><h3>{{ s.titulo }}</h3></div>
        <ol class="passos">{% for p in s.passos %}<li>{{ p }}</li>{% endfor %}</ol>
        <div class="e112"><b>Ligue 112 se:</b> {{ s.e112 }}</div>
      </div>
      {% endfor %}
    </div>
  </section>

  <!-- INVENTARIO -->
  <section id="sec-inventario" class="hide">
    <div class="card" style="margin-bottom:1rem">
      <div class="row">
        <div class="field" style="flex:2 1 200px"><label>Medicamento</label>
          <input id="inv-nome" list="medlist" placeholder="ex.: Ben-u-ron 1000 mg"></div>
        <div class="field"><label>Validade</label>
          <input id="inv-val" type="month"></div>
        <div class="field" style="max-width:90px"><label>Qtd.</label>
          <input id="inv-qty" type="number" min="1" value="1"></div>
        <button class="btn" id="inv-add">＋ Adicionar</button>
      </div>
      <datalist id="medlist">{% for m in meds %}<option value="{{ m.nome }}">{% endfor %}</datalist>
      <div class="sub" style="margin-top:.5rem">Adiciona o que tens em casa. Podes ter vários do mesmo
        com validades diferentes — cada um é uma linha. Fica guardado no Pi.</div>
    </div>
    <div id="inv-list"></div>
  </section>

  <footer>
    Kit Médico Caseiro · informação geral de medicamentos de venda livre.<br>
    Em caso de dúvida fale com o farmacêutico · <span class="em">112</span> · SNS 24: <b>808 24 24 24</b>
  </footer>
</div>

<script>
  const fold = s => s.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
  const $ = id => document.getElementById(id);

  // --- Tabs ---
  const SEARCHABLE = {sintomas:1, medicamentos:1, socorros:1};
  function showTab(name) {
    document.querySelectorAll('.tab').forEach(t => t.classList.toggle('on', t.dataset.tab === name));
    ['sintomas','medicamentos','pediatrico','socorros','inventario'].forEach(s =>
      $('sec-' + s).classList.toggle('hide', s !== name));
    $('q').classList.toggle('hide', !SEARCHABLE[name]);
    if (name === 'inventario') loadInv();
  }
  document.querySelectorAll('.tab').forEach(t => t.addEventListener('click', () => showTab(t.dataset.tab)));

  // --- Pesquisa (filtra a secção ativa) ---
  $('q').addEventListener('input', () => {
    const term = fold($('q').value.trim());
    document.querySelectorAll('section:not(.hide) .filt').forEach(c => {
      c.style.display = (!term || c.dataset.search.includes(term)) ? '' : 'none';
    });
  });

  // --- Calculadora pediátrica ---
  function round5(x) { return Math.round(x / 5) * 5; }
  function calc() {
    const p = parseFloat($('peso').value);
    if (!p || p <= 0) { $('calcout').innerHTML = 'Insira o peso para calcular.'; return; }
    const cpar = parseFloat($('cpar').value), cibu = parseFloat($('cibu').value);
    const parDose = Math.min(round5(15 * p), 1000), parMax = Math.min(Math.round(60 * p), 3000);
    const ibuDose = Math.min(round5(10 * p), 400), ibuMax = Math.min(Math.round(30 * p), 1200);
    const ml = (mg, c) => (c && c > 0) ? ` (≈ ${(mg / c).toFixed(1).replace('.', ',')} mL)` : '';
    $('calcout').innerHTML =
      `<p><b>Paracetamol</b> (Ben-u-ron) — <span class="big">${parDose} mg</span>${ml(parDose, cpar)} por toma,
        a cada <b>6 h</b>. Máx. ~${parMax} mg/dia.</p>
       <p><b>Ibuprofeno</b> (Brufen) — <span class="big">${ibuDose} mg</span>${ml(ibuDose, cibu)} por toma,
        a cada <b>8 h</b>, com comida. Máx. ~${ibuMax} mg/dia.</p>
       <p class="sub">Valores arredondados (paracetamol 15 mg/kg; ibuprofeno 10 mg/kg). Não exceder a
        dose de adulto. Confirme na bula do seu frasco.</p>`;
  }
  ['peso','cpar','cibu'].forEach(id => $(id).addEventListener('input', calc));

  // --- Inventário ---
  function expClass(v) {
    if (!v) return 'none';
    const [y, m] = v.split('-').map(Number);
    if (!y || !m) return 'none';
    const end = new Date(y, m, 0), now = new Date();
    const days = (end - now) / 86400000;
    if (days < 0) return 'exp';
    if (days < 60) return 'soon';
    return 'ok';
  }
  function expLabel(v, cls) {
    if (!v) return 'sem validade';
    const txt = v.split('-').reverse().join('/');  // YYYY-MM -> MM/YYYY
    return (cls === 'exp' ? '⚠ expirado ' : (cls === 'soon' ? 'expira ' : 'val. ')) + txt;
  }
  async function loadInv() {
    let items = [];
    try { items = await (await fetch('/api/inventory')).json(); } catch (e) {}
    render(items);
  }
  function render(items) {
    const box = $('inv-list');
    if (!items.length) { box.innerHTML = '<div class="empty">Sem medicamentos no inventário. Adiciona o que tens em casa. 👆</div>'; return; }
    const groups = {};
    items.forEach(it => (groups[it.nome] = groups[it.nome] || []).push(it));
    box.innerHTML = Object.keys(groups).sort((a, b) => a.localeCompare(b, 'pt')).map(nome => {
      const rows = groups[nome].sort((a, b) => (a.validade || '').localeCompare(b.validade || '')).map(it => {
        const cls = expClass(it.validade);
        return `<div class="inv-item"><span class="v ${cls}">${expLabel(it.validade, cls)}</span>
          <span class="sub">${it.qty > 1 ? '×' + it.qty : ''}</span>
          <button class="x" data-del="${it.id}" title="remover">✕</button></div>`;
      }).join('');
      return `<div class="inv-group"><h4>${nome}</h4>${rows}</div>`;
    }).join('');
    box.querySelectorAll('.x').forEach(b => b.addEventListener('click', () => delItem(b.dataset.del)));
  }
  async function addItem() {
    const nome = $('inv-nome').value.trim();
    if (!nome) { $('inv-nome').focus(); return; }
    const body = { nome, validade: $('inv-val').value, qty: $('inv-qty').value };
    const r = await fetch('/api/inventory/add', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
    if (r.ok) { $('inv-nome').value = ''; $('inv-val').value = ''; $('inv-qty').value = '1';
      render(await r.json()); $('inv-nome').focus(); }
  }
  async function delItem(id) {
    const r = await fetch('/api/inventory/delete', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id }) });
    if (r.ok) render(await r.json());
  }
  $('inv-add').addEventListener('click', addItem);
  $('inv-nome').addEventListener('keydown', e => { if (e.key === 'Enter') addItem(); });

  // Quick-add a partir da ficha do medicamento
  document.querySelectorAll('.quick').forEach(b => b.addEventListener('click', () => {
    showTab('inventario'); $('inv-nome').value = b.dataset.add; $('inv-val').focus();
  }));
</script>
</body>
</html>"""


@app.route("/")
def index():
    return render_template_string(PAGE, sintomas=_sintomas(), meds=_meds_ref(), socorros=_socorros())


@app.route("/healthz")
def healthz():
    return {"ok": True}


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8001)
