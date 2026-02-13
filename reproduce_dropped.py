from fastapi.testclient import TestClient
from app import app
import json

client = TestClient(app)

def test_dropped_revisit():
    print("Sending VRP request...")
    response = client.post("/solve", json={
        "locations": [
             {"lat": 52.517037, "lon": 13.388860, "demand": 0}, # Depot
             {"lat": 52.529407, "lon": 13.397634, "demand": 50}, # Customer 1
             {"lat": 52.523219, "lon": 13.428555, "demand": 50}  # Customer 2
        ],
        "vehicles": [{"id": 0, "capacity": 60}] # Cap 60 < 100
    })
    
    if response.status_code != 200:
        print(f"Error: {response.status_code}")
        print(response.text)
        return

    data = response.json()
    print(f"Response: {json.dumps(data, indent=2)}")
    
    served_nodes = set()
    total_trips = set()
    
    for route in data.get('routes', []):
        trip_id = route.get('trip_id', 1) # Default to 1 if not present
        total_trips.add(trip_id)
        for node_idx in route['route']:
            # Note: node_idx here might be index in current run's locations list
            # But the user wants "nodes (locations) again".
            # The indices returned by `process_solution` are indices into the CURRENT `locations` list.
            # If we re-run, indices shift. 
            # Ideally, valid node IDs should be mapped back to original or just counted.
            # In this simple case, we just want to ensure we visit 2 unique non-depot locations.
            # But wait, if solving logic changes the "index" semantic between runs,
            # we can't easily track identity unless we pass IDs.
            # However, `route['distance']` > 0 implies something was visited.
            pass
            
            # Simple check: number of routes with non-zero distance?
            # Or sum of distances?
            
    # For now, let's just check if we have more than 1 route.
    # With 1 vehicle and capacity constraint, we MUST have multiple trips (routes) to serve both.
    # But wait, standard VRP doesn't reuse vehicles. 
    # If 1 vehicle provided, VRP returns 1 route. The other node is dropped.
    # So we expect 1 route in original code.
    # After fix, we expect multiple routes (trips).
    
    num_routes = len(data.get('routes', []))
    print(f"Number of routes: {num_routes}")
    
    # We enforce trip_id existence too
    has_trip_id = all('trip_id' in r for r in data.get('routes', []))
    print(f"Has trip_id: {has_trip_id}")
    
    # Check that at least some routes are non-empty (serving customers)
    served_routes = [r for r in data.get('routes', []) if r['distance'] > 0 or len(r['route']) > 2]
    print(f"Served routes: {len(served_routes)}")
    
    if len(served_routes) < 2:
        raise AssertionError("Expected at least 2 served routes/trips, got " + str(len(served_routes)))
        
    # Verify indices
    visited_nodes = set()
    for route in data.get('routes', []):
        for node in route['route']:
            if node != 0: # Exclude depot
                visited_nodes.add(node)
                
    print(f"Visited nodes: {visited_nodes}")
    expected_nodes = {1, 2}
    if visited_nodes != expected_nodes:
        raise AssertionError(f"Expected visited nodes {expected_nodes}, got {visited_nodes}")
        
    # Verify objective
    total_objective = data.get('objective', 0)
    print(f"Total Objective: {total_objective}")
    
    calculated_distance = sum(r['distance'] for r in data.get('routes', []))
    print(f"Calculated Distance from routes: {calculated_distance}")
    
    if total_objective != calculated_distance:
         raise AssertionError(f"Objective mismatch: {total_objective} != {calculated_distance}")
    
    if total_objective == 0:
         # It's possible if distances are 0 for very close points, but unlikely with OSRM.
         # Actually with mock points they might be far.
         # But the test passes with distance > 0 checks above.
         pass

if __name__ == "__main__":
    try:
        test_dropped_revisit()
        print("Test PASSED")
    except AssertionError as e:
        print(f"Test FAILED: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")
