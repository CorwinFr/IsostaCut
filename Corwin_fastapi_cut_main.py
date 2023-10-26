from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Tuple

from ortools.linear_solver import pywraplp
from collections import Counter
# Importez les autres dépendances nécessaires

app = FastAPI()

class CutRequest(BaseModel):
    tasseaux: List[Tuple[int, int]]
    bar_length: int

@app.post("/optimize/", response_model=dict)
async def optimize(request: CutRequest):
    print("Requête entrante:", request.json())
    # Reste du code...

    try:
        cuts = optimize_cutting(request.tasseaux, request.bar_length)
        cuts_count = format_and_count_cuts(cuts)
        total_bars = sum(cuts_count.values())

        print("Retour de la fonction optimize:", {"cuts": cuts_count, "total_bars": total_bars})
        
        return {"cuts": cuts_count, "total_bars": total_bars}

    except Exception as e:
        print("Erreur lors de l'optimisation:", e)
        raise HTTPException(status_code=500, detail=str(e))


# Votre code existant ici (fonctions optimize_cutting, optimize_bar, etc.)

def optimize_bar(tasseaux, bar_length):
    solver = pywraplp.Solver.CreateSolver('SCIP')
    if not solver:
        return None, tasseaux

    cuts = []
    remaining_length = bar_length

    while remaining_length > 0 and any(quantite > 0 for _, quantite in tasseaux):
        for i, (longueur, quantite) in enumerate(tasseaux):
            if longueur <= remaining_length and quantite > 0:
                cuts.append(longueur)
                tasseaux[i] = (longueur, quantite - 1)
                remaining_length -= longueur
                break
        else:
            break

    return cuts, tasseaux

def optimize_cutting(tasseaux, bar_length):
    # Tri décroissant
    tasseaux_sorted = sorted(tasseaux, reverse=True)
    cuts_per_bar = []

    while any(quantite > 0 for _, quantite in tasseaux_sorted):
        cuts, new_tasseaux = optimize_bar(tasseaux_sorted, bar_length)
        if cuts:
            cuts_per_bar.append(cuts)
            tasseaux_sorted = new_tasseaux
        else:
            break

    return cuts_per_bar


def format_and_count_cuts(cuts_per_bar):
    formatted_cuts = {}
    for cuts in cuts_per_bar:
        # Compter les occurrences de chaque longueur dans la coupe
        counts = Counter(cuts)
        # Formater la coupe (regrouper les longueurs identiques)
        formatted_cut = ', '.join(f"{length} x {count}" if count > 1 else f"{length}" for length, count in counts.items())
        formatted_cuts[formatted_cut] = formatted_cuts.get(formatted_cut, 0) + 1
    return formatted_cuts


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
