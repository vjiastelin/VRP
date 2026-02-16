import React, { useState } from 'react'
import { MapContainer, TileLayer, Marker, Popup, Polyline, useMapEvents, Tooltip, CircleMarker } from 'react-leaflet'
import axios from 'axios'
import 'leaflet/dist/leaflet.css'
// Removed App.css import as we are using Tailwind via index.css

// Fix for default marker icon
import L from 'leaflet';
import icon from 'leaflet/dist/images/marker-icon.png';
import iconShadow from 'leaflet/dist/images/marker-shadow.png';

let DefaultIcon = L.icon({
  iconUrl: icon,
  shadowUrl: iconShadow,
  iconSize: [25, 41],
  iconAnchor: [12, 41]
});

L.Marker.prototype.options.icon = DefaultIcon;

function LocationMarker({ points, setPoints }) {
  useMapEvents({
    click(e) {
      setPoints(e.latlng)
    },
  })

  return points.map((pos, idx) => (
    <Marker key={`input-${idx}`} position={pos}>
      <Popup>
        Point {idx + 1}<br />
        Demand: {pos.demand}
      </Popup>
    </Marker>
  ))
}

// Component to visualize route stops with vehicle info
function RouteVisualization({ solution, points }) {
  if (!solution || !points.length) return null;

  // Use a color palette for different vehicles
  const colors = ['blue', 'red', 'green', 'purple', 'orange', 'darkred', 'cadetblue'];

  return (
    <>
      {solution.routes.map((route, vIdx) => {
        const color = colors[vIdx % colors.length];
        const routePoints = route.route.map(idx => points[parseInt(idx)]);

        return (
          <React.Fragment key={`vehicle-${vIdx}`}>
            <Polyline positions={routePoints} color={color} weight={5} opacity={0.7} />
            {route.route.map((nodeIdx, seqIdx) => {
              const pos = points[parseInt(nodeIdx)];
              const isDepot = parseInt(nodeIdx) === 0;

              return (
                <CircleMarker
                  key={`v${vIdx}-s${seqIdx}`}
                  center={pos}
                  radius={isDepot ? 10 : 6}
                  pathOptions={{ color: color, fillColor: color, fillOpacity: 0.8 }}
                >
                  <Tooltip permanent direction="top" offset={[0, -10]} className="route-tooltip">
                    V{route.vehicle_id} (T{route.trip_id}): #{seqIdx}
                  </Tooltip>
                </CircleMarker>
              )
            })}
          </React.Fragment>
        );
      })}
    </>
  );
}

