"""Kit de Sobrevivência Médico — guia doméstico de sintomas → medicação.

Aplicação web simples (Flask), em português, pensada para uso doméstico: mapeia
sintomas comuns para os medicamentos de venda livre que ajudam, com dose,
frequência, máximos e avisos. NÃO substitui aconselhamento médico/farmacêutico.

Página única, autossuficiente (CSS embutido, sem dependências externas), com
pesquisa por sintoma ou medicamento (ignora acentos). Corre no porto 8001.
"""

import unicodedata

from flask import Flask, render_template_string

app = Flask(__name__)


# --- Medicamentos (informação de referência, doses para ADULTOS saudáveis) ---
MEDS = {
    "paracetamol": {
        "nome": "Paracetamol — Ben-u-ron",
        "substancia": "Paracetamol",
        "classe": "Analgésico e antipirético",
        "dose": "500–1000 mg por toma",
        "freq": "a cada 6–8 h",
        "max": "máx. 3 g por dia",
        "notas": "1ª escolha para dor ligeira a moderada e febre. Com ou sem comida.",
        "avisos": "Não tomar em simultâneo com outros medicamentos que contenham "
                  "paracetamol (muitos antigripais têm). Cuidado com doença do fígado "
                  "e álcool.",
    },
    "ibuprofeno": {
        "nome": "Ibuprofeno — Brufen / Nurofen",
        "substancia": "Ibuprofeno",
        "classe": "Anti-inflamatório (AINE)",
        "dose": "200–400 mg por toma",
        "freq": "a cada 6–8 h",
        "max": "máx. 1200 mg por dia (sem receita)",
        "notas": "Útil quando há inflamação: dor muscular, dentária, menstrual, febre. "
                 "Tomar sempre com ou após comida.",
        "avisos": "Evitar com úlcera/azia, problemas renais ou cardíacos, asma agravada "
                  "por anti-inflamatórios e na gravidez (sobretudo 3º trimestre). Não "
                  "combinar com outros AINEs.",
    },
    "aspirina": {
        "nome": "Ácido acetilsalicílico — Aspirina",
        "substancia": "Ácido acetilsalicílico (AAS)",
        "classe": "Analgésico / antipirético / anti-inflamatório",
        "dose": "500 mg por toma",
        "freq": "a cada 4–6 h",
        "max": "máx. 3 g por dia",
        "notas": "Alternativa para dor/febre em adultos. Tomar com comida.",
        "avisos": "NÃO dar a menores de 16 anos (risco de síndrome de Reye). Maior risco "
                  "de hemorragia e irritação do estômago — em geral prefira paracetamol "
                  "ou ibuprofeno.",
    },
    "fluimucil": {
        "nome": "Acetilcisteína — Fluimucil",
        "substancia": "Acetilcisteína",
        "classe": "Mucolítico (fluidifica o catarro)",
        "dose": "600 mg (ou 200 mg 3x/dia)",
        "freq": "1x/dia, de preferência de manhã",
        "max": "conforme a apresentação",
        "notas": "Para tosse COM expetoração/catarro. Beba bastante água.",
        "avisos": "Não usar em tosse seca. Não tomar ao fim do dia. Não combinar com "
                  "antitússicos (que travam a tosse).",
    },
    "antitussico": {
        "nome": "Antitússico — Dextrometorfano (xarope)",
        "substancia": "Dextrometorfano",
        "classe": "Suprime a tosse seca",
        "dose": "conforme rótulo (ex.: 15 mg)",
        "freq": "a cada 6–8 h",
        "max": "conforme rótulo",
        "notas": "Apenas para tosse SECA e irritativa que perturba o descanso.",
        "avisos": "Não usar em tosse com expetoração nem em conjunto com mucolíticos.",
    },
    "biafine": {
        "nome": "Biafine — emulsão cutânea",
        "substancia": "Trolamina",
        "classe": "Tópico para queimaduras / vermelhidão",
        "dose": "camada generosa, massajar até absorver",
        "freq": "1–3x/dia",
        "max": "—",
        "notas": "Queimaduras solares ligeiras, eritema e escoriações superficiais "
                 "em pele intacta.",
        "avisos": "Não aplicar em feridas a sangrar, infetadas ou queimaduras graves.",
    },
    "antihistaminico": {
        "nome": "Anti-histamínico — Cetirizina / Loratadina",
        "substancia": "Cetirizina ou Loratadina",
        "classe": "Anti-histamínico (alergias)",
        "dose": "10 mg",
        "freq": "1x/dia",
        "max": "1 comprimido/dia",
        "notas": "Alergias, rinite, urticária, comichão e picadas. Pouco sedativos.",
        "avisos": "A cetirizina pode dar alguma sonolência — cuidado a conduzir.",
    },
    "loperamida": {
        "nome": "Loperamida — Imodium",
        "substancia": "Loperamida",
        "classe": "Antidiarreico",
        "dose": "4 mg ao início, depois 2 mg após cada dejeção líquida",
        "freq": "conforme necessidade",
        "max": "máx. 8 mg/dia (sem receita)",
        "notas": "Diarreia aguda. Acompanhar sempre com líquidos / soro de reidratação.",
        "avisos": "NÃO usar se houver febre alta ou sangue nas fezes, nem em crianças "
                  "pequenas sem indicação médica.",
    },
    "soro_oral": {
        "nome": "Soro de reidratação oral — Dioralyte / Redrate",
        "substancia": "Sais de reidratação",
        "classe": "Reidratação",
        "dose": "1 saqueta dissolvida em água",
        "freq": "após cada dejeção/vómito",
        "max": "conforme necessidade",
        "notas": "Essencial em diarreia e vómitos, sobretudo em crianças e idosos.",
        "avisos": "Se não conseguir reter líquidos ou houver sinais de desidratação "
                  "(boca seca, pouca urina, moleza), procure médico.",
    },
    "antiacido": {
        "nome": "Antiácido — Gaviscon / Kompensan",
        "substancia": "Alginato / sais antiácidos",
        "classe": "Antiácido (alívio rápido)",
        "dose": "conforme rótulo",
        "freq": "após as refeições e ao deitar",
        "max": "conforme rótulo",
        "notas": "Alívio rápido de azia e refluxo ocasionais.",
        "avisos": "Se for frequente (mais de 2x/semana) ou persistente, fale com médico.",
    },
    "omeprazol": {
        "nome": "Omeprazol",
        "substancia": "Omeprazol",
        "classe": "Protetor gástrico (IBP)",
        "dose": "20 mg",
        "freq": "1x/dia, antes do pequeno-almoço",
        "max": "até 14 dias sem receita",
        "notas": "Para azia/refluxo frequentes; efeito ao fim de 1–3 dias.",
        "avisos": "Se os sintomas persistirem após 14 dias, consulte o médico.",
    },
    "buscopan": {
        "nome": "Butilescopolamina — Buscopan",
        "substancia": "Butilescopolamina",
        "classe": "Antiespasmódico",
        "dose": "10–20 mg (1–2 comprimidos)",
        "freq": "até 3x/dia",
        "max": "conforme rótulo",
        "notas": "Cólicas abdominais e menstruais.",
        "avisos": "Não usar em dor abdominal intensa e persistente sem avaliação médica.",
    },
    "diclofenac_gel": {
        "nome": "Diclofenac gel — Voltaren Emulgel",
        "substancia": "Diclofenac (tópico)",
        "classe": "Anti-inflamatório tópico",
        "dose": "fina camada, massajar",
        "freq": "3–4x/dia",
        "max": "—",
        "notas": "Dores musculares e articulares, contusões e entorses ligeiras.",
        "avisos": "Aplicar em pele intacta, lavar as mãos depois e evitar exposição solar "
                  "na zona aplicada.",
    },
    "garganta": {
        "nome": "Pastilhas/Spray para a garganta — Strepsils",
        "substancia": "Anti-séptico / anestésico local",
        "classe": "Alívio da dor de garganta",
        "dose": "1 pastilha",
        "freq": "a cada 2–3 h",
        "max": "conforme rótulo",
        "notas": "Alívio local da irritação e dor de garganta.",
        "avisos": "Se houver febre alta, placas de pus ou durar mais de 5 dias, ver médico.",
    },
    "nasal": {
        "nome": "Soro fisiológico + Descongestionante — Nasex",
        "substancia": "Cloreto de sódio / Xilometazolina",
        "classe": "Congestão nasal",
        "dose": "lavagem com soro; spray se necessário",
        "freq": "soro: várias vezes/dia; spray: 1–2x/dia",
        "max": "spray: máx. 5–7 dias seguidos",
        "notas": "Comece pela lavagem com soro/água do mar. O spray descongestionante "
                 "alivia rapidamente.",
        "avisos": "Não use o spray mais de uma semana — o uso prolongado piora a "
                  "congestão (efeito de ressalto).",
    },
    "antissetico": {
        "nome": "Antisséptico — Betadine / Clorohexidina",
        "substancia": "Iodopovidona / Clorohexidina",
        "classe": "Limpeza de feridas",
        "dose": "limpar e desinfetar a ferida",
        "freq": "1–2x/dia até cicatrizar",
        "max": "—",
        "notas": "Cortes e feridas superficiais: lavar com água, desinfetar e cobrir "
                 "com penso.",
        "avisos": "Feridas profundas, sujas, mordeduras, ou que não param de sangrar → "
                  "ver médico (e confirmar a vacina do tétano).",
    },
    "hidrocortisona": {
        "nome": "Hidrocortisona creme 1%",
        "substancia": "Hidrocortisona (tópico)",
        "classe": "Corticoide tópico fraco",
        "dose": "fina camada",
        "freq": "1–2x/dia, poucos dias",
        "max": "—",
        "notas": "Comichão, picadas de inseto, dermatite e irritação ligeira da pele.",
        "avisos": "Não usar na cara nem em zonas extensas por longos períodos sem médico; "
                  "não aplicar em pele infetada.",
    },
}


