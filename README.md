# 🚲 VeloGuard

**Surveillance automatique de la conformité des marchés publics de voirie à l'obligation d'aménagement cyclable**

> *Article L228-2 du Code de l'environnement (issu de la Loi d'Orientation des Mobilités, 2019) :*
> *"À l'occasion des réalisations ou des rénovations des voies urbaines, à l'exception des autoroutes et voies rapides, doivent être mis au point des itinéraires cyclables."*

---

## Contexte

La LOM de 2019 impose d'intégrer des aménagements cyclables dans tout projet de réfection ou de réaménagement de voirie urbaine. Cette obligation est souvent méconnue ou ignorée dans les appels d'offres publics.

VeloGuard collecte automatiquement les marchés publics de travaux publiés au BOAMP, identifie ceux qui relèvent du périmètre L228-2, et signale ceux qui ne mentionnent aucun aménagement cyclable.

---

## Structure du projet

```
veloguard/
├── app.py                          # Dashboard Streamlit
├── collect_boamp.py                # Script de collecte (utilisé par GitHub Actions)
├── requirements.txt                # Dépendances Python
├── README.md
├── .github/
│   └── workflows/
│       └── collect_boamp.yml       # Automatisation hebdomadaire
└── data/
    └── boamp_voirie_YYYYMMDD.csv   # Fichiers collectés (un par semaine)
```

---

## Installation et lancement

### Prérequis

