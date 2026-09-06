import { useEffect, useState } from "react";
import { Search, MapPin, Loader2 } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { api, apiErrorMessage } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import SpecialistCard, { type Specialist } from "@/components/SpecialistCard";

interface SpecialtiesResponse {
  specialties: string[];
}

interface StatsResponse {
  trained_rows: number;
  specialties: number;
}

interface SearchResponse {
  specialty: string | null;
  lat: number;
  lon: number;
  k: number;
  results: Specialist[];
}

export default function Specialists() {
  const { user } = useAuth();
  const [lat, setLat] = useState<string>("");
  const [lon, setLon] = useState<string>("");
  const [specialty, setSpecialty] = useState<string>("");
  const [k, setK] = useState(5);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [results, setResults] = useState<Specialist[] | null>(null);
  const [info, setInfo] = useState<string>(
    "Share a location and pick a specialty to query the trained KNN model.",
  );

  const specialtiesQ = useQuery({
    queryKey: ["knn-specialties"],
    queryFn: async () => (await api.get<SpecialtiesResponse>("/api/location/specialties")).data,
  });
  const statsQ = useQuery({
    queryKey: ["knn-stats"],
    queryFn: async () => (await api.get<StatsResponse>("/api/location/stats")).data,
  });

  useEffect(() => {
    if (user?.location?.lat != null && user?.location?.lon != null) {
      setLat(user.location.lat.toFixed(6));
      setLon(user.location.lon.toFixed(6));
      setInfo("Using your saved profile location. Pick a specialty and search.");
    }
  }, [user?.location?.lat, user?.location?.lon]);

  function useBrowserLocation() {
    if (!navigator.geolocation) {
      setInfo("Browser geolocation is not available.");
      return;
    }
    setInfo("Requesting browser location…");
    navigator.geolocation.getCurrentPosition(
      (p) => {
        setLat(p.coords.latitude.toFixed(6));
        setLon(p.coords.longitude.toFixed(6));
        setInfo("Location filled. Run search when ready.");
      },
      () => setInfo("Could not read browser location."),
      { timeout: 8000 },
    );
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!lat || !lon) {
      setErr("Please share a location first.");
      return;
    }
    setBusy(true);
    setErr(null);
    setResults(null);
    try {
      const r = await api.get<SearchResponse>("/api/location/nearby-specialists", {
        params: {
          ...(specialty ? { specialty } : {}),
          lat: Number(lat),
          lon: Number(lon),
          k,
        },
      });
      setResults(r.data.results);
      setInfo(
        r.data.results.length
          ? `${r.data.results.length} doctor${r.data.results.length === 1 ? "" : "s"} found, sorted by distance.`
          : "No doctors matched — try a different specialty.",
      );
    } catch (e) {
      setErr(apiErrorMessage(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="max-w-6xl mx-auto px-6 py-8">
      <header className="mb-6 flex flex-col md:flex-row md:items-end md:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Find a specialist</h1>
          <p className="text-muted text-sm mt-1">
            KNN match against the trained Nepal medical specialists dataset.
          </p>
        </div>
        {statsQ.data && (
          <div className="text-right text-sm text-muted glass px-4 py-2">
            <div>
              <span className="text-text font-semibold">
                {statsQ.data.trained_rows.toLocaleString()}
              </span>{" "}
              doctors indexed
            </div>
            <div className="opacity-80">{statsQ.data.specialties} specialties</div>
          </div>
        )}
      </header>

      <section className="grid grid-cols-1 lg:grid-cols-[360px,1fr] gap-5 items-start">
        <form onSubmit={submit} className="glass p-5 grid gap-3">
          <label className="grid gap-1 text-sm">
            <span className="text-muted">Latitude</span>
            <input
              type="number"
              step="0.000001"
              value={lat}
              onChange={(e) => setLat(e.target.value)}
              placeholder="27.717200"
              required
            />
          </label>
          <label className="grid gap-1 text-sm">
            <span className="text-muted">Longitude</span>
            <input
              type="number"
              step="0.000001"
              value={lon}
              onChange={(e) => setLon(e.target.value)}
              placeholder="85.324000"
              required
            />
          </label>
          <label className="grid gap-1 text-sm">
            <span className="text-muted">Specialty</span>
            <select value={specialty} onChange={(e) => setSpecialty(e.target.value)}>
              <option value="">Any specialty</option>
              {specialtiesQ.data?.specialties.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </label>
          <label className="grid gap-1 text-sm">
            <span className="text-muted">Results</span>
            <input
              type="number"
              min={1}
              max={25}
              value={k}
              onChange={(e) => setK(Math.max(1, Math.min(25, Number(e.target.value) || 5)))}
            />
          </label>

          <div className="grid grid-cols-2 gap-2 pt-1">
            <button type="submit" className="btn-primary disabled:opacity-50" disabled={busy}>
              {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
              Search
            </button>
            <button type="button" className="btn-ghost" onClick={useBrowserLocation} disabled={busy}>
              <MapPin className="w-4 h-4" />
              Use my location
            </button>
          </div>

          {err && (
            <div className="text-sm text-red-700 border border-red-300 bg-red-50 rounded-lg px-3 py-2">
              {err}
            </div>
          )}
        </form>

        <section className="glass p-5 min-h-[420px]">
          <div className="flex items-center justify-between mb-3 gap-3">
            <h2 className="text-lg font-semibold">Nearest doctors</h2>
            <span className="text-sm text-muted text-right">{info}</span>
          </div>

          {results === null && !busy && (
            <div className="text-muted text-sm py-12 text-center">
              Run a search to see results.
            </div>
          )}
          {busy && (
            <div className="text-muted text-sm py-12 text-center flex items-center justify-center gap-2">
              <Loader2 className="w-4 h-4 animate-spin" />
              Querying KNN…
            </div>
          )}
          {results && results.length > 0 && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {results.map((s, i) => (
                <SpecialistCard key={`${s.Doctor_ID ?? i}-${s.Latitude},${s.Longitude}`} s={s} />
              ))}
            </div>
          )}
        </section>
      </section>
    </div>
  );
}
