from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Tuple
from fastapi.middleware.cors import CORSMiddleware
from ortools.linear_solver import pywraplp
from collections import Counter
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)

# Necessary dependencies imported
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # This is for debugging. In production, replace "*" with your frontend domain.
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)

class CutRequest(BaseModel):
    bars: List[Tuple[int, int]]
    bar_length: int

@app.post("/optimize/", response_model=dict)
async def optimize(request: CutRequest):
    logging.info(f"Incoming request: {request.json()}")
    
    try:
        cuts, total_waste, total_bars_cut = optimize_cutting(request.bars, request.bar_length)
        cuts_count = format_and_count_cuts(cuts)
        total_bars = sum(cuts_count.values())

        return {
            "cuts": cuts_count, 
            "total_bars": total_bars, 
            "total_waste": total_waste, 
            "total_bars_cut": total_bars_cut
        }

    except Exception as e:
        logging.error(f"Error during optimization: {e}")
        raise HTTPException(status_code=500, detail=str(e))

def optimize_bar(bars, bar_length):
    solver = pywraplp.Solver.CreateSolver('SCIP')
    if not solver:
        return None, bars

    # Sort bars in descending order of length
    bars = sorted(bars, key=lambda x: x[0], reverse=True)

    # Find index of the largest bar with quantity > 0
    idx_max = next((i for i, (length, qty) in enumerate(bars) if qty > 0), None)
    if idx_max is None:
        return [], bars

    # Variables
    x = []  # x[i] will be equal to the number of bars of length bars[i][0] used
    for _, quantity in bars:
        x.append(solver.IntVar(0, quantity, ""))
    
    # Constraint: Must use the largest bar with quantity > 0
    solver.Add(x[idx_max] >= 1)

    # Constraint: sum of bar lengths used must not exceed bar_length
    constraint_expr = sum(bars[i][0] * x[i] for i in range(len(bars)))
    solver.Add(constraint_expr <= bar_length)

    # Objective: maximize the sum of bar lengths used
    solver.Maximize(constraint_expr)

    if solver.Solve() != pywraplp.Solver.OPTIMAL:
        return None, bars

    optimal_length = sum(bars[i][0] * x[i].solution_value() for i in range(len(bars)))

    # Reset solver for the second pass
    solver = pywraplp.Solver.CreateSolver('SCIP')
    x = [solver.IntVar(0, quantity, "") for _, quantity in bars]

    # Constraint: Sum of lengths should equal optimal length
    solver.Add(sum(bars[i][0] * x[i] for i in range(len(bars))) == optimal_length)

    # Constraint: Must use the largest bar with quantity > 0
    solver.Add(x[idx_max] >= 1)

    # New Objective: maximize the sum of (bar quantities used * length^2)
    objective_expr = sum(bars[i][0]**2 * x[i] for i in range(len(bars)))
    solver.Maximize(objective_expr)

    if solver.Solve() != pywraplp.Solver.OPTIMAL:
        return None, bars

    best_cuts = []
    for i in range(len(bars)):
        best_cuts.extend([bars[i][0]] * int(x[i].solution_value()))
        bars[i] = (bars[i][0], bars[i][1] - int(x[i].solution_value()))

    return best_cuts, bars

def optimize_cutting(bars, bar_length):
    sorted_bars = sorted(bars, reverse=True)
    cuts_per_bar = []
    total_waste = 0
    total_cut_bars = 0

    while any(quantity > 0 for _, quantity in sorted_bars):
        cuts, new_bars = optimize_bar(sorted_bars, bar_length)
        if cuts:
            cuts_per_bar.append(cuts)
            sorted_bars = new_bars
            total_waste += bar_length - sum(cuts)
            total_cut_bars += len(cuts)
        else:
            break

    return cuts_per_bar, total_waste, total_cut_bars

def format_and_count_cuts(cuts_per_bar):
    formatted_cuts = {}
    for cuts in cuts_per_bar:
        counts = Counter(cuts)
        formatted_cut = ', '.join(f"{length} x {count}" if count > 1 else f"{length}" for length, count in counts.items())
        formatted_cuts[formatted_cut] = formatted_cuts.get(formatted_cut, 0) + 1

    sorted_formatted_cuts = dict(sorted(formatted_cuts.items(), key=lambda item: item[1], reverse=True))

    return sorted_formatted_cuts

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