- Python 3.10+
- Un compte GitHub (pour l'automatisation)
- Un compte [Streamlit Cloud](https://share.streamlit.io) (pour le déploiement public, gratuit)

### En local

```bash
pip install -r requirements.txt
# Placer un fichier boamp_voirie_YYYYMMDD.csv dans le même dossier
streamlit run app.py
```

### Déploiement sur Streamlit Cloud

1. Pousser ce repo sur GitHub avec `app.py`, `requirements.txt` et un CSV dans `data/`
2. Se connecter sur [share.streamlit.io](https://share.streamlit.io) avec son compte GitHub
3. **New app** → sélectionner le repo → fichier principal : `app.py` → **Deploy**
4. Le dashboard est accessible via une URL publique (ex : `https://veloguard.streamlit.app`)

---

## Collecte des données

### Source

**API BOAMP / DILA** — [boamp-datadila.opendatasoft.com](https://boamp-datadila.opendatasoft.com)
Gratuite, sans clé, Licence ouverte v2.0 (Etalab). Mise à jour 2x/jour, 7j/7.

### Ce qui est collecté

Tous les marchés de type **TRAVAUX** publiés au BOAMP dont l'objet ou les descripteurs contiennent des mots-clés voirie (`voirie`, `chaussée`, `trottoir`, `réfection`, `réaménagement`...).

### Notebook de collecte (Google Colab)

Le fichier `VeloGuard_01_Collecte_BOAMP_v5.ipynb` permet de lancer une collecte manuelle et de télécharger le CSV résultant. Il suffit de l'ouvrir dans Google Colab et d'exécuter les cellules dans l'ordre.

### Automatisation (GitHub Actions)

Le workflow `.github/workflows/collect_boamp.yml` exécute le script `collect_boamp.py` chaque lundi matin et commite le CSV dans le dossier `data/`. Streamlit Cloud relit automatiquement le fichier le plus récent.

---

## Logique d'analyse

### Étape 1 — Score de périmètre L228-2

Chaque marché reçoit un score de **0 à 5** qui évalue la probabilité qu'il soit soumis à l'obligation.

| Condition | Points |
|---|---|
| Descripteur BOAMP = "Voirie" ou "Voirie et réseaux divers" (marché mono ou bi-lot) | **+2** |
| Même descripteur dans un accord-cadre avec 5 à 8 lots | **+1** |
| Voirie noyée dans un accord-cadre TCE (> 8 lots) | **0** |
| Descripteur "Chaussée", "Trottoir" ou "Revêtement" (≤ 4 lots) | **+1** |
| Objet contient un mot de réfection/réaménagement associé à voirie/rue/avenue/chaussée | **+1** |
| Objet contient : bâtiment, FTTH, toiture, hôpital, pharmacie, cimetière, aéroport... | **−3** |
| Objet contient : autoroute, voie rapide, 2x2 voies, pont/viaduc sur RN/RD, échangeur | **−3** |
| Objet contient : construction neuve + bâtiment/logements | **−1** |

**Seuil retenu : score ≥ 2 = dans le périmètre L228-2**

> **Note sur les routes départementales et nationales** : la loi exclut uniquement les autoroutes et voies rapides. Une RD ou RN traversant une agglomération est une voie urbaine — L228-2 s'applique. Seuls les ouvrages d'art (ponts, viaducs), échangeurs et contournements hors agglomération sont exclus.

### Étape 2 — Détection d'aménagement cyclable

L'objet du marché et ses descripteurs sont analysés à la recherche de mentions cyclables :

*piste cyclable, bande cyclable, voie verte, véloroute, couloir vélo, aménagement cyclable, vélo, cycliste, arceaux vélo, abri vélo, mode doux, cheminement doux, L228-2...*

### Résultat

| Flag | Définition |
|---|---|
| `alerte_l228 = True` | Marché dans le périmètre **sans** mention d'aménagement cyclable → à vérifier |
| `dans_perimetre = True` + `cyclable_detecte = True` | Marché dans le périmètre **avec** mention cyclable → a priori conforme |

### Limite connue

Seul le **titre du marché** (`objet`) est analysé via l'API, pas la description complète du CCTP. Certains marchés classés "alerte" peuvent mentionner le vélo dans leur descriptif complet. **Une vérification manuelle sur [boamp.fr](https://www.boamp.fr) est recommandée avant toute interprétation ou action.**

---

## Fonctionnalités du dashboard

- **Carte de France** des alertes par département
- **KPIs** : total analysé, périmètre L228-2, alertes, conformes, taux de conformité
- **Timeline** des publications par semaine
- **Distribution des scores** (0 à 5)
- **Tableau filtrable** : par département, score, période, recherche textuelle dans l'objet
- **Lien direct** vers chaque annonce sur boamp.fr
- **Export CSV** de la sélection
- **Section méthodologie** expliquant le scoring

---

## Limites et perspectives

**Limites actuelles**

- Analyse limitée au titre du marché (pas le CCTP complet)
- Couverture BOAMP : marchés > 40 000 € HT principalement (les MAPA en dessous peuvent ne pas y figurer)
- Le scoring est heuristique — des cas limites existent, la vérification manuelle reste nécessaire

**Pistes d'amélioration**

- Récupération du texte intégral de l'avis via l'API DILA (requête secondaire par `idweb`)
- Croisement avec les données de planification cyclable des collectivités (SRADDET, PDU)
- Alertes email ou Slack sur les nouvelles publications à risque
- Élargissement à d'autres sources : PLACE, portails open data des grandes métropoles

---

## Colonnes du CSV produit

| Colonne | Description |
|---|---|
| `idweb` | Identifiant unique BOAMP |
| `dateparution` | Date de publication |
| `dept` | Département (2 caractères) |
| `nomacheteur` | Nom de l'acheteur public |
| `objet` | Titre du marché |
| `descripteur_str` | Descripteurs BOAMP |
| `score_perimetre` | Score L228-2 (−3 à +5) |
| `dans_perimetre` | True si score ≥ 2 |
| `cyclable_detecte` | True si mention d'aménagement cyclable |
| `cyclable_mots` | Mots cyclables détectés |
| `alerte_l228` | **True = alerte à vérifier** |
| `url_avis` | Lien direct vers l'annonce BOAMP |

---

## Sources et références

- [Article L228-2 du Code de l'environnement](https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000039784296)
- [Loi d'Orientation des Mobilités (LOM)](https://www.legifrance.gouv.fr/jorf/id/JORFTEXT000039666574)
- [API BOAMP / DILA](https://boamp-datadila.opendatasoft.com)
- [Guide FUB sur l'obligation L228-2](https://www.fub.fr)

---

## Licence

Code source : MIT
Données BOAMP : [Licence ouverte v2.0](https://www.etalab.gouv.fr/licence-ouverte-open-licence) (Etalab / DILA)
