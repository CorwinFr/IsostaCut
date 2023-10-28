from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Tuple
from fastapi.middleware.cors import CORSMiddleware
from ortools.linear_solver import pywraplp
from collections import Counter
# Importez les autres dépendances nécessaires

app = FastAPI()



app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # C'est pour le debugging. En production, remplacez "*" par votre domaine frontend.
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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

    # Triez les tasseaux dans l'ordre décroissant de longueur
    tasseaux = sorted(tasseaux, key=lambda x: x[0], reverse=True)
    
    cuts = []

    # Variables
    x = []  # x[i] sera égal au nombre de tasseaux de longueur tasseaux[i][0] utilisés
    for _, quantite in tasseaux:
        x.append(solver.IntVar(0, quantite, ""))
    
    # Contrainte : la somme des longueurs des tasseaux utilisés ne doit pas dépasser bar_length
    constraint_expr = sum(tasseaux[i][0] * x[i] for i in range(len(tasseaux)))
    solver.Add(constraint_expr <= bar_length)

    # Objectif : maximiser la somme des longueurs des tasseaux utilisés, en donnant plus de poids aux tasseaux plus longs, dit autrement on applique une pénalité à chaque tasseau
    objective_expr = sum(tasseaux[i][0] * x[i] for i in range(len(tasseaux))) * bar_length - sum(x[i] for i in range(len(tasseaux)))
    solver.Maximize(objective_expr)
        
    status = solver.Solve()
    
    if status == pywraplp.Solver.OPTIMAL:
        for i in range(len(tasseaux)):
            cuts.extend([tasseaux[i][0]] * int(x[i].solution_value()))
            tasseaux[i] = (tasseaux[i][0], tasseaux[i][1] - int(x[i].solution_value()))
    
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

    # Trier les résultats par le nombre d'utilisation décroissante
    sorted_formatted_cuts = dict(sorted(formatted_cuts.items(), key=lambda item: item[1], reverse=True))

    return sorted_formatted_cuts


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
