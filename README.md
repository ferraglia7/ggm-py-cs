# Recipe Pipeline (`ggm-py-cs`)

Pipeline di automazione per la generazione di ricette 3D nel gioco **Restaurant Roguelite** (Unity 6.3 LTS).

> **Utilizzo consigliato**: tramite la web UI **ggm-fe** che lancia questo script automaticamente, gestisce le API key e mostra i log in realtime. Vedi il repo `ggm-fe` per il setup completo.

## Panoramica

Dato il nome di una ricetta e un'immagine di riferimento, lo script automatizza:

1. Rimozione sfondo (remove.bg)
2. Salvataggio icona 2D per la UI di Unity
3. Classificazione automatica del tipo di ricetta (Gemini)
4. Upload immagine e generazione modello 3D (Meshy image-to-3D)
5. Remesh a 30k triangoli
6. Download FBX + textures nella cartella del progetto Unity
7. Scrittura del file trigger (`recipe_meta.json`) → Unity completa automaticamente il resto

## Flusso completo

```
Immagine input
    → remove.bg          → PNG trasparente
    → Unity UI/Images    → icona 2D (Sprite)
    → Gemini 2.5 Flash   → classificazione tipo (meat/fish/drink/wheat/vegetables)
    → catbox.moe         → hosting temporaneo immagine
    → Meshy image-to-3D  → modello 3D
    → Meshy remesh       → 30k triangoli
    → Assets/Prefabs/Recipes/NomeRicetta/
        ├── Source/       ← FBX + verrà estratto da Unity
        └── Textures/     ← texture scaricate
    → recipe_meta.json   → trigger per RecipeImporter.cs in Unity
```

### Cosa fa Unity automaticamente (RecipeImporter.cs)

Quando rileva `recipe_meta.json`, Unity esegue:

- Estrae la **mesh** dal FBX come asset standalone in `Source/`
- Elimina il package FBX originale
- Crea il **materiale** URP/Lit con le texture
- Crea il **prefab** con la gerarchia:
  ```
  NomeRicetta (root)
  ├── Rigidbody
  ├── BoxCollider  (bounds combinati cibo + piatto)
  ├── CookedDish   (script, recipeData assegnato automaticamente)
  ├── NomeRicetta_mesh (MeshFilter + MeshRenderer)
  └── Plate_[Tipo] (prefab piatto istanziato)
  ```
- Scala e posiziona il cibo automaticamente in base ai bounds del piatto
- Crea `Recipe_NomeRicetta.asset` (RecipeDataSO)
- Clona `Minigame_NomeRicetta.asset` da Meatballs
- Aggiunge la ricetta al **RecipePool** (baseRecipes + draftPool)

## Requisiti

```bash
pip install -r requirements.txt
```

### API Key necessarie

**Se usi ggm-fe**: le chiavi vengono passate automaticamente come variabili d'ambiente (`GGM_GEMINI_KEY`, `GGM_REMOVEBG_KEY`, `GGM_MESHY_KEY`, `GGM_UNITY_ASSETS`). Configurale una volta sola in Settings.

**Se usi da riga di comando**: aprire `pipeline.py` e inserire le chiavi nelle prime righe:

| Variabile | Servizio | Note |
|---|---|---|
| `GEMINI_API_KEY` | Google AI Studio | Per classificazione tipo ricetta (gratuito) |
| `REMOVE_BG_API_KEY` | remove.bg | Per rimozione sfondo |
| `MESHY_API_KEY` | Meshy AI | Per generazione 3D |

## Utilizzo standalone (riga di comando)

```bash
# Con immagine già pronta (consigliato)
python pipeline.py NomeRicetta "C:\percorso\immagine.png"

# Con generazione automatica via API (richiede billing Gemini)
python pipeline.py NomeRicetta
```

### Esempi

```bash
python pipeline.py Fries "C:\Users\...\Downloads\Fries.png"
python pipeline.py Fish_And_Chips "C:\Users\...\Downloads\Fish_And_Chips.png"
python pipeline.py Beer "C:\Users\...\Downloads\Beer.png"
```

## Tipi di ricetta supportati

| Tipo | Piatto Unity |
|---|---|
| `meat` | Plate_Meat |
| `fish` | Plate_Fish |
| `drink` | Plate_Drink |
| `wheat` | Plate_Wheat |
| `vegetables` | Plate_Vegetable |

Il tipo viene classificato automaticamente da Gemini. Se sbagliato, si può correggere manualmente nel campo `Category` del `RecipeDataSO` in Unity.

## Struttura output in Unity

```
Assets/
├── Prefabs/Recipes/NomeRicetta/
│   ├── NomeRicetta.prefab
│   ├── Source/
│   │   ├── NomeRicetta.mesh
│   │   └── NomeRicetta.mat
│   ├── Textures/
│   │   └── texture_0.png
│   └── recipe_meta.json
├── UI/Images/
│   └── NomeRicetta.png
└── SourceFiles/Scripts/Data/
    ├── Recipes/Recipe_NomeRicetta.asset
    └── Minigames/Minigame_NomeRicetta.asset
```

## Campi da completare manualmente in Unity

Dopo l'esecuzione, aprire `Recipe_NomeRicetta.asset` e completare:

- `Required Ingredients` — lista ingredienti con quantità
- `Required Equipment` — tipo di attrezzatura (default: Pan)
- `Base Payment` — compenso base
- `Description` — testo descrittivo opzionale
- `Is Alcoholic` — flag per le bevande alcoliche
- `Tier` — livello di progressione (default: Tier0)

## Note

- `RecipeImporter.cs` va in `Assets/Editor/` e **non deve essere pushato** al repository Unity (aggiungilo alla lista ignore di Unity Version Control)
- Le immagini caricate su catbox.moe sono pubblicamente accessibili per ~30 giorni
- Il remesh a 30k triangoli usa l'endpoint `web/v2` di Meshy
