## 1. Contexte

Ce projet s'inscrit dans une séquence pédagogique où des élèves apprennent à créer un site web (HTML/CSS) en se faisant aider par un LLM, puis à lire, comprendre et modifier le code obtenu. Cette étape se fait aujourd'hui « à la main » : l'élève copie-colle un prompt dans un chatbot générique, récupère deux blocs de code, et doit parfois relancer le LLM si le HTML et le CSS sont mélangés.

Tu vas construire une application web dédiée qui remplace cette étape manuelle : l'élève saisit son prompt dans une interface simple, un agent IA hébergé sur un serveur produit un site complet et propre, et l'élève télécharge directement `index.html` et `style.css` prêts à être déposés dans son dossier `version_llm`.

## 2. Principe

- La clé API est stockée dans un fichier `.env` **côté serveur**, jamais exposée au navigateur.
- L'agent tourne **côté serveur**, construit avec **LangGraph** 
- Le serveur est une **API FastAPI** (Python).
- Le modèle de langage est appelé via **OpenRouter** (et non plus directement via l'API Anthropic), avec le modèle **DeepSeek V4 Flash** (slug OpenRouter : `deepseek/deepseek-v4-flash` — c'est le modèle que la communauté appelle familièrement « V4 Lite » ; vérifie sur `openrouter.ai/models` que ce slug est toujours exact au moment où tu codes, le catalogue évolue).
- Le frontend (Vue 3 + Tailwind CSS v4) et le backend (FastAPI) sont **deux dossiers distincts** à la racine du projet, déployables et développés indépendamment.


## 3. Objectif fonctionnel

Une application web où l'élève :
1. saisit un prompt décrivant le thème et le contenu souhaité de son site ;
2. déclenche la génération ;
3. visualise le code HTML produit et le code CSS produit dans deux zones distinctes ;
4. télécharge les fichiers `index.html` et `style.css` correspondants.

Exigence transversale la plus importante : **le rendu visuel du site généré doit être réellement soigné et professionnel**, pas un site « par défaut » générique. C'est le critère de qualité numéro un — voir section 7.

## 4. Stack technique imposée

**Backend** (dossier `backend/`) :
- Python, **FastAPI** pour exposer l'API HTTP.
- **LangGraph** (Python) pour orchestrer l'agent (voir section 6).
- **OpenRouter** comme fournisseur de modèle, via son API compatible OpenAI (`https://openrouter.ai/api/v1`), modèle `deepseek/deepseek-v4-flash`. L'intégration la plus simple côté LangChain/LangGraph est `langchain_openai.ChatOpenAI` pointé vers la base URL d'OpenRouter — pas besoin de SDK spécifique.
- Variables sensibles dans un fichier `.env` (non commité), chargé via `python-dotenv` ou `pydantic-settings`.
- Serveur ASGI : `uvicorn`.

**Frontend** (dossier `frontend/`) :
- **Vue 3** (Composition API, `<script setup>`).
- **Tailwind CSS v4**, intégré via le plugin officiel `@tailwindcss/vite`. Configuration *CSS-first* : un unique `@import "tailwindcss";` dans la feuille de style principale, personnalisation via des blocs `@theme`, **pas de fichier `tailwind.config.js`**.
- **Vite** comme outil de build.
- Le frontend ne contient **aucune logique d'agent ni aucune clé API** : il se contente d'appeler l'API du backend.

## 5. Vue d'ensemble de l'architecture

Élève (navigateur, frontend Vue 3) → requête HTTP `POST /api/generate` → backend FastAPI → graphe LangGraph → appel OpenRouter (`deepseek/deepseek-v4-flash`) → réponse structurée → backend renvoie un JSON (`html`, `css`, `feedback`, `status`) → frontend affiche le résultat.

En développement, configure soit un proxy Vite (`server.proxy` vers `http://localhost:8000`) soit un middleware CORS côté FastAPI autorisant l'origine du frontend (`http://localhost:5173` par défaut) — choisis l'un ou l'autre, mais ne laisse pas l'API ouverte à toutes les origines en production.

## 6. Agent côté backend (LangGraph Python)

L'objectif est le même qu'avant : un agent à plusieurs étapes avec une vraie boucle d'auto-correction, pas un simple aller-retour avec le modèle.

### 6.1 Sortie structurée plutôt que parsing de texte

Comme évoqué, on élimine le problème du html et du css mélangés par construction en demandant une sortie structurée plutôt que du texte libre à découper :

