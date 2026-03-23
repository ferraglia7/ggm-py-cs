# CLAUDE.md

Guida per Claude Code quando lavora in questo repository.

## Cos'è questo progetto

Script Python che automatizza la creazione di ricette 3D per il gioco **Restaurant Roguelite** (Unity 6.3 LTS, URP, DX12).

**Nota**: questo script viene normalmente invocato dalla web UI **ggm-fe** (`C:\Users\Denni\Documents\Claude\ggm\ggm-fe`), che gestisce API key, immagini, log in realtime e batch processing. Le API key vengono passate come variabili d'ambiente dal frontend (`GGM_GEMINI_KEY`, `GGM_REMOVEBG_KEY`, `GGM_MESHY_KEY`, `GGM_UNITY_ASSETS`), non sono più hardcoded nel file.

Il gioco si trova in `C:\Users\marco\Progetto\` — repository separato con il suo CLAUDE.md.

Il gioco si trova in `C:\Users\marco\Progetto\` — repository separato con il suo CLAUDE.md.

## File principali

| File | Ruolo |
|---|---|
| `pipeline.py` | Script principale — tutto il flusso |
| `requirements.txt` | Dipendenze Python (`google-genai`, `requests`) |
| `C:\Users\marco\Progetto\Assets\Editor\RecipeImporter.cs` | Script Unity Editor che completa l'automazione lato Unity — **non pushare nel repo Unity** |

## Flusso pipeline

```
python pipeline.py NomeRicetta "percorso\immagine.png"
    1. remove.bg          → rimuove sfondo dall'immagine
    2. save_icon          → salva PNG trasparente in Assets/UI/Images/
    3. gemini_classify    → classifica tipo (meat/fish/drink/wheat/vegetables)
    4. _upload_image      → carica su catbox.moe per dare URL pubblico a Meshy
    5. meshy_create_task  → POST /v1/image-to-3d (model: meshy-6)
    6. meshy_poll         → attende SUCCEEDED
    7. meshy_remesh       → POST /web/v2/tasks/{id}/remesh (30k triangoli)
    8. meshy_poll remesh  → attende SUCCEEDED su /web/v2/tasks/{remesh_id}
    9. meshy_download_assets → scarica FBX + textures in Assets/Prefabs/Recipes/
   10. write_metadata     → scrive recipe_meta.json (trigger per RecipeImporter.cs)
```

## Endpoint Meshy (IMPORTANTE)

Meshy ha due API diverse — usare quella giusta:

| Operazione | Endpoint | Note |
|---|---|---|
| Crea task 3D | `POST /v1/image-to-3d` | model: meshy-6 (meshy-4 deprecated) |
| Poll task 3D | `GET /v1/image-to-3d/{task_id}` | risposta diretta, no wrapper |
| Crea remesh | `POST /web/v2/tasks/{task_id}/remesh` | body: topology/targetPolycount/decimationMode |
| Poll remesh | `GET /web/v2/tasks/{remesh_id}` | risposta wrappata: `{"code":"OK","result":{...}}` |

Il polling gestisce entrambe le strutture di risposta (diretta e wrappata) in `meshy_poll()`.

## Struttura output in Unity

```
Assets/
├── Prefabs/Recipes/{Nome}/
│   ├── {Nome}.prefab          ← creato da RecipeImporter.cs
│   ├── Source/
│   │   ├── {Nome}.mesh        ← estratto dall'FBX da RecipeImporter.cs
│   │   └── {Nome}.mat         ← creato da RecipeImporter.cs
│   ├── Textures/
│   │   └── texture_0.png      ← scaricato da pipeline.py
│   └── recipe_meta.json       ← trigger per RecipeImporter.cs
├── UI/Images/{Nome}.png       ← icona 2D
└── SourceFiles/Scripts/Data/
    ├── Recipes/Recipe_{Nome}.asset
    └── Minigames/Minigame_{Nome}.asset
```

## Mapping tipi ricetta → piatti Unity

```python
PLATE_MAP = {
    "meat":       "Plate_Meat",
    "fish":       "Plate_Fish",
    "drink":      "Plate_Drink",
    "wheat":      "Plate_Wheat",
    "vegetables": "Plate_Vegetable",   # senza 's' finale
}
```

Attenzione: `RecipeCategory` enum in Unity usa `Vegetable` (senza 's'), non `Vegetables`.

## RecipeImporter.cs — cosa fa in Unity

Quando Unity rileva `recipe_meta.json`:
1. Configura import FBX (no materiali embedded, isReadable=true)
2. Estrae mesh dal FBX → `Source/{Nome}.mesh` standalone
3. Elimina FBX originale (alla fine, dopo che tutto è salvato)
4. Crea materiale URP/Lit con base/metallic/normal texture
5. Crea prefab: root (Rigidbody + BoxCollider + CookedDish) + figlio mesh + figlio Plate_Tipo
6. Scala cibo automaticamente (80% XZ del piatto) e lo posiziona sul piatto (bounds)
7. Crea `Recipe_{Nome}.asset` (RecipeDataSO) con nome, icona, prefab, categoria, minigame
8. Clona `Minigame_Meatballs` → `Minigame_{Nome}.asset`
9. Aggiunge ricetta a RecipePool (baseRecipes + recipes/draftPool)
10. Assegna RecipeDataSO al campo `recipeData` di CookedDish nel prefab

## API Keys

Lo script legge le chiavi da variabili d'ambiente (quando lanciato da ggm-fe):

| Env var | Servizio |
|---|---|
| `GGM_GEMINI_KEY` | Google Gemini — classificazione tipo ricetta |
| `GGM_REMOVEBG_KEY` | remove.bg — rimozione sfondo |
| `GGM_MESHY_KEY` | Meshy AI — generazione 3D |
| `GGM_UNITY_ASSETS` | Percorso locale della cartella `Assets/` Unity |

Se queste variabili non sono presenti, il codice fallback sulle costanti hardcoded in `pipeline.py` righe 21-23 (usare solo per test locali standalone).

## Gotcha importanti

- **meshy-4 è deprecated** → usare `meshy-6`
- **catbox.moe** blocca requests con user-agent generico → già gestito nella funzione `_upload_image`
- **RecipeImporter.cs non va pushato** al repo Unity (solo uso locale del developer)
- **`texture_urls` è null** nella risposta iniziale di Meshy (progress < 100%) — popolato solo a SUCCEEDED
- **Il remesh ritorna un nuovo task_id** nel campo `result` della POST response — non usare lo stesso task_id per il polling
- **Plate_Vegetable** senza 's' — sia nel PLATE_MAP che nel ParseCategory di RecipeImporter.cs
- **`RecipeCategory` è [Flags]** in Unity — valori: Fish=1, Meat=2, Drink=4, Wheat=8, Vegetable=16
- **`CookedDish.recipeData`** è un campo privato serializzato — si setta via `SerializedObject.FindProperty("recipeData")`
- **`AssetDatabase.Refresh()`** dentro `OnPostprocessAllAssets` può causare re-import loop — evitare, usare `SaveAssets()`

## Campi RecipeDataSO da completare manualmente dopo la pipeline

- `requiredIngredients` — lista ingredienti
- `requiredEquipment` — attrezzatura (default: Pan)
- `basePayment` — compenso
- `isAlcoholic` — per drink alcolici
- `tier` — progressione (default: Tier0)
- `description` — testo opzionale
