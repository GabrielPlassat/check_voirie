# VeloGuard — Dashboard conformité L228-2

Surveillance des marchés publics de voirie non conformes à l'obligation
d'aménagement cyclable (art. L228-2 Code de l'environnement, LOM 2019).

## Lancer en local

```bash
pip install -r requirements.txt
# Placer le CSV dans le même dossier que app.py
streamlit run app.py
```

## Déployer sur Streamlit Cloud (gratuit)

1. Pushez ce dossier sur GitHub
2. https://share.streamlit.io → New app → sélectionner `app.py`
3. Le dashboard est en ligne

## Structure

```
veloguard/
├── app.py                        # Dashboard
├── collect_boamp.py              # Script de collecte
├── requirements.txt
├── README.md
├── .github/workflows/
│   └── collect_boamp.yml         # GitHub Actions (hebdo)
└── data/
    └── boamp_voirie_YYYYMMDD.csv
```

## Logique de scoring (score_perimetre)

| Score | Signification |
|---|---|
| 0 | Hors périmètre L228-2 |
| 1 | Périmètre incertain |
| ≥ 2 | **Dans le périmètre** — L228-2 s'applique probablement |
| ≥ 4 | Voirie urbaine avec réfection confirmée |

**alerte_l228** = dans_perimetre ET sans mention cyclable