# --- Sintomas → medicamentos recomendados ------------------------------------
SINTOMAS = [
    {"sintoma": "Dor de cabeça", "icone": "🤕", "meds": ["paracetamol", "ibuprofeno"],
     "nota": "Descanse, hidrate-se e reduza ecrãs/ruído.",
     "medico_se": "for súbita e muito intensa (a pior de sempre), com febre alta e pescoço "
                  "rígido, após pancada na cabeça, ou com alterações da visão, fala ou força."},
    {"sintoma": "Febre", "icone": "🌡️", "meds": ["paracetamol", "ibuprofeno"],
     "nota": "Hidrate-se bem e descanse. Roupa leve.",
     "medico_se": "passar dos 39–40 °C sem ceder, durar mais de 3 dias, ou houver falta de "
                  "ar, confusão, manchas na pele. Em bebés com menos de 3 meses, qualquer febre."},
    {"sintoma": "Dor de corpo / muscular", "icone": "💪",
     "meds": ["paracetamol", "ibuprofeno", "diclofenac_gel"],
     "nota": "Repouso e calor local ajudam.",
     "medico_se": "for após lesão grave, com inchaço importante, ou não melhorar em alguns dias."},
    {"sintoma": "Dor de dentes", "icone": "🦷", "meds": ["ibuprofeno", "paracetamol"],
     "nota": "Bochechos com água morna e sal podem aliviar.",
     "medico_se": "houver inchaço da face ou febre → dentista/médico assim que possível."},
    {"sintoma": "Dor de garganta", "icone": "😣",
     "meds": ["garganta", "ibuprofeno", "paracetamol"],
     "nota": "Líquidos mornos, repouso da voz.",
     "medico_se": "houver dificuldade em engolir/respirar, placas de pus, febre alta, ou durar +5–7 dias."},
    {"sintoma": "Constipação / Gripe", "icone": "🤧",
     "meds": ["paracetamol", "nasal", "garganta", "fluimucil"],
     "nota": "Repouso, líquidos e paciência (costuma passar em 5–7 dias).",
     "medico_se": "houver falta de ar, dor no peito, ou febre alta que persiste."},
    {"sintoma": "Tosse com expetoração", "icone": "🫁", "meds": ["fluimucil"],
     "nota": "Beba muita água para ajudar a soltar o catarro.",
     "medico_se": "houver expetoração com sangue, falta de ar, ou durar mais de 2–3 semanas."},
    {"sintoma": "Tosse seca", "icone": "🌬️", "meds": ["antitussico"],
     "nota": "Mel (em adultos) e ar húmido ajudam.",
     "medico_se": "for persistente, com falta de ar ou perda de peso."},
    {"sintoma": "Congestão nasal", "icone": "👃", "meds": ["nasal", "antihistaminico"],
     "nota": "Lavagem nasal com soro é o primeiro passo.",
     "medico_se": "durar mais de 10 dias ou houver dor facial/febre (possível sinusite)."},
    {"sintoma": "Alergia / Comichão", "icone": "🌼",
     "meds": ["antihistaminico", "hidrocortisona"],
     "nota": "Afaste-se do que provoca a alergia, se souber.",
     "medico_se": "houver inchaço da boca/garganta ou dificuldade em respirar → 112 já."},
    {"sintoma": "Diarreia", "icone": "🚽", "meds": ["soro_oral", "loperamida"],
     "nota": "Hidratação é o mais importante. Dieta leve.",
     "medico_se": "houver sangue nas fezes, febre alta, sinais de desidratação, ou durar +3 dias."},
    {"sintoma": "Náuseas / Vómitos", "icone": "🤢", "meds": ["soro_oral"],
     "nota": "Líquidos aos golinhos e comida leve quando tolerar.",
     "medico_se": "os vómitos forem persistentes, com sangue, dor abdominal intensa ou desidratação."},
    {"sintoma": "Azia / Refluxo", "icone": "🔥", "meds": ["antiacido", "omeprazol"],
     "nota": "Evite refeições pesadas, álcool e deitar logo após comer.",
     "medico_se": "for frequente, houver dificuldade a engolir, perda de peso ou dor no peito."},
    {"sintoma": "Cólicas abdominais / menstruais", "icone": "🩸",
     "meds": ["buscopan", "ibuprofeno"],
     "nota": "Calor local (saco de água quente) ajuda muito.",
     "medico_se": "a dor for intensa e persistente, com febre ou vómitos."},
    {"sintoma": "Queimadura solar", "icone": "☀️",
     "meds": ["biafine", "ibuprofeno", "antihistaminico"],
     "nota": "Arrefeça a pele, hidrate-se e evite mais sol. Beba água.",
     "medico_se": "houver bolhas extensas, febre, ou queimadura grande/em crianças."},
    {"sintoma": "Queimadura ligeira", "icone": "🔥",
     "meds": ["biafine", "paracetamol"],
     "nota": "Arrefeça com água corrente 10–20 min. NÃO use gelo nem rebente bolhas.",
     "medico_se": "for profunda, extensa, na cara/mãos/genitais, ou com bolhas grandes."},
    {"sintoma": "Feridas / Cortes", "icone": "🩹", "meds": ["antissetico"],
     "nota": "Lavar com água, desinfetar, comprimir se sangrar e cobrir.",
     "medico_se": "for profunda, não parar de sangrar, ou for mordedura → ver médico (e tétano)."},
    {"sintoma": "Picadas de inseto", "icone": "🦟",
     "meds": ["hidrocortisona", "antihistaminico"],
     "nota": "Lave a zona; gelo envolto num pano reduz o inchaço.",
     "medico_se": "houver reação alérgica grave (inchaço da boca/garganta, falta de ar) → 112."},
]