```python
from typing import Literal
from pydantic import BaseModel, Field

class SiteOutput(BaseModel):
    html: str = Field(description="Document HTML complet, de <!DOCTYPE html> à </html>.")
    css: str = Field(description="Contenu complet de style.css, sans aucune balise HTML.")

class ReviewOutput(BaseModel):
    status: Literal["approved", "needs_revision"]
    feedback: list[str] = Field(
        description="Remarques concrètes et actionnables ; jamais vide, même si approved."
    )
```

Utilise `llm.with_structured_output(SiteOutput)` (et `ReviewOutput` pour la relecture) plutôt que de demander deux blocs Markdown et de les parser toi-même. **Point de vigilance** : vérifie que `deepseek/deepseek-v4-flash`, via le ou les fournisseurs vers lesquels OpenRouter route la requête, supporte de façon fiable les sorties structurées / le function calling (regarde l'onglet « API » / les `supported_parameters` de la fiche du modèle sur `openrouter.ai`). Si ce n'est pas fiable à 100 %, prévois un filet de sécurité : demander `response_format={"type": "json_object"}`, des instructions strictes dans le prompt système, et un `json.loads` défensif avec une tentative de réparation avant d'abandonner.

Client modèle, exemple de référence (à adapter) :

```python
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(
    model=settings.MODEL_NAME,            # "deepseek/deepseek-v4-flash"
    base_url="https://openrouter.ai/api/v1",
    api_key=settings.OPENROUTER_API_KEY,
)
```

### 6.2 État du graphe

```python
from typing import TypedDict, Literal, Optional

class GraphState(TypedDict):
    student_prompt: str
    html: str
    css: str
    review_feedback: list[str]
    retry_count: int
    max_retries: int
    status: Literal["running", "done", "failed"]
    error_message: Optional[str]
```

### 6.3 Nœuds et arêtes

1. **`generate`** — appelle `llm.with_structured_output(SiteOutput)` avec le prompt système « générateur » (section 7) et le prompt de l'élève (ou, en cas de relance, le HTML/CSS précédents + le feedback du critique). Met à jour `html` / `css`.
2. **`validate`** — nœud déterministe (pas d'appel LLM) : vérifie que `html`/`css` sont non vides, que `html` contient `<!DOCTYPE html>` et `<link rel="stylesheet" href="style.css">`, que `css` ne contient pas de balises HTML manifestes. Arête conditionnelle :
   - invalide et `retry_count < max_retries` → retour à `generate` (avec le problème précis ajouté au contexte) ;
   - invalide et plus de relances disponibles → `fail` ;
   - valide → `design_review`.
3. **`design_review`** — appelle `llm.with_structured_output(ReviewOutput)` avec le prompt système « critique design » (section 7). Arête conditionnelle :
   - `approved` → `finalize` ;
   - `needs_revision` et `retry_count < max_retries` → `refine` ;
   - sinon → `finalize` (on livre le meilleur résultat obtenu, feedback affiché comme suggestions, plutôt que de bloquer l'élève indéfiniment).
4. **`refine`** — rappelle le modèle « générateur » en lui donnant le HTML/CSS actuel et le `feedback`, lui demandant de corriger précisément ces points. Incrémente `retry_count`. Retour à `validate`.
5. **`finalize`** — `status = "done"`. Le `review_feedback` final est conservé et sera affiché à l'élève comme pistes d'amélioration — pont direct avec l'étape 7 de `p2.md` (« voici des exemples de modifications que vous pouvez faire »).
6. **`fail`** — `status = "failed"`, message d'erreur clair (ex. proposer de reformuler le prompt et réessayer).

Plafonne `max_retries` à une petite valeur (2 suggéré) pour borner coût et latence. Utilise des fonctions de nœuds `async def` et `await llm.ainvoke(...)` puisque FastAPI est asynchrone. Consulte la documentation actuelle de LangGraph (Python) pour la syntaxe exacte de `StateGraph`, `add_conditional_edges`, etc. : ce document décrit le comportement attendu, pas l'API précise.

## 7. Directives de qualité visuelle à intégrer aux prompts système de l'agent

**Prompt système du nœud `generate`** :

```
Tu es un développeur web front-end senior, spécialisé dans la création de sites
vitrines au design soigné et distinctif (pas un design « par défaut » générique
d'IA). On te donne le thème et les attentes de contenu d'un site, rédigés par un
élève. Produis un site complet, à page unique, en HTML5 sémantique et CSS3
modernes, prêt à l'emploi.

Règles de contenu et de structure HTML :
- Document HTML5 complet et valide, de <!DOCTYPE html> à </html>, lang="fr".
- <head> avec un <title> descriptif, une meta viewport, et
  <link rel="stylesheet" href="style.css">.
- Structure sémantique (header, nav si pertinent, main, section, footer) plutôt
  que des <div> génériques partout.
- Un titre principal (h1), une description, et au moins deux sections de contenu
  distinctes, avec un vrai contenu rédigé en lien avec le thème (jamais de texte
  de remplissage générique type "lorem ipsum").
- Toute image utilise un attribut alt descriptif.

Règles de design CSS (le point le plus important) :
- Choisis une palette de 4 à 6 couleurs cohérentes et justifiées par le thème
  (variables CSS dans :root), plutôt qu'un choix par défaut. Évite spécifiquement
  les trois travers les plus fréquents des designs générés par IA : (1) fond
  crème + police serif à fort contraste + accent terracotta, (2) fond presque
  noir + un seul accent néon, (3) mise en page "journal" à filets fins et angles
  droits partout.
- Choisis une paire de polices délibérée (police d'affichage pour les titres,
  police de texte courant), importée via Google Fonts dans le <head>, avec une
  échelle de tailles cohérente.
- Utilise une échelle d'espacement cohérente (marges/paddings sur des multiples
  réguliers).
- Mets en page avec Flexbox ou Grid ; prévois au moins une media query pour le
  mobile.
- Ajoute des états :hover et :focus visibles sur les éléments interactifs, avec
  un contour de focus clavier visible.
- Reste sobre : un seul élément "signature" peut être audacieux ; le reste doit
  rester discipliné et cohérent.

Renvoie uniquement les champs prévus (html, css), sans aucun texte additionnel
avant ou après.
```

**Prompt système du nœud `design_review`** :

```
Tu es un directeur artistique senior qui relit le travail d'un autre développeur
avant publication. On te donne le HTML et le CSS d'un site généré pour un élève.
Évalue-le selon cette grille :
1. Le HTML est-il sémantique et complet (doctype, head, body, lien vers
   style.css) ?
2. Le contenu est-il réellement lié au thème, sans texte générique ?
3. La palette de couleurs est-elle cohérente et volontaire, et évite-t-elle les
   trois travers génériques de l'IA (crème+serif+terracotta, noir+néon, journal
   à filets) ?
4. Les polices sont-elles appariées de façon réfléchie, avec une échelle de
   tailles claire ?
5. La mise en page est-elle responsive (au moins une media query) ?
6. Les éléments interactifs ont-ils des états hover/focus visibles ?
7. L'espacement est-il cohérent ?
8. Le design reste-t-il sobre et cohérent, sans surcharge décorative ?

Renvoie status = "approved" si tous les points essentiels sont remplis (de
petites imperfections mineures sont acceptables), sinon "needs_revision". Le
champ feedback contient toujours au moins une remarque concrète et actionnable,
même si status = "approved" (pistes d'amélioration facultatives pour l'élève).
```

(Ces deux textes reprennent et adaptent des principes de design délibéré — palette assumée, typographie hiérarchisée, sobriété, accessibilité de base — plutôt que de copier un quelconque fichier trouvé en ligne ; libre à toi de les enrichir.)

## 8. API du backend

- `POST /api/generate` — corps `{"prompt": "..."}`, réponse `{"html": "...", "css": "...", "feedback": ["..."], "status": "done" | "failed"}`. Renvoie une erreur HTTP propre (4xx/5xx avec message clair) en cas de prompt vide, de clé OpenRouter manquante/invalide, ou d'échec après toutes les relances — **ne jamais renvoyer la stack trace brute ou la clé API dans la réponse**.
- `GET /api/health` — simple vérification de disponibilité.
- Middleware CORS limité à l'origine du frontend (variable d'environnement `FRONTEND_ORIGIN`), pas `allow_origins=["*"]` en production.
- **Suggestion de protection contre les abus** : contrairement à la version précédente où chaque élève apportait sa propre clé, la clé OpenRouter est maintenant partagée et payée par l'enseignant — n'importe qui découvrant l'URL pourrait consommer le budget. Ajoute une protection légère, par exemple un en-tête `X-Classroom-Key` comparé à une valeur définie dans `.env` (un simple code de classe, pas un vrai secret), et/ou une limite de débit basique par IP (ex. avec `slowapi`). Ce n'est pas une vraie barrière de sécurité, juste un frein raisonnable pour un usage en classe.
- Variables d'environnement attendues (`backend/.env`, avec un `backend/.env.example` commité comme modèle) :
  ```
  OPENROUTER_API_KEY=
  MODEL_NAME=deepseek/deepseek-v4-flash
  FRONTEND_ORIGIN=http://localhost:5173
  MAX_RETRIES=2
  CLASSROOM_SECRET=
  ```

## 9. Interface utilisateur (frontend)

Plus de champ de clé API : c'est la simplification principale par rapport à la version précédente. Composants attendus :

1. **Zone de prompt** — grand `<textarea>`, exemples de thèmes en placeholder, bouton « Générer le site » (désactivé pendant le chargement).
2. **Panneau HTML** — affichage en lecture seule du code HTML généré, bouton « Copier ».
3. **Panneau CSS** — idem pour le CSS.
4. **Boutons de téléchargement** — un bouton qui télécharge un fichier nommé exactement `index.html`, un autre nommé exactement `style.css` (ces noms doivent correspondre exactement à ceux attendus dans le dossier `version_llm` de `p2.md`).
5. **Pistes d'amélioration** (recommandé) — affiche le `feedback` renvoyé par l'API sous forme de liste de suggestions concrètes, en lien avec l'étape 7 de `p2.md`.
6. **Aperçu en direct** (bonus, non bloquant pour une v1) — `<iframe sandbox>` avec `srcdoc`, CSS injecté dans une balise `<style>` (l'iframe n'a pas accès au système de fichiers pour résoudre `style.css`).
7. **États d'erreur** — messages clairs en français : prompt vide, serveur indisponible, échec après toutes les relances.
8. **(Optionnel) Code d'accès de classe** — si tu implémentes `CLASSROOM_SECRET` côté backend, un petit champ (mémorisé en `localStorage`, ce n'est pas un secret sensible) permettant à l'élève de saisir une fois le code donné par l'enseignant.

Le composable qui orchestre tout ceci (`useSiteGenerator.ts`) se contente d'un `fetch` vers `` `${import.meta.env.VITE_API_BASE_URL}/api/generate` `` — toute la complexité de l'agent reste côté serveur.

## 10. Structure de projet imposée (deux dossiers distincts)

```
mon-projet/
├── backend/
│   ├── app/
│   │   ├── main.py              (création de l'app FastAPI, middleware CORS, montage des routes)
│   │   ├── api/
│   │   │   └── routes.py        (POST /api/generate, GET /api/health)
│   │   ├── agent/
│   │   │   ├── graph.py         (StateGraph LangGraph : état, nœuds, arêtes)
│   │   │   ├── schemas.py       (SiteOutput, ReviewOutput, GraphState)
│   │   │   └── prompts.py       (les deux prompts système, section 7)
│   │   └── core/
│   │       └── config.py        (chargement de .env, pydantic-settings)
│   ├── requirements.txt
│   ├── .env.example
│   └── .env                     (jamais commité — à ajouter au .gitignore)
└── frontend/
    ├── index.html
    ├── package.json
    ├── vite.config.ts
    ├── .env.example              (VITE_API_BASE_URL=http://localhost:8000)
    └── src/
        ├── main.ts
        ├── App.vue
        ├── style.css             (entrée Tailwind : @import "tailwindcss"; + @theme)
        ├── components/
        │   ├── PromptForm.vue
        │   ├── CodePanel.vue     (réutilisable pour HTML et CSS)
        │   ├── PreviewPanel.vue  (bonus)
        │   └── ImprovementTips.vue
        └── composables/
            └── useSiteGenerator.ts
```

## 11. Déploiement

Le backend nécessite un hôte capable de faire tourner un processus Python persistant (`uvicorn app.main:app`) — VPS, PaaS (Render, Railway, Fly.io, PythonAnywhere…), ou serveur de l'établissement si Python y est disponible. Le frontend (`npm run build` → dossier `frontend/dist/`) peut être servi soit séparément par un hébergeur de fichiers statiques (en configurant `VITE_API_BASE_URL` vers l'URL publique du backend), soit directement par FastAPI via `StaticFiles` si on préfère un seul service à gérer pour la classe. Indique clairement dans le `README` laquelle des deux options est utilisée.

## 12. Critères d'acceptation

- Le backend démarre (`uvicorn app.main:app --reload`) et `GET /api/health` répond.
- `POST /api/generate` avec un prompt valide renvoie un JSON contenant un HTML complet et un CSS complet, exploitables tels quels.
- La boucle de relance (`validate` → `generate`, `design_review` → `refine`) est plafonnée et ne tourne jamais indéfiniment.
- Une clé OpenRouter absente ou invalide produit une erreur HTTP claire côté frontend, jamais une fuite de la clé ni une trace serveur brute.
- Le `.env` n'est jamais committé (présent dans `.gitignore`), et il existe un `.env.example` à jour.
- Téléchargés côte à côte, `index.html` et `style.css` affichent un site stylé dans un navigateur (le lien `<link rel="stylesheet">` fonctionne).
- Le frontend ne contient aucune trace de clé API ni d'appel direct à OpenRouter ou à un fournisseur de LLM.