"""Kit de Sobrevivência Médico — guia doméstico de sintomas → medicação.

Aplicação web (Flask), em português, para uso doméstico. Separadores:
  • Sintomas — o que tomar para cada sintoma (dose, frequência, máximos).
  • Medicamentos — ficha de cada medicamento de venda livre + avisos.
  • Pediátrico — calculadora de dose por peso (paracetamol / ibuprofeno).
  • Primeiros Socorros — passos rápidos para emergências comuns.
  • Inventário — o que tens em casa e validades (guardado no servidor).

NÃO substitui aconselhamento médico/farmacêutico. Corre no porto 8001.
"""

import base64
import json
import os
import tempfile
import unicodedata
import uuid
from pathlib import Path

from flask import Flask, jsonify, render_template_string, request, Response

app = Flask(__name__)

DATA_DIR = Path(os.environ.get("DATA_DIR", Path(__file__).with_name("data")))
DATA_DIR.mkdir(parents=True, exist_ok=True)
INV_FILE = DATA_DIR / "inventory.json"

# Categorias do inventário (separadores). "geral" é a genérica por omissão.
INV_CATS = [
    {"key": "medicamentos", "label": "Medicamentos", "icone": "💊", "validade": True},
    {"key": "pensos", "label": "Pensos & Material", "icone": "🩹", "validade": False},
    {"key": "geral", "label": "Geral", "icone": "🧰", "validade": True},
]
INV_CAT_KEYS = {c["key"] for c in INV_CATS}


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
    except (FileNotFoundError, json.JSONDecodeError):
        return []
    if not isinstance(data, list):
        return []
    for it in data:
        if "cat" not in it:          # itens antigos eram medicamentos
            it["cat"] = "medicamentos"
        if "stock" not in it:        # qty antigo -> stock; novo campo "uso"
            it["stock"] = it.get("qty", 1)
        if "uso" not in it:
            it["uso"] = 0
        it.pop("qty", None)
    return data


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
    cat = (d.get("cat") or "geral").strip()
    if cat not in INV_CAT_KEYS:
        cat = "geral"
    items = read_inv()
    items.append({"id": uuid.uuid4().hex[:10], "nome": nome, "cat": cat,
                  "validade": validade, "stock": 1, "uso": 0})
    write_inv(items)
    return jsonify(items)


@app.route("/api/inventory/qty", methods=["POST"])
def api_inventory_qty():
    d = request.get_json(silent=True) or request.form
    item_id = (d.get("id") or "").strip()
    campo = d.get("campo")
    if campo not in ("stock", "uso"):
        return jsonify({"ok": False}), 400
    try:
        delta = int(d.get("delta", 0))
    except (TypeError, ValueError):
        delta = 0
    items = read_inv()
    for it in items:
        if it.get("id") == item_id:
            it[campo] = max(0, int(it.get(campo, 0)) + delta)
            break
    write_inv(items)
    return jsonify(items)


@app.route("/api/inventory/delete", methods=["POST"])
def api_inventory_delete():
    d = request.get_json(silent=True) or request.form
    item_id = (d.get("id") or "").strip()
    items = [it for it in read_inv() if it.get("id") != item_id]
    write_inv(items)
    return jsonify(items)


APPLE_ICON_PNG = base64.b64decode(
    "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")


@app.route("/apple-touch-icon.png")
def apple_touch_icon():
    return Response(APPLE_ICON_PNG, mimetype="image/png")


