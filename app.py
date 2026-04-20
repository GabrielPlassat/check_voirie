import streamlit as st
import pandas as pd
import plotly.express as px
import re, ast, requests
from pathlib import Path
from datetime import datetime

st.set_page_config(
    page_title="VeloGuard — Conformité L228-2",
    page_icon="🚲", layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
[data-testid="stMetricValue"] { font-size: 2rem; }
.warning-banner {
    background: #fffbeb; border-left: 4px solid #f59e0b;
    padding: 10px 14px; border-radius: 0 8px 8px 0; margin: 8px 0;
    font-size: 13px;
}
</style>
""", unsafe_allow_html=True)

# ── SCORING (identique au notebook v5) ───────────────────────
DESC_VOIRIE_FORT   = ['voirie', 'voirie et réseaux divers', 'chaussée']
DESC_VOIRIE_FAIBLE = ['trottoir', 'revêtement', 'terrassement']
MOTS_REFECTION = [
    r'r[eé]fection.{0,30}(voirie|chauss[eé]e|trottoir|rue|avenue|boulevard)',
    r'r[eé]habilitation.{0,30}(voirie|chauss[eé]e|rue|avenue)',
    r'r[eé]am[eé]nagement.{0,30}(voirie|rue|avenue|boulevard|place|giratoire)',
    r'am[eé]nagement.{0,30}(voirie|rue|avenue|boulevard|place|giratoire|carrefour)',
    r'requalification.{0,30}(voirie|rue|avenue|boulevard|place)',
    r'travaux.{0,20}voirie', r'entretien.{0,20}voirie',
    r'am[eé]nagement urbain', r'enrob[eé]', r'enduit superficiel',
    r'rev[eê]tement.{0,20}(chauss[eé]e|voirie|rue)',
    r'trottoir', r'chauss[eé]e', r'giratoire',
    r'carrefour.{0,20}(am[eé]nag|s[eé]curis)',
]
EXCLUSIONS_FORTES = [
    r'\b(b[aâ]timent|r[eé]novation.{0,20}b[aâ]t|construction.{0,20}b[aâ]t)\b',
    r'\b(r[eé]seau.{0,15}(ftth|fibre|eau potable|gaz|assainissement))\b',
    r'\b(toiture|charpente|menuiserie|peinture.{0,10}b[aâ]t|plomberie)\b',
    r'\b(barrage|berge|digue)\b', r'\b(ascenseur|escalier)\b',
    r'\bd[eé]samiantage\b',
    r'\b(pharmacie|h[oô]pital|chru?|ehpad)\b',
    r'\bstade\b', r'\btribune\b', r'\bcimeti[eè]re\b', r'\ba[eé]roport\b',
]
HORS_AGGLO = [
    r'\bRN\s*\d+\b', r'\bautoroute\b',
    r'\bRD\s*\d+.{0,40}(hors agglo|route d[eé]partementale.{0,20}(entre|pr\s*\d|section))',
]
KEYWORDS_CYCLABLE = [
    r'piste cyclable', r'bande cyclable', r'voie cyclable',
    r'itin[eé]raire cyclable', r'r[eé]seau cyclable',
    r'v[eé]loroute', r'voie verte', r'couloir v[eé]lo',
    r'am[eé]nagement cyclable', r'continuit[eé] cyclable',
    r'arceaux? v[eé]lo', r'stationnement v[eé]lo',
    r'abri v[eé]lo', r'box v[eé]lo', r'parking v[eé]lo',
    r'borne de recharge.{0,20}v[eé]lo',
    r'v[eé]lo\b', r'v[eé]los\b', r'cycliste',
    r'deux[-\s]roues', r'mobilit[eé] douce',
    r'cheminement doux', r'mode doux',
    r'usager.{0,15}v[eé]lo', r'L\.?228[-\s]2',
]

def parse_descripteurs(val):
    try:
        lst = ast.literal_eval(str(val))
        if isinstance(lst, list):
            return [str(x).lower().strip() for x in lst]
    except:
        pass
    return [s.strip().lower() for s in str(val).split(',')]

def score_perimetre(row):
    descs   = parse_descripteurs(row.get('descripteur_str', ''))
    objet   = str(row.get('objet', '')).lower()
    nb_desc = len(descs)
    score   = 0
    has_fort = any(any(v in d for v in DESC_VOIRIE_FORT) for d in descs)
    if has_fort:
        score += 0 if nb_desc > 8 else (1 if nb_desc > 5 else 2)
    elif any(any(v in d for v in DESC_VOIRIE_FAIBLE) for d in descs) and nb_desc <= 4:
        score += 1
    for p in MOTS_REFECTION:
        if re.search(p, objet, re.IGNORECASE):
            score += 1; break
    for p in EXCLUSIONS_FORTES:
        if re.search(p, objet, re.IGNORECASE):
            score -= 3; break
    for p in HORS_AGGLO:
        if re.search(p, objet, re.IGNORECASE):
            score -= 2; break
    if re.search(r'\bconstruction\b.{0,30}\b(neuve|b[aâ]timent|logements|maisons?)\b', objet, re.IGNORECASE):
        score -= 1
    return score

def detecter_cyclable(texte):
    t = str(texte).lower()
    mots = []
    for p in KEYWORDS_CYCLABLE:
        m = re.findall(p, t, re.IGNORECASE)
        if m: mots.extend([str(x).lower() for x in m])
    return bool(mots), list(set(mots))

# ── CHARGEMENT ────────────────────────────────────────────────
@st.cache_data(ttl=3600)
def load(path):
    df = pd.read_csv(path)
    def parse_dept(v):
        try:
            lst = ast.literal_eval(str(v))
            return str(lst[0]).zfill(2) if lst else "00"
        except:
            return str(v).zfill(2)[:2]
    if 'code_departement' in df.columns:
        df['dept'] = df['code_departement'].apply(parse_dept)
    df['dateparution'] = pd.to_datetime(df['dateparution'], errors='coerce')
    # Recalculer avec scoring v5 si colonnes présentes
    if 'score_perimetre' not in df.columns or True:
        df['score_perimetre'] = df.apply(score_perimetre, axis=1)
        df['dans_perimetre']  = df['score_perimetre'] >= 2
        results = (df['objet'].fillna('') + ' ' + df.get('descripteur_str', pd.Series([''] * len(df))).fillna('')).apply(detecter_cyclable)
        df['cyclable_detecte'] = results.apply(lambda x: x[0])
        df['cyclable_mots']    = results.apply(lambda x: ', '.join(x[1]) if x[1] else '')
        df['alerte_l228']      = df['dans_perimetre'] & ~df['cyclable_detecte']
    return df

@st.cache_data(ttl=86400)
def load_geo():
    try:
        return requests.get(
            "https://raw.githubusercontent.com/gregoiredavid/france-geojson/master/departements-version-simplifiee.geojson",
            timeout=10).json()
    except:
        return None

uploaded = st.sidebar.file_uploader("📂 Fichier CSV VeloGuard", type="csv")
csv_local = sorted(Path(".").glob("boamp_voirie_*.csv"))
if uploaded:
    df = load(uploaded)
elif csv_local:
    df = load(str(csv_local[-1]))
else:
    st.error("Aucun fichier CSV. Chargez-en un via la sidebar.")
    st.stop()

geo = load_geo()

# ── SIDEBAR ───────────────────────────────────────────────────
st.sidebar.title("🔍 Filtres")
dates = df['dateparution'].dropna()
d_min, d_max = dates.min().date(), dates.max().date()
plage = st.sidebar.date_input("Période", (d_min, d_max), min_value=d_min, max_value=d_max)
vue = st.sidebar.radio("Afficher", ["⚠️ Alertes L228-2 uniquement", "Périmètre complet", "Tous les marchés"])
sel_depts = st.sidebar.multiselect("Département(s)", sorted(df['dept'].dropna().unique()), placeholder="Tous")
score_min = st.sidebar.slider("Score périmètre minimum", 0, 5, 0)
texte = st.sidebar.text_input("Recherche dans l'objet", placeholder="réfection, avenue…")

mask = pd.Series(True, index=df.index)
if len(plage) == 2:
    mask &= (df['dateparution'] >= pd.Timestamp(plage[0])) & (df['dateparution'] <= pd.Timestamp(plage[1]))
if sel_depts:
    mask &= df['dept'].isin(sel_depts)
if score_min:
    mask &= df['score_perimetre'] >= score_min
if texte:
    mask &= df['objet'].str.contains(texte, case=False, na=False)
if vue == "⚠️ Alertes L228-2 uniquement":
    mask &= df['alerte_l228']
elif vue == "Périmètre complet":
    mask &= df['dans_perimetre']
dff = df[mask].copy()

# ── HEADER ────────────────────────────────────────────────────
st.title("🚲 VeloGuard")
st.markdown(
    "Surveillance de la **conformité L228-2** — Tout réaménagement de voirie urbaine "
    "doit intégrer des aménagements cyclables *(Code de l'environnement, LOM 2019)*"
)
src_date = df['dateparution'].max()
st.caption(f"Données BOAMP/DILA · {src_date.strftime('%d/%m/%Y') if pd.notna(src_date) else 'N/A'} · Licence ouverte v2.0")

st.markdown("""
<div class='warning-banner'>
⚠️ <strong>Limite de l'analyse</strong> : seul le <em>titre du marché</em> (champ <code>objet</code>) est analysé, 
pas la description complète du CCTP. Certaines alertes peuvent mentionner le vélo dans leur descriptif complet. 
Une <strong>vérification manuelle</strong> sur <a href="https://www.boamp.fr" target="_blank">boamp.fr</a> est recommandée avant toute action.
</div>
""", unsafe_allow_html=True)

st.divider()

# ── KPIs ─────────────────────────────────────────────────────
n_tot  = len(df)
n_p    = int(df['dans_perimetre'].sum())
n_a    = int(df['alerte_l228'].sum())
n_c    = int((df['dans_perimetre'] & df['cyclable_detecte']).sum())
tx     = n_c / n_p * 100 if n_p else 0

c1,c2,c3,c4,c5 = st.columns(5)
c1.metric("Marchés analysés",      f"{n_tot:,}")
c2.metric("Périmètre L228-2",      f"{n_p:,}",  help="Score ≥ 2")
c3.metric("⚠️ Alertes",            f"{n_a:,}",  delta=f"{n_a/n_p*100:.0f}% du périmètre" if n_p else None, delta_color="inverse")
c4.metric("✅ Conformes",           f"{n_c:,}",  delta=f"{tx:.0f}%", delta_color="normal")
c5.metric("Taux de conformité",    f"{tx:.1f}%")
st.divider()

# ── CARTE + BARRES ────────────────────────────────────────────
dept_stats = (df[df['dans_perimetre']].groupby('dept')
    .agg(total=('idweb','count'), alertes=('alerte_l228','sum'), conformes=('cyclable_detecte','sum'))
    .reset_index())
dept_stats['taux'] = (dept_stats['alertes'] / dept_stats['total'] * 100).round(1)

col_map, col_bar = st.columns([1.5, 1])
with col_map:
    st.subheader("🗺️ Alertes par département")
    if geo:
        fig = px.choropleth(dept_stats, geojson=geo, locations='dept',
            featureidkey='properties.code', color='alertes',
            color_continuous_scale=["#fff7ed","#fed7aa","#fb923c","#ea580c","#7c2d12"],
            hover_data={'dept':True,'alertes':True,'total':True,'taux':True},
            labels={'alertes':'Alertes','total':'Total périmètre','taux':'% alerte'})
        fig.update_geos(fitbounds="locations", visible=False)
        fig.update_layout(margin=dict(r=0,t=10,l=0,b=0), height=400,
            coloraxis_colorbar=dict(title="Alertes",thickness=12,len=0.5))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("GeoJSON indisponible.")

with col_bar:
    st.subheader("📊 Top 15 départements")
    top = dept_stats.sort_values('alertes', ascending=False).head(15)
    fig_b = px.bar(top, x='alertes', y='dept', orientation='h',
        color='taux', color_continuous_scale=["#fed7aa","#ea580c","#7c2d12"],
        text='alertes', labels={'alertes':'Alertes','dept':'Dept','taux':'% alerte'})
    fig_b.update_traces(textposition='outside')
    fig_b.update_layout(height=400, margin=dict(t=10,b=10),
        yaxis=dict(autorange='reversed'),
        coloraxis_colorbar=dict(title="% alerte",thickness=10))
    st.plotly_chart(fig_b, use_container_width=True)

st.divider()

# ── TIMELINE + SCORES ─────────────────────────────────────────
col_t, col_s = st.columns(2)
with col_t:
    st.subheader("📅 Publications par semaine")
    df_tw = df[df['dans_perimetre']].copy()
    df_tw['sem']    = df_tw['dateparution'].dt.to_period('W').astype(str)
    df_tw['statut'] = df_tw['cyclable_detecte'].map({True:'✅ Conforme', False:'⚠️ Alerte'})
    tw = df_tw.groupby(['sem','statut']).size().reset_index(name='n')
    fig_t = px.bar(tw, x='sem', y='n', color='statut',
        color_discrete_map={'⚠️ Alerte':'#fb923c','✅ Conforme':'#34d399'},
        barmode='stack', labels={'n':'Marchés','sem':'Semaine','statut':''})
    fig_t.update_layout(height=280, margin=dict(t=5,b=40),
        legend=dict(orientation='h',y=-0.35))
    st.plotly_chart(fig_t, use_container_width=True)

with col_s:
    st.subheader("🎯 Distribution des scores")
    sc = df['score_perimetre'].value_counts().sort_index().reset_index()
    sc.columns = ['score','n']
    LABELS = {-3:"−3 Exclu (bâtiment…)",-2:"−2 Hors agglo",-1:"−1 Constr. neuve",
               0:"0 Hors périmètre",1:"1 Incertain",2:"2 Probable ✓",3:"3 Confirmé ✓",
               4:"4 Réfection ✓",5:"5 Certain ✓"}
    sc['label'] = sc['score'].map(LABELS).fillna(sc['score'].astype(str))
    sc['perim'] = sc['score'].apply(lambda x: 'Dans périmètre' if x >= 2 else 'Hors périmètre')
    fig_s = px.bar(sc, x='score', y='n', text='n', color='perim',
        color_discrete_map={'Dans périmètre':'#fb923c','Hors périmètre':'#e2e8f0'},
        labels={'score':'Score L228-2','n':'Nb marchés','perim':''},
        hover_data={'label':True})
    fig_s.update_traces(textposition='outside')
    fig_s.update_layout(height=280, margin=dict(t=5),
        legend=dict(orientation='h',y=1.15))
    st.plotly_chart(fig_s, use_container_width=True)

st.divider()

# ── MÉTHODOLOGIE ─────────────────────────────────────────────
with st.expander("📐 Méthodologie — Comment est calculé le score ?"):
    st.markdown("""
### Principe général

Chaque marché reçoit un **score de périmètre L228-2** (de -3 à +5) qui évalue la probabilité  
qu'il soit soumis à l'obligation d'aménagement cyclable de l'article L228-2 du Code de l'environnement.

**Seuil retenu : score ≥ 2 = dans le périmètre**

---

### Règles de scoring

| Condition | Points |
|---|---|
| Descripteur BOAMP = "Voirie" ou "Voirie et réseaux divers" (marché mono-lot) | **+2** |
| Même descripteur dans un accord-cadre multi-lots (5-8 descripteurs) | **+1** |
| Voirie noyée dans un accord-cadre TCE (>8 descripteurs) | **0** |
| Descripteur "Chaussée", "Trottoir", "Revêtement" (marché ≤4 lots) | **+1** |
| Objet contient : réfection/réaménagement/requalification + voirie/rue/avenue/chaussée... | **+1** |
| Objet contient : bâtiment, FTTH, toiture, hôpital, cimetière, aéroport... | **−3** |
| Objet contient : RN, autoroute (hors agglomération certaine) | **−2** |
| Objet contient : construction neuve + bâtiment/logements | **−1** |

---

### Détection des aménagements cyclables

L'analyse porte uniquement sur le **titre du marché** (`objet`) et ses descripteurs,  
pas sur la description complète du cahier des charges (CCTP).

Mots recherchés : *piste cyclable, bande cyclable, voie verte, véloroute, vélo, cycliste,  
aménagement cyclable, voie cyclable, arceaux vélo, abri vélo, mode doux, L228-2…*

> ⚠️ **Conséquence** : certains marchés classés "alerte" peuvent mentionner le vélo  
> dans leur descriptif complet, non accessible via l'API. Une vérification sur  
> [boamp.fr](https://www.boamp.fr) est recommandée avant toute interprétation.

---

### Source des données

API BOAMP / DILA — [boamp-datadila.opendatasoft.com](https://boamp-datadila.opendatasoft.com)  
Licence ouverte v2.0 (Etalab) · Mise à jour 2×/jour
    """)

st.divider()

# ── TABLEAU ───────────────────────────────────────────────────
st.subheader(f"📋 {len(dff):,} marchés — {vue}")

if dff.empty:
    st.info("Aucun résultat.")
else:
    cols_map = {'dateparution':'Date','dept':'Dept','score_perimetre':'Score',
                'nomacheteur':'Acheteur','objet':'Objet',
                'descripteur_str':'Descripteurs','cyclable_mots':'Mots cyclables','url_avis':'BOAMP'}
    cols_ok = [c for c in cols_map if c in dff.columns]
    disp = dff[cols_ok].copy()
    disp['dateparution'] = disp['dateparution'].dt.strftime('%d/%m/%Y')
    disp = disp.rename(columns=cols_map)

    st.dataframe(
        disp.sort_values('Score', ascending=False),
        use_container_width=True, height=480,
        column_config={
            "BOAMP":  st.column_config.LinkColumn("BOAMP"),
            "Objet":  st.column_config.TextColumn(width="large"),
            "Acheteur": st.column_config.TextColumn(width="medium"),
            "Score":  st.column_config.NumberColumn(format="%d ⭐"),
        }
    )
    csv_dl = dff.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig')
    st.download_button("⬇️ Télécharger la sélection (CSV)", data=csv_dl,
        file_name=f"veloguard_{datetime.now().strftime('%Y%m%d_%H%M')}.csv", mime="text/csv")

st.divider()
st.markdown("<div style='text-align:center;color:#94a3b8;font-size:12px'>"
    "VeloGuard · BOAMP/DILA (Licence ouverte v2.0) · Art. L228-2 Code de l'environnement · LOM 2019"
    "</div>", unsafe_allow_html=True)
