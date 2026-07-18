/**
 * Proxy OpenRouteService — calcule un itinéraire voiture qui évite des polygones.
 *
 * Env Vercel : ORS_API_KEY (clé gratuite sur https://openrouteservice.org/)
 *
 * POST JSON body:
 *   { origin: {lat, lon}, destination: {lat, lon}, avoid: GeoJSON FeatureCollection|Geometry }
 * Response:
 *   { coordinates: [[lon,lat],...], distanceM, durationS }
 */

const ORS_URL = "https://api.openrouteservice.org/v2/directions/driving-car/geojson";

function cors(res) {
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Methods", "POST, OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type");
}

function featuresToMultiPolygon(avoid) {
  if (!avoid) return null;
  if (avoid.type === "MultiPolygon") return avoid;
  if (avoid.type === "Polygon") {
    return { type: "MultiPolygon", coordinates: [avoid.coordinates] };
  }
  const features = avoid.type === "FeatureCollection"
    ? avoid.features || []
    : avoid.type === "Feature"
      ? [avoid]
      : [];
  const polygons = [];
  for (const f of features) {
    const g = f && f.geometry;
    if (!g) continue;
    if (g.type === "Polygon") polygons.push(g.coordinates);
    else if (g.type === "MultiPolygon") polygons.push(...g.coordinates);
  }
  if (!polygons.length) return null;
  return { type: "MultiPolygon", coordinates: polygons };
}

module.exports = async function handler(req, res) {
  cors(res);
  if (req.method === "OPTIONS") {
    res.status(204).end();
    return;
  }
  if (req.method !== "POST") {
    res.status(405).json({ error: "POST only" });
    return;
  }

  const key = process.env.ORS_API_KEY;
  if (!key) {
    res.status(503).json({
      error: "ORS_API_KEY manquante. Ajoutez la clé dans les variables d'environnement Vercel.",
    });
    return;
  }

  let body = req.body;
  if (typeof body === "string") {
    try {
      body = JSON.parse(body);
    } catch {
      res.status(400).json({ error: "JSON invalide" });
      return;
    }
  }

  const origin = body && body.origin;
  const destination = body && body.destination;
  if (
    !origin || typeof origin.lat !== "number" || typeof origin.lon !== "number" ||
    !destination || typeof destination.lat !== "number" || typeof destination.lon !== "number"
  ) {
    res.status(400).json({ error: "origin et destination {lat, lon} requis" });
    return;
  }

  const avoidPolygons = featuresToMultiPolygon(body.avoid);
  const payload = {
    coordinates: [
      [origin.lon, origin.lat],
      [destination.lon, destination.lat],
    ],
  };
  if (avoidPolygons) {
    payload.options = { avoid_polygons: avoidPolygons };
  }

  try {
    const orsRes = await fetch(ORS_URL, {
      method: "POST",
      headers: {
        Authorization: key,
        "Content-Type": "application/json",
        Accept: "application/json, application/geo+json",
      },
      body: JSON.stringify(payload),
    });

    const text = await orsRes.text();
    let data;
    try {
      data = JSON.parse(text);
    } catch {
      res.status(502).json({ error: "Réponse ORS illisible", detail: text.slice(0, 300) });
      return;
    }

    if (!orsRes.ok) {
      const msg =
        (data && data.error && (data.error.message || data.error)) ||
        "Échec OpenRouteService";
      res.status(orsRes.status === 404 ? 422 : 502).json({
        error: String(msg),
        detail: data,
      });
      return;
    }

    const feature = data.features && data.features[0];
    if (!feature || !feature.geometry || !feature.geometry.coordinates) {
      res.status(502).json({ error: "Itinéraire vide" });
      return;
    }

    const summary = (feature.properties && feature.properties.summary) || {};
    res.status(200).json({
      coordinates: feature.geometry.coordinates,
      distanceM: summary.distance != null ? summary.distance : null,
      durationS: summary.duration != null ? summary.duration : null,
    });
  } catch (err) {
    res.status(502).json({
      error: "Erreur réseau vers OpenRouteService",
      detail: String(err && err.message ? err.message : err),
    });
  }
};