def _fold(text):
    """Minúsculas e sem acentos, para pesquisa tolerante."""
    return "".join(c for c in unicodedata.normalize("NFD", text.lower())
                   if unicodedata.category(c) != "Mn")


def _build():
    """Prepara os sintomas com os dados completos dos medicamentos + texto de pesquisa."""
    out = []
    for s in SINTOMAS:
        meds = [dict(MEDS[k], key=k) for k in s["meds"] if k in MEDS]
        terms = [s["sintoma"]] + [m["nome"] for m in meds] \
            + [m["substancia"] for m in meds] + [m["classe"] for m in meds]
        out.append({**s, "meds": meds, "search": _fold(" ".join(terms))})
    return out


PAGE = """<!doctype html>
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
      --amber:#c98a12; --amber-bg:#c98a1216; --chip:#eef2f8;
    }
    @media (prefers-color-scheme: dark) {
      :root { --bg:#0e131b; --card:#19212c; --text:#e8eef6; --muted:#90a0b6;
        --border:#28323f; --shadow:0 1px 2px rgba(0,0,0,.4); --accent:#34c884;
        --accent-bg:#34c8841f; --red:#ef6a59; --red-bg:#ef6a591f; --amber:#e0a93b;
        --amber-bg:#e0a93b1f; --chip:#222c38; }
    }
    * { box-sizing:border-box; }
    body { margin:0; background:var(--bg); color:var(--text);
      font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
      line-height:1.5; }
    .wrap { max-width:1100px; margin:0 auto; padding:1.1rem 1rem 3rem; }
    header h1 { margin:.2rem 0 .1rem; font-size:1.5rem; }
    header p { margin:0; color:var(--muted); font-size:.9rem; }
    .disclaimer { background:var(--red-bg); border:1px solid var(--red); color:var(--text);
      border-radius:12px; padding:.7rem .9rem; margin:.9rem 0; font-size:.86rem; }
    .disclaimer b { color:var(--red); }
    .search { width:100%; padding:.7rem .9rem; font-size:1rem; border-radius:12px;
      border:1px solid var(--border); background:var(--card); color:var(--text);
      box-shadow:var(--shadow); margin:.4rem 0 1rem; }
    h2 { font-size:1rem; color:var(--muted); text-transform:uppercase;
      letter-spacing:.04em; margin:1.4rem 0 .6rem; }
    .grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(330px,1fr)); gap:.8rem; }
    .card { background:var(--card); border:1px solid var(--border); border-radius:14px;
      box-shadow:var(--shadow); padding:.85rem .95rem; }
    .sym-top { display:flex; align-items:center; gap:.5rem; }
    .sym-top .ico { font-size:1.4rem; }
    .sym-top h3 { margin:0; font-size:1.08rem; }
    .nota { color:var(--muted); font-size:.84rem; margin:.35rem 0 .5rem; }
    .med { border-top:1px solid var(--border); padding:.5rem 0 .2rem; }
    .med .n { font-weight:700; font-size:.92rem; }
    .med .d { display:flex; flex-wrap:wrap; gap:.3rem; margin:.3rem 0; }
    .pill { font-size:.74rem; font-weight:700; padding:.12rem .5rem; border-radius:999px;
      background:var(--accent-bg); color:var(--accent); border:1px solid var(--accent); }
    .pill.max { background:var(--amber-bg); color:var(--amber); border-color:var(--amber); }
    .med .obs { font-size:.8rem; color:var(--muted); }
    .flag { margin-top:.6rem; font-size:.82rem; background:var(--amber-bg);
      border:1px solid var(--amber); border-radius:10px; padding:.4rem .55rem; }
    .flag b { color:var(--amber); }
    .ref .card { margin-bottom:0; }
    .ref .n { font-weight:700; }
    .ref .sub { color:var(--muted); font-size:.82rem; margin:.15rem 0 .4rem; }
    .ref .obs { font-size:.83rem; }
    .ref .warn { font-size:.83rem; color:var(--red); margin-top:.35rem; }
    .empty { color:var(--muted); padding:1rem; }
    footer { margin-top:2rem; text-align:center; color:var(--muted); font-size:.82rem; }
    .em { color:var(--red); font-weight:700; }
  </style>
</head>
<body>
<div class="wrap">
  <header>
    <h1>🩺 Kit Médico Caseiro</h1>
    <p>O que tomar em casa para sintomas comuns — dose, frequência e quando ir ao médico.</p>
  </header>

  <div class="disclaimer">
    <b>⚠️ Aviso:</b> guia de referência doméstico, <b>não substitui</b> o médico ou o
    farmacêutico. As doses são para <b>adultos saudáveis</b> e podem não se aplicar ao seu
    caso. Em crianças, gravidez/amamentação, doenças crónicas ou medicação habitual,
    <b>pergunte sempre</b> e leia o <b>folheto informativo (bula)</b>. Em emergência ligue
    <span class="em">112</span>.
  </div>

  <input id="q" class="search" type="search" autocomplete="off"
         placeholder="🔎 Pesquisar sintoma ou medicamento (ex.: dor de cabeça, febre, queimadura)…">

  <h2>Sintomas</h2>
  <div class="grid" id="sintomas">
    {% for s in sintomas %}
    <div class="card sym" data-search="{{ s.search }}">
      <div class="sym-top"><span class="ico">{{ s.icone }}</span><h3>{{ s.sintoma }}</h3></div>
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
  <div class="empty" id="noresults" hidden>Sem resultados para a pesquisa.</div>

  <h2>Lista de medicamentos</h2>
  <div class="grid ref" id="meds">
    {% for m in meds %}
    <div class="card medref" data-search="{{ m.search }}">
      <div class="n">{{ m.nome }}</div>
      <div class="sub">{{ m.classe }} · {{ m.substancia }}</div>
      <div class="d" style="display:flex;flex-wrap:wrap;gap:.3rem;margin:.2rem 0 .4rem">
        <span class="pill">{{ m.dose }}</span>
        <span class="pill">{{ m.freq }}</span>
        {% if m.max and m.max != '—' %}<span class="pill max">{{ m.max }}</span>{% endif %}
      </div>
      <div class="obs">{{ m.notas }}</div>
      <div class="warn">⚠️ {{ m.avisos }}</div>
    </div>
    {% endfor %}
  </div>

  <footer>
    Kit Médico Caseiro · informação geral de medicamentos de venda livre.<br>
    Em caso de dúvida fale com o seu farmacêutico · Emergência: <span class="em">112</span> ·
    Linha SNS 24: <b>808 24 24 24</b>
  </footer>
</div>

<script>
  const fold = s => s.normalize('NFD').replace(/[\\u0300-\\u036f]/g, '').toLowerCase();
  const q = document.getElementById('q');
  const syms = [...document.querySelectorAll('.sym')];
  const refs = [...document.querySelectorAll('.medref')];
  const none = document.getElementById('noresults');
  q.addEventListener('input', () => {
    const term = fold(q.value.trim());
    let shown = 0;
    syms.forEach(c => {
      const hit = !term || c.dataset.search.includes(term);
      c.style.display = hit ? '' : 'none';
      if (hit) shown++;
    });
    refs.forEach(c => {
      c.style.display = (!term || c.dataset.search.includes(term)) ? '' : 'none';
    });
    none.hidden = shown > 0 || !term;
  });
</script>
</body>
</html>"""


@app.route("/")
def index():
    return render_template_string(PAGE, sintomas=_build(),
                                  meds=[dict(v, search=_fold(v["nome"] + " " + v["substancia"]
                                                             + " " + v["classe"]))
                                        for v in MEDS.values()])


@app.route("/healthz")
def healthz():
    return {"ok": True}


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8001)
