import streamlit as st
import pandas as pd
import plotly.express as px
import ast
import requests
from pathlib import Path
from datetime import datetime

st.set_page_config(
    page_title="VeloGuard — Conformité L228-2",
    page_icon="🚲",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
[data-testid="stMetricValue"] { font-size: 2rem; }
.alerte-box {
    background: #fff5f5; border-left: 4px solid #e53e3e;
    padding: 10px 14px; border-radius: 0 8px 8px 0; margin-bottom: 6px;
}
.conforme-box {
    background: #f0fff4; border-left: 4px solid #38a169;
    padding: 10px 14px; border-radius: 0 8px 8px 0; margin-bottom: 6px;
}
.score-badge {
    display:inline-block; background:#2d3748; color:white;
    font-size:11px; font-weight:bold; padding:2px 7px;
    border-radius:10px; margin-right:6px;
}
</style>
""", unsafe_allow_html=True)

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
    df['alerte_l228']    = df['alerte_l228'].astype(bool)
    df['dans_perimetre'] = df['dans_perimetre'].astype(bool)
    df['cyclable_detecte'] = df['cyclable_detecte'].astype(bool)
    return df

@st.cache_data(ttl=86400)
def load_geojson():
    url = "https://raw.githubusercontent.com/gregoiredavid/france-geojson/master/departements-version-simplifiee.geojson"
    try:
        return requests.get(url, timeout=10).json()
    except:
        return None

uploaded = st.sidebar.file_uploader("📂 Fichier CSV VeloGuard", type="csv")
csv_local = sorted(Path(".").glob("boamp_voirie_20260420.csv"))

if uploaded:
    df = load(uploaded)
elif csv_local:
    df = load(str(csv_local[-1]))
else:
    st.error("Aucun fichier CSV trouvé. Chargez-en un via la barre latérale.")
    st.stop()

geo = load_geojson()

# ── SIDEBAR FILTRES ───────────────────────────────────────────

st.sidebar.title("🔍 Filtres")

dates = df['dateparution'].dropna()
d_min, d_max = dates.min().date(), dates.max().date()
plage = st.sidebar.date_input("Période", value=(d_min, d_max), min_value=d_min, max_value=d_max)

vue = st.sidebar.radio("Afficher", ["⚠️ Alertes L228-2 uniquement", "Tous les marchés du périmètre", "Tous les marchés collectés"])

depts_dispo = sorted(df['dept'].dropna().unique())
sel_depts = st.sidebar.multiselect("Département(s)", depts_dispo, placeholder="Tous")

score_min = st.sidebar.slider("Score périmètre minimum", 0, 5, 0,
    help="0 = tous | 2 = dans périmètre L228-2 | 4+ = voirie urbaine certaine")

texte = st.sidebar.text_input("Recherche dans l'objet", placeholder="ex: réfection, avenue, giratoire…")

# Application filtres
mask = pd.Series(True, index=df.index)
if len(plage) == 2:
    mask &= (df['dateparution'] >= pd.Timestamp(plage[0])) & (df['dateparution'] <= pd.Timestamp(plage[1]))
if sel_depts:
    mask &= df['dept'].isin(sel_depts)
if score_min > 0:
    mask &= df['score_perimetre'] >= score_min
if texte:
    mask &= df['objet'].str.contains(texte, case=False, na=False)
if vue == "⚠️ Alertes L228-2 uniquement":
    mask &= df['alerte_l228']
elif vue == "Tous les marchés du périmètre":
    mask &= df['dans_perimetre']

dff = df[mask].copy()

# ── HEADER ───────────────────────────────────────────────────

st.title("🚲 VeloGuard")
st.markdown(
    "Surveillance de la **conformité L228-2** — "
    "Tout réaménagement de voirie urbaine doit intégrer des aménagements cyclables "
    "*(Code de l'environnement, issu de la LOM 2019)*"
)

src_date = df['dateparution'].max()
st.caption(f"Données BOAMP/DILA · Extraction du {src_date.strftime('%d/%m/%Y') if pd.notna(src_date) else 'N/A'} · Licence ouverte v2.0")
st.divider()

# ── KPIs ─────────────────────────────────────────────────────

n_tot      = len(df)
n_perim    = int(df['dans_perimetre'].sum())
n_alertes  = int(df['alerte_l228'].sum())
n_conf     = int((df['dans_perimetre'] & df['cyclable_detecte']).sum())
taux_conf  = n_conf / n_perim * 100 if n_perim > 0 else 0

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Marchés analysés",    f"{n_tot:,}",    help="Tous marchés TRAVAUX collectés")
c2.metric("Dans périmètre L228-2", f"{n_perim:,}", help="Score ≥ 2 : soumis à l'obligation")
c3.metric("⚠️ Alertes",           f"{n_alertes:,}", delta=f"{n_alertes/n_perim*100:.0f}% du périmètre" if n_perim else None, delta_color="inverse")
c4.metric("✅ Conformes",          f"{n_conf:,}",   delta=f"{taux_conf:.0f}% du périmètre", delta_color="normal")
c5.metric("Taux de conformité",   f"{taux_conf:.1f}%", help="Marchés voirie avec mention cyclable / total périmètre")

st.divider()

# ── CARTE + BARRES ────────────────────────────────────────────

col_map, col_bars = st.columns([1.5, 1])

dept_stats = (
    df[df['dans_perimetre']]
    .groupby('dept')
    .agg(
        total      = ('idweb', 'count'),
        alertes    = ('alerte_l228', 'sum'),
        conformes  = ('cyclable_detecte', 'sum'),
    )
    .reset_index()
)
dept_stats['taux_alerte'] = (dept_stats['alertes'] / dept_stats['total'] * 100).round(1)
dept_stats['hover'] = (
    "Dept " + dept_stats['dept'] + "<br>"
    + dept_stats['alertes'].astype(str) + " alertes / "
    + dept_stats['total'].astype(str) + " marchés<br>"
    + dept_stats['taux_alerte'].astype(str) + "% sans mention cyclable"
)

with col_map:
    st.subheader("🗺️ Alertes par département")
    if geo:
        fig = px.choropleth(
            dept_stats,
            geojson=geo,
            locations='dept',
            featureidkey='properties.code',
            color='alertes',
            color_continuous_scale=["#fff7ed","#fed7aa","#fb923c","#ea580c","#7c2d12"],
            hover_name='hover',
            hover_data={'dept': False, 'alertes': True, 'total': True, 'taux_alerte': True},
            labels={'alertes': 'Alertes L228-2', 'total': 'Total périmètre', 'taux_alerte': 'Taux alerte %'},
        )
        fig.update_geos(fitbounds="locations", visible=False)
        fig.update_layout(margin=dict(r=0,t=10,l=0,b=0), height=400,
                          coloraxis_colorbar=dict(title="Alertes", thickness=12, len=0.5))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("GeoJSON indisponible — carte remplacée par le graphique ci-contre.")

with col_bars:
    st.subheader("📊 Top 15 départements")
    top = dept_stats.sort_values('alertes', ascending=False).head(15)
    fig_b = px.bar(
        top, x='alertes', y='dept', orientation='h',
        color='taux_alerte',
        color_continuous_scale=["#fed7aa","#ea580c","#7c2d12"],
        text='alertes',
        labels={'alertes': 'Alertes', 'dept': 'Département', 'taux_alerte': '% sans mention'},
    )
    fig_b.update_traces(textposition='outside')
    fig_b.update_layout(height=400, margin=dict(t=10,b=10),
                        yaxis=dict(autorange='reversed'),
                        coloraxis_colorbar=dict(title="% alerte", thickness=10))
    st.plotly_chart(fig_b, use_container_width=True)

st.divider()

# ── TIMELINE + SCORES ─────────────────────────────────────────

col_t, col_s = st.columns(2)

with col_t:
    st.subheader("📅 Publications par semaine")
    df_tw = df[df['dans_perimetre']].copy()
    df_tw['sem'] = df_tw['dateparution'].dt.to_period('W').astype(str)
    df_tw['statut'] = df_tw['cyclable_detecte'].map({True: '✅ Conforme', False: '⚠️ Alerte'})
    tw = df_tw.groupby(['sem', 'statut']).size().reset_index(name='n')
    fig_t = px.bar(tw, x='sem', y='n', color='statut',
                   color_discrete_map={'⚠️ Alerte': '#fb923c', '✅ Conforme': '#34d399'},
                   barmode='stack',
                   labels={'n': 'Marchés', 'sem': 'Semaine', 'statut': ''})
    fig_t.update_layout(height=280, margin=dict(t=5,b=40),
                        legend=dict(orientation='h', y=-0.35))
    st.plotly_chart(fig_t, use_container_width=True)

with col_s:
    st.subheader("🎯 Distribution des scores")
    sc = df['score_perimetre'].value_counts().sort_index().reset_index()
    sc.columns = ['score', 'n']
    sc['label'] = sc['score'].map({
        0: "0 — Hors périmètre",
        1: "1 — Périmètre incertain",
        2: "2 — Périmètre probable",
        3: "3 — Voirie confirmée",
        4: "4 — Voirie + réfection",
        5: "5 — Voirie certaine",
    }).fillna(sc['score'].astype(str))
    colors = ['#e2e8f0','#fed7aa','#fb923c','#ea580c','#c2410c','#7c2d12']
    fig_s = px.bar(sc, x='score', y='n', text='n',
                   color='score',
                   color_continuous_scale=colors,
                   labels={'score': 'Score périmètre L228-2', 'n': 'Nb marchés'})
    fig_s.update_traces(textposition='outside')
    fig_s.update_layout(height=280, margin=dict(t=5), showlegend=False,
                        coloraxis_showscale=False)
    st.plotly_chart(fig_s, use_container_width=True)

st.divider()

# ── TABLEAU ───────────────────────────────────────────────────

st.subheader(f"📋 Détail — {len(dff):,} marchés ({vue})")

if dff.empty:
    st.info("Aucun résultat avec les filtres actuels.")
else:
    disp_cols = {
        'dateparution': 'Date',
        'dept': 'Dept',
        'score_perimetre': 'Score',
        'nomacheteur': 'Acheteur',
        'objet': 'Objet du marché',
        'descripteur_str': 'Descripteurs',
        'cyclable_mots': 'Mots cyclables',
        'url_avis': 'BOAMP',
    }
    cols_ok = [c for c in disp_cols if c in dff.columns]
    df_disp = dff[cols_ok].copy()
    df_disp['dateparution'] = df_disp['dateparution'].dt.strftime('%d/%m/%Y')
    df_disp = df_disp.rename(columns=disp_cols)

    st.dataframe(
        df_disp.sort_values('Score', ascending=False),
        use_container_width=True,
        height=480,
        column_config={
            "BOAMP":  st.column_config.LinkColumn("BOAMP"),
            "Objet du marché": st.column_config.TextColumn(width="large"),
            "Acheteur": st.column_config.TextColumn(width="medium"),
            "Score": st.column_config.NumberColumn(format="%d ⭐"),
        }
    )

    csv_dl = dff.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig')
    st.download_button(
        "⬇️ Télécharger la sélection (CSV)",
        data=csv_dl,
        file_name=f"veloguard_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
        mime="text/csv"
    )

# ── FOOTER ────────────────────────────────────────────────────
st.divider()
st.markdown(
    "<div style='text-align:center;color:#94a3b8;font-size:12px'>"
    "VeloGuard · Données BOAMP/DILA (Licence ouverte v2.0) · "
    "Art. L228-2 Code de l'environnement · LOM 2019"
    "</div>",
    unsafe_allow_html=True
)