PAGE = r"""<!doctype html>
<html lang="pt">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Kit Médico Caseiro</title>
  <link rel="apple-touch-icon" href="/apple-touch-icon.png">
  <meta name="apple-mobile-web-app-capable" content="yes">
  <meta name="apple-mobile-web-app-title" content="Kit Médico">
  <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
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
    .tab { font-size:.9rem; font-weight:700; padding:.5rem .85rem; border-radius:999px; cursor:grab;
      border:1px solid var(--border); background:var(--card); color:var(--muted);
      touch-action:none; user-select:none; -webkit-user-select:none; }
    .tab.on { background:var(--accent); color:#fff; border-color:var(--accent); }
    .tab.dragging { opacity:.55; cursor:grabbing; }
    .grip { opacity:.4; margin-right:.2rem; font-size:.95em; letter-spacing:-2px; }
    .tab.on .grip { opacity:.75; }
    .itabs { display:flex; gap:.4rem; flex-wrap:wrap; margin-bottom:.6rem; }
    .itab { font-size:.85rem; font-weight:700; padding:.4rem .7rem; border-radius:999px; cursor:pointer;
      border:1px solid var(--border); background:var(--card); color:var(--muted); display:inline-flex;
      align-items:center; gap:.3rem; }
    .itab.on { background:var(--accent); color:#fff; border-color:var(--accent); }
    .invhead { display:flex; justify-content:space-between; align-items:center; gap:.5rem; flex-wrap:wrap; margin-bottom:.4rem; }
    .level-title { font-size:.74rem; color:var(--muted); text-transform:uppercase; letter-spacing:.05em; font-weight:800; }
    .cart { display:flex; align-items:center; gap:.4rem; padding:.45rem .8rem; border-radius:999px;
      border:1px solid var(--accent); background:var(--accent); color:#fff; font-weight:800; cursor:pointer; font-size:.88rem; }
    .cart .badge { background:#fff; color:var(--accent); font-size:.72rem; font-weight:800; min-width:17px;
      text-align:center; padding:0 .28rem; border-radius:999px; }
    .ibadge { font-size:.7rem; font-weight:800; min-width:16px; text-align:center; padding:0 .26rem;
      border-radius:999px; background:var(--red); color:#fff; }
    .itab.on .ibadge { background:#fff; color:var(--red); }
    .inv-item.falta { border-color:var(--red); background:var(--red-bg); }
    .inv-item .info { flex:1; min-width:130px; font-weight:700; display:flex; align-items:center; gap:.4rem; flex-wrap:wrap; }
    .steppers { display:flex; gap:.6rem; flex-wrap:wrap; }
    .stp { display:flex; align-items:center; gap:.2rem; }
    .stp .lbl { font-size:.68rem; color:var(--muted); font-weight:700; }
    .sb { width:28px; height:28px; border-radius:8px; border:1px solid var(--border); background:var(--card);
      color:var(--text); font-size:1.1rem; line-height:1; cursor:pointer; font-weight:700; }
    .sb:hover { border-color:var(--accent); color:var(--accent); }
    .num { min-width:20px; text-align:center; font-weight:800; }
    .num.zero { color:var(--red); }
    .act.repor { border:1px solid var(--accent); background:var(--accent); color:#fff; border-radius:9px;
      padding:.4rem .6rem; cursor:pointer; font-weight:700; font-size:.82rem; }
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

  <div class="tabs" id="tabs">
    <div class="tab on" data-tab="sintomas">🤒 Sintomas</div>
    <div class="tab" data-tab="medicamentos">💊 Medicamentos</div>
    <div class="tab" data-tab="socorros">🚑 1ºs Socorros</div>
    <div class="tab" data-tab="pediatrico">🧒 Pediátrico</div>
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
    <div class="invhead">
      <div class="level-title">📂 Categorias do inventário</div>
      <button id="inv-cartbtn" class="cart">🛒 A comprar <span class="badge" id="inv-cartn">0</span></button>
    </div>
    <div class="itabs" id="invtabs">
      {% for c in inv_cats %}
      <div class="itab{% if loop.first %} on{% endif %}" data-inv="{{ c.key }}" data-val="{{ 1 if c.validade else 0 }}">{{ c.icone }} {{ c.label }} <span class="ibadge hide" id="ib-{{ c.key }}"></span></div>
      {% endfor %}
    </div>
    <div class="card" id="inv-addcard" style="margin:.7rem 0 1rem">
      <div class="row">
        <div class="field" style="flex:2 1 200px"><label>Item (em <b id="inv-catlabel">Medicamentos</b>)</label>
          <input id="inv-nome" list="medlist" placeholder="ex.: Ben-u-ron 1000 mg, Pensos rápidos…"></div>
        <div class="field" id="inv-valwrap"><label>Validade (opcional)</label>
          <input id="inv-val" type="date"></div>
        <button class="btn" id="inv-add">＋ Adicionar</button>
      </div>
      <datalist id="medlist">{% for m in meds %}<option value="{{ m.nome }}">{% endfor %}</datalist>
      <div class="sub" style="margin-top:.5rem">Cada item tem <b>stock</b> (reserva) e <b>em uso</b>; quando o
        stock chega a 0 vai para <b>A comprar</b>. A validade é opcional (pensos não têm).</div>
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
  function expEnd(v) {           // aceita AAAA-MM-DD (data) ou AAAA-MM (legado)
    const p = (v || '').split('-').map(Number);
    if (p.length >= 3 && p[0]) return new Date(p[0], p[1] - 1, p[2]);
    if (p.length === 2 && p[0]) return new Date(p[0], p[1], 0);  // fim do mês
    return null;
  }
  function expClass(v) {
    const end = expEnd(v);
    if (!end) return 'none';
    const days = (end - new Date()) / 86400000;
    if (days < 0) return 'exp';
    if (days < 60) return 'soon';
    return 'ok';
  }
  function expLabel(v, cls) {
    if (!v) return 'sem validade';
    const p = v.split('-');
    const txt = p.length >= 3 ? `${p[2]}/${p[1]}/${p[0]}` : `${p[1]}/${p[0]}`;
    return (cls === 'exp' ? '⚠ expirado ' : (cls === 'soon' ? 'expira ' : 'val. ')) + txt;
  }
  let invCat = 'medicamentos', invItems = [], invMode = 'cat', invPaused = false;
  const INV_LABELS = {}, INV_HASVAL = {}, CATKEYS = [];
  document.querySelectorAll('#invtabs .itab').forEach(t => {
    CATKEYS.push(t.dataset.inv);
    INV_LABELS[t.dataset.inv] = t.textContent.trim();
    INV_HASVAL[t.dataset.inv] = t.dataset.val === '1';
  });
  const invFalta = it => (it.stock || 0) === 0;
  function setInvCat(key) {
    invCat = key; invMode = 'cat';
    document.querySelectorAll('#invtabs .itab').forEach(t => t.classList.toggle('on', t.dataset.inv === key));
    $('inv-catlabel').textContent = (INV_LABELS[key] || '').replace(/^\S+\s/, '');
    $('inv-valwrap').classList.toggle('hide', !INV_HASVAL[key]);
    renderInv();
  }
  document.querySelectorAll('#invtabs .itab').forEach(t => t.addEventListener('click', () => setInvCat(t.dataset.inv)));
  $('inv-cartbtn').onclick = () => { invMode = invMode === 'lista' ? 'cat' : 'lista'; renderInv(); };

  function invStepper(id, campo, label, val) {
    return `<div class="stp"><span class="lbl">${label}</span>
      <button class="sb" data-iq="${id}|${campo}|-1">−</button>
      <span class="num ${campo === 'stock' && val === 0 ? 'zero' : ''}">${val}</span>
      <button class="sb" data-iq="${id}|${campo}|1">+</button></div>`;
  }
  function invRow(it) {
    const falta = invFalta(it);
    let chip = '';
    if (INV_HASVAL[it.cat]) { const cls = expClass(it.validade); chip = `<span class="v ${cls}">${expLabel(it.validade, cls)}</span>`; }
    return `<div class="inv-item ${falta ? 'falta' : ''}">
      <div class="info">${it.nome} ${falta ? '<span class="v exp">EM FALTA</span>' : chip}</div>
      <div class="steppers">${invStepper(it.id, 'stock', 'Stock', it.stock || 0)}${invStepper(it.id, 'uso', 'Em uso', it.uso || 0)}</div>
      <button class="x" data-del="${it.id}" title="remover">✕</button></div>`;
  }
  function invRowFalta(it) {
    return `<div class="inv-item falta"><div class="info">${it.nome}</div>
      <button class="act repor" data-ibuy="${it.id}">✓ Comprei (+1)</button>
      <button class="x" data-del="${it.id}" title="remover">✕</button></div>`;
  }
  async function loadInv() {
    if (invPaused) return;
    try { invItems = await (await fetch('/api/inventory')).json(); } catch (e) {}
    renderInv();
  }
  function renderInv() {
    let total = 0;
    CATKEYS.forEach(k => {
      const n = invItems.filter(i => (i.cat || 'geral') === k && invFalta(i)).length;
      const b = $('ib-' + k); if (b) { b.textContent = n; b.classList.toggle('hide', n === 0); } total += n;
    });
    $('inv-cartn').textContent = total;
    $('inv-addcard').classList.toggle('hide', invMode === 'lista');
    $('invtabs').classList.toggle('hide', invMode === 'lista');
    const box = $('inv-list');
    if (invMode === 'lista') {
      const falta = invItems.filter(invFalta);
      if (!falta.length) box.innerHTML = '<div class="empty">🎉 Nada em falta. Tudo com stock!</div>';
      else box.innerHTML = CATKEYS.map(k => {
        const sub = falta.filter(i => (i.cat || 'geral') === k);
        return sub.length ? `<div class="inv-group"><h4>${INV_LABELS[k]}</h4>${sub.map(invRowFalta).join('')}</div>` : '';
      }).join('');
    } else {
      let list = invItems.filter(i => (i.cat || 'geral') === invCat);
      list.sort((a, b) => (invFalta(b) - invFalta(a)) || a.nome.localeCompare(b.nome, 'pt'));
      box.innerHTML = list.length ? list.map(invRow).join('')
        : `<div class="empty">Nada em "${(INV_LABELS[invCat] || '').replace(/^\S+\s/, '')}". Adiciona acima. 👆</div>`;
    }
    box.querySelectorAll('[data-iq]').forEach(b => b.onclick = () => { const [id, c, d] = b.dataset.iq.split('|'); invApi('/api/inventory/qty', { id, campo: c, delta: Number(d) }); });
    box.querySelectorAll('[data-ibuy]').forEach(b => b.onclick = () => invApi('/api/inventory/qty', { id: b.dataset.ibuy, campo: 'stock', delta: 1 }));
    box.querySelectorAll('[data-del]').forEach(b => b.onclick = () => invApi('/api/inventory/delete', { id: b.dataset.del }));
  }
  async function invApi(path, body) {
    invPaused = true;
    try { const r = await fetch(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
      invItems = await r.json(); } finally { invPaused = false; }
    renderInv();
  }
  async function addItem() {
    const nome = $('inv-nome').value.trim();
    if (!nome) { $('inv-nome').focus(); return; }
    const body = { nome, cat: invCat, validade: INV_HASVAL[invCat] ? $('inv-val').value : '' };
    invPaused = true;
    try { const r = await fetch('/api/inventory/add', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
      if (r.ok) invItems = await r.json(); } finally { invPaused = false; }
    $('inv-nome').value = ''; $('inv-val').value = ''; renderInv(); $('inv-nome').focus();
  }
  $('inv-add').addEventListener('click', addItem);
  $('inv-nome').addEventListener('keydown', e => { if (e.key === 'Enter') addItem(); });
  setInterval(() => { if (!$('sec-inventario').classList.contains('hide')) loadInv(); }, 5000);

  // Quick-add a partir da ficha do medicamento (vai para Medicamentos)
  document.querySelectorAll('.quick').forEach(b => b.addEventListener('click', () => {
    showTab('inventario'); setInvCat('medicamentos'); $('inv-nome').value = b.dataset.add; $('inv-val').focus();
  }));

  // Arrastar para reordenar as tabs (guardado por dispositivo)
  function makeSortable(container, key, attr) {
    try {
      const saved = JSON.parse(localStorage.getItem(key) || '[]');
      saved.forEach(k => { const el = container.querySelector('[' + attr + '="' + k + '"]'); if (el) container.appendChild(el); });
    } catch (e) {}
    const save = () => localStorage.setItem(key,
      JSON.stringify([...container.querySelectorAll('[' + attr + ']')].map(e => e.getAttribute(attr))));
    container.querySelectorAll('[' + attr + ']').forEach(el => {
      el.insertAdjacentHTML('afterbegin', '<span class="grip" aria-hidden="true">⠿</span>');
      el.addEventListener('pointerdown', e => {
        if (e.button) return;
        const sx = e.clientX, sy = e.clientY; let moved = false;
        const move = ev => {
          if (!moved && Math.hypot(ev.clientX - sx, ev.clientY - sy) < 8) return;
          if (!moved) { moved = true; el.classList.add('dragging'); try { el.setPointerCapture(ev.pointerId); } catch (_) {} }
          ev.preventDefault();
          let best = null, bd = Infinity;
          container.querySelectorAll('[' + attr + ']:not(.dragging)').forEach(o => {
            const r = o.getBoundingClientRect(), cx = r.left + r.width / 2, cy = r.top + r.height / 2;
            const d = Math.hypot(ev.clientX - cx, ev.clientY - cy);
            if (d < bd) { bd = d; best = { o, cx }; }
          });
          if (best) container.insertBefore(el, ev.clientX < best.cx ? best.o : best.o.nextSibling);
        };
        const up = () => {
          document.removeEventListener('pointermove', move);
          document.removeEventListener('pointerup', up);
          if (moved) {
            el.classList.remove('dragging'); save();
            const swallow = c => { c.stopPropagation(); c.preventDefault(); };
            el.addEventListener('click', swallow, { capture: true, once: true });
            setTimeout(() => el.removeEventListener('click', swallow, true), 50);
          }
        };
        document.addEventListener('pointermove', move);
        document.addEventListener('pointerup', up);
      });
    });
  }
  makeSortable($('tabs'), 'medkit_taborder', 'data-tab');
</script>
</body>
</html>"""


@app.route("/")
def index():
    return render_template_string(PAGE, sintomas=_sintomas(), meds=_meds_ref(),
                                  socorros=_socorros(), inv_cats=INV_CATS)


@app.route("/healthz")
def healthz():
    return {"ok": True}


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8001)
