from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp
import requests

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class Location(BaseModel):
    lat: float
    lon: float
    demand: int = 0

class Vehicle(BaseModel):
    id: int
    capacity: int

class VrpRequest(BaseModel):
    locations: list[Location]
    vehicles: list[Vehicle]

def create_distance_matrix_osrm(locations: list[Location]):
    """
    Using free OSRM API
    """
    coords_str = ";".join([f"{loc.lon},{loc.lat}" for loc in locations])
    url = f"http://router.project-osrm.org/table/v1/driving/{coords_str}"
    params = {'annotations': 'distance,duration'}
    
    response = requests.get(url, params=params)
    if response.status_code != 200:
        raise HTTPException(status_code=500, detail="Error fetching distance matrix from OSRM")
        
    data = response.json()
    if 'distances' not in data:
         raise HTTPException(status_code=500, detail="Invalid response from OSRM")

    return [[int(round(x)) for x in row] for row in data['distances']]

def create_data_model(locations: list[Location], vehicles: list[Vehicle]):
    """Stores the data for the problem."""
    data = {}

    # Validate inputs
    total_locations = len(locations)
    
    if total_locations < 2:
         raise HTTPException(status_code=400, detail="At least 2 locations (depot + 1 customer) required")

    distance_matrix = create_distance_matrix_osrm(locations)

    demands = [loc.demand for loc in locations]

    data['distance_matrix'] = distance_matrix
    data['demands'] = demands
    data["num_vehicles"] = len(vehicles)
    data['vehicle_capacities'] = [v.capacity for v in vehicles]
    data["depot"] = 0
    return data

def solve_vrp(locations: list[Location], vehicles: list[Vehicle]):
    data = create_data_model(locations, vehicles)

    manager = pywrapcp.RoutingIndexManager(
        len(data["distance_matrix"]), data["num_vehicles"], data["depot"]
    )
    routing = pywrapcp.RoutingModel(manager)


     # Create and register a transit callback.
    def distance_callback(from_index, to_index):
        """Returns the distance between the two nodes."""
        # Convert from routing variable Index to distance matrix NodeIndex.
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        return data["distance_matrix"][from_node][to_node]

    transit_callback_index = routing.RegisterTransitCallback(distance_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)

    def demand_callback(from_index):
        """Returns the demand of the node."""
        # Convert from routing variable Index to demands NodeIndex.
        from_node = manager.IndexToNode(from_index)
        return data["demands"][from_node]

    demand_callback_index = routing.RegisterUnaryTransitCallback(demand_callback)
    routing.AddDimensionWithVehicleCapacity(
        demand_callback_index,
        0,  # null capacity slack
        data["vehicle_capacities"],  # vehicle maximum capacities
        True,  # start cumul to zero
        "Capacity",
    )

    penalty = 1000000
    for node in range(1, len(data["distance_matrix"])):
        routing.AddDisjunction([manager.NodeToIndex(node)], penalty)


    search_parameters = pywrapcp.DefaultRoutingSearchParameters()
    search_parameters.first_solution_strategy = (
        routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    )
    search_parameters.local_search_metaheuristic = (
        routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    )
    search_parameters.time_limit.FromSeconds(5)

    solution = routing.SolveWithParameters(search_parameters)
    
    if solution:
        return process_solution(data, manager, routing, solution)
    else:
        status = routing.status()
        status_map = {
            0: "ROUTING_NOT_SOLVED",
            1: "ROUTING_SUCCESS",
            2: "ROUTING_FAIL",
            3: "ROUTING_FAIL_TIMEOUT",
            4: "ROUTING_INVALID",
            5: "ROUTING_INFEASIBLE"
        }
        status_str = status_map.get(status, f"UNKNOWN_STATUS_{status}")
        logger.warning(f"Solver failed with status: {status_str}")
        raise HTTPException(status_code=404, detail=f"No solution found. Solver status: {status_str}")

def process_solution(data, manager, routing, solution):
    """Returns solution as a dictionary."""
    result = {"objective": solution.ObjectiveValue(), "routes": []}
    total_distance = 0
    total_load = 0
    max_route_distance = 0 
    dropped_nodes = []
    for node in range(routing.Size()):
        if routing.IsStart(node) or routing.IsEnd(node):
            continue
        if solution.Value(routing.NextVar(node)) == node:
            dropped_nodes.append(manager.IndexToNode(node))
            
    result["dropped_nodes"] = dropped_nodes
    
    for vehicle_id in range(data["num_vehicles"]):
        index = routing.Start(vehicle_id)
        route_nodes = []
        route_distance = 0
        route_load = 0
        while not routing.IsEnd(index):
            node_index = manager.IndexToNode(index)
            route_nodes.append(node_index)
            previous_index = index
            index = solution.Value(routing.NextVar(index))
            route_distance += routing.GetArcCostForVehicle(
                previous_index, index, vehicle_id
            )
        route_nodes.append(manager.IndexToNode(index))
        result["routes"].append({
            "vehicle_id": vehicle_id,
            "route": route_nodes,
            "distance": route_distance
        })
    return result

import logging
import traceback

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@app.post("/solve")
def solve_endpoint(request: VrpRequest):
    try:
        all_routes = []
        current_locations = request.locations
        # Keep track of original indices to map back result
        current_indices = list(range(len(request.locations)))
        
        trip_id = 1
        max_trips = 5
        
        while trip_id <= max_trips:
            # Solve for current locations
            result = solve_vrp(current_locations, request.vehicles)
            
            # Map route indices back to original and add trip_id
            for route in result.get("routes", []):
                mapped_route = []
                for node_idx in route["route"]:
                    if node_idx < len(current_indices):
                        mapped_route.append(current_indices[node_idx])
                    else:
                         mapped_route.append(node_idx) # Should not happen
                
                route["route"] = mapped_route
                route["trip_id"] = trip_id
                all_routes.append(route)
            
            dropped_indices = result.get("dropped_nodes", [])
            
            if not dropped_indices:
                break
                
            # If we have dropped nodes, prepare next iteration
            new_locations = [current_locations[0]] # Always keep depot
            new_indices = [current_indices[0]]
            
            for idx in dropped_indices:
                if idx < len(current_locations):
                    new_locations.append(current_locations[idx])
                    new_indices.append(current_indices[idx])
            
            if len(new_locations) < 2:
                break
                
            current_locations = new_locations
            current_indices = new_indices
            trip_id += 1
        
        total_distance = sum(route.get("distance", 0) for route in all_routes)
        return {"routes": all_routes, "total_distance": total_distance}
    except HTTPException:
        # Re-raise HTTPExceptions as is (e.g. 404 No Solution)
        raise
    except Exception as e:
        logger.error("An unexpected error occurred during VRP solving:", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