function App() {
  const [points, setPoints] = useState([])
  const [numVehicles, setNumVehicles] = useState(1)
  const [vehicleCapacity, setVehicleCapacity] = useState(50)
  const [error, setError] = useState(null)
  const [solution, setSolution] = useState(null)
  const [loading, setLoading] = useState(false)

  const handlePointClick = (newPoint) => {
    // Add demand property to the new point
    const pointWithDemand = { ...newPoint, demand: 0 }
    setPoints([...points, pointWithDemand])
  }

  const handleUpdateDemand = (index, value) => {
    const newPoints = [...points]
    newPoints[index].demand = parseInt(value) || 0
    setPoints(newPoints)
  }

  const removePoint = (index) => {
    const newPoints = points.filter((_, i) => i !== index)
    setPoints(newPoints)
  }

  const handleSolve = async () => {
    if (points.length < 2) {
      setError("Please add at least 2 points")
      return
    }
    setError(null)
    setLoading(true)

    // Prepare Locations
    const locations = points.map(p => ({
      lat: p.lat,
      lon: p.lng,
      demand: p.demand
    }));

    // Prepare Vehicles
    // Parse capacity input: "10, 20" -> [10, 20]
    // If single value "50", and numVehicles 2 -> [50, 50]
    let capacities = [];
    if (vehicleCapacity.toString().includes(',')) {
      capacities = vehicleCapacity.toString().split(',').map(s => parseInt(s.trim())).filter(n => !isNaN(n));
    } else {
      const cap = parseInt(vehicleCapacity);
      if (!isNaN(cap)) {
        capacities = Array(parseInt(numVehicles)).fill(cap);
      }
    }

    // If user entered fewer capacities than numVehicles, cycle or fill with last?
    // Let's strict: if comma list, ignore numVehicles or require match.
    // Better UX: If comma list, use that size as numVehicles. If single, use numVehicles.

    let vehicles = [];
    if (vehicleCapacity.toString().includes(',')) {
      // Use the explicit list
      vehicles = capacities.map((cap, i) => ({ id: i, capacity: cap }));
      // Update numVehicles for consistency in UI (optional, but good for feedback)
      // setNumVehicles(vehicles.length); 
    } else {
      // Use numVehicles count with uniform capacity
      vehicles = Array.from({ length: parseInt(numVehicles) }, (_, i) => ({
        id: i,
        capacity: capacities[0] || 50
      }));
    }

    try {
      // Use the hostname from user's last edit
      const response = await axios.post('/solve', {
        locations: locations,
        vehicles: vehicles
      })

      setSolution(response.data)

    } catch (err) {
      console.error(err)
      setError(err.response?.data?.detail || "Failed to solve VRP. Make sure backend is running.")
    } finally {
      setLoading(false)
    }
  }

  const handleClear = () => {
    setPoints([])
    setSolution(null)
    setError(null)
  }

  return (
    <div className="flex w-full h-screen font-sans text-gray-900 bg-gray-100">
      {/* Sidebar */}
      <div className="w-80 h-full bg-white shadow-xl flex flex-col p-6 z-[1000] relative overflow-y-auto">
        <h1 className="text-2xl font-bold mb-2 text-gray-800">VRP Solver</h1>
        <p className="text-gray-500 mb-6 text-sm">Click on the map to add delivery points.</p>

        <div className="mb-4 space-y-4">
          <div>
            <label className="block text-sm font-semibold text-gray-700 mb-1">Number of Vehicles</label>
            <input
              type="number"
              min="1"
              max="10"
              value={numVehicles}
              onChange={(e) => setNumVehicles(e.target.value)}
              className="w-full p-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 focus:outline-none transition"
            />
          </div>
          <div>
            <label className="block text-sm font-semibold text-gray-700 mb-1">Vehicle Capacity</label>
            <input
              type="text"
              placeholder="e.g. 50 or 15, 20"
              value={vehicleCapacity}
              onChange={(e) => setVehicleCapacity(e.target.value)}
              className="w-full p-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 focus:outline-none transition"
            />
          </div>
        </div>

        {/* Points List */}
        <div className="mb-6 flex-grow overflow-y-auto max-h-60 border-t border-b border-gray-100 py-2">
          <h3 className="text-sm font-semibold text-gray-700 mb-2">Points & Demands</h3>
          {points.length === 0 ? (
            <p className="text-xs text-gray-400 italic">No points added yet.</p>
          ) : (
            <div className="space-y-2">
              {points.map((p, idx) => (
                <div key={idx} className="flex items-center gap-2 text-sm">
                  <span className="w-6 text-gray-500 font-mono">{idx === 0 ? 'D' : idx}</span>
                  <div className="flex-1">
                    <span className="text-xs text-gray-400 mr-2">Dem:</span>
                    <input
                      type="number"
                      min="0"
                      value={p.demand}
                      onChange={(e) => handleUpdateDemand(idx, e.target.value)}
                      className="w-16 p-1 border border-gray-300 rounded text-center text-xs"
                    />
                  </div>
                  <button onClick={() => removePoint(idx)} className="text-red-400 hover:text-red-600">×</button>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="flex gap-3 mb-4 mt-auto pt-4 border-t border-gray-100">
          <button
            onClick={handleSolve}
            disabled={points.length < 2 || loading}
            className={`flex-1 px-4 py-2 rounded text-white font-medium transition ${points.length < 2 || loading
              ? 'bg-blue-300 cursor-not-allowed'
              : 'bg-blue-600 hover:bg-blue-700 shadow-md transform active:scale-95'
              }`}
          >
            {loading ? 'Solving...' : 'Solve'}
          </button>
          <button
            onClick={handleClear}
            className="px-4 py-2 bg-gray-100 text-gray-700 rounded font-medium hover:bg-gray-200 transition shadow-sm border border-gray-200"
          >
            Clear
          </button>
        </div>

        {error && (
          <div className="mb-4 p-3 bg-red-50 text-red-700 text-sm rounded border border-red-100">
            {error}
          </div>
        )}

        {solution && (
          <div className="mt-4 border-t border-gray-100 pt-4">
            <h3 className="text-lg font-semibold mb-3 text-gray-800">Results</h3>
            <div className="mb-4 p-3 bg-blue-50 text-blue-800 rounded text-sm font-medium">
              Total Distance: <span className="font-bold">{solution.total_distance}m</span>
            </div>

            <div className="space-y-3">
              {solution.routes.map((r, idx) => (
                <div key={`${r.vehicle_id}-${r.trip_id}-${idx}`} className="p-3 bg-gray-50 rounded border border-gray-100 shadow-sm">
                  <div className="flex justify-between items-center mb-1">
                    <span className="font-bold text-gray-700">Vehicle {r.vehicle_id} <span className="text-xs font-normal text-gray-500">(Trip {r.trip_id})</span></span>
                    <span className="text-xs font-mono bg-gray-200 px-2 py-0.5 rounded text-gray-600">{r.distance}m</span>
                  </div>
                  <p className="text-xs text-gray-500 leading-relaxed font-mono mt-2 break-words">
                    {r.route.join(' → ')}
                  </p>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Map */}
      <div className="flex-grow h-full relative z-0">
        <MapContainer center={[57.150507, 65.550726]} zoom={13} style={{ height: "100%", width: "100%" }}>
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          {!solution && <LocationMarker points={points} setPoints={handlePointClick} />}
          <RouteVisualization solution={solution} points={points} />
        </MapContainer>
      </div>
    </div>
  )
}

export default App
