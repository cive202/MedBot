import { MapPin, Phone, Award, Stethoscope } from "lucide-react";

/**
 * Shape returned by the trained KNN endpoint (one row of the Nepal medical
 * specialists dataset, plus the haversine distance in km).
 */
export interface Specialist {
  Doctor_ID?: string | number | null;
  Doctor_Name?: string | null;
  Specialty?: string | null;
  Hospital?: string | null;
  City?: string | null;
  Province?: string | null;
  Experience_Years?: number | null;
  Contact_Phone?: string | null;
  Latitude?: number | null;
  Longitude?: number | null;
  Distance_km: number;
}

export default function SpecialistCard({ s }: { s: Specialist }) {
  const km = Number.isFinite(s.Distance_km) ? s.Distance_km.toFixed(1) : "—";
  const cityLine = [s.City, s.Province].filter(Boolean).join(", ");
  const lat = s.Latitude;
  const lon = s.Longitude;
  return (
    <article className="rounded-2xl border border-border/70 bg-white/90 p-4 shadow-sm">
      <header className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="font-semibold text-text truncate">
            {s.Doctor_Name || "Unknown doctor"}
          </div>
          {s.Specialty && (
            <span className="inline-flex items-center gap-1 mt-1 text-[11px] font-semibold uppercase tracking-wider text-[rgb(var(--accent))] bg-orange-50 border border-orange-200 rounded-full px-2 py-0.5">
              <Stethoscope className="w-3 h-3" />
              {s.Specialty}
            </span>
          )}
        </div>
        <div className="shrink-0 text-xs text-muted text-right">
          <div className="font-semibold text-text">{km} km</div>
          <div className="opacity-70">away</div>
        </div>
      </header>

      <dl className="mt-3 grid grid-cols-[80px,1fr] gap-y-1 gap-x-2 text-sm">
        {s.Hospital && (
          <>
            <dt className="text-muted">Hospital</dt>
            <dd className="text-text break-words">{s.Hospital}</dd>
          </>
        )}
        {cityLine && (
          <>
            <dt className="text-muted">Location</dt>
            <dd className="text-text break-words flex items-start gap-1">
              <MapPin className="w-3 h-3 mt-1 shrink-0 text-muted" />
              {cityLine}
            </dd>
          </>
        )}
        {s.Experience_Years != null && (
          <>
            <dt className="text-muted">Experience</dt>
            <dd className="text-text flex items-center gap-1">
              <Award className="w-3 h-3 text-muted" />
              {s.Experience_Years} years
            </dd>
          </>
        )}
        {s.Contact_Phone && (
          <>
            <dt className="text-muted">Phone</dt>
            <dd>
              <a
                href={`tel:${s.Contact_Phone}`}
                className="inline-flex items-center gap-1 text-primary hover:underline"
              >
                <Phone className="w-3 h-3" />
                {s.Contact_Phone}
              </a>
            </dd>
          </>
        )}
        {s.Doctor_ID != null && (
          <>
            <dt className="text-muted">ID</dt>
            <dd className="text-text/80 text-xs font-mono">{s.Doctor_ID}</dd>
          </>
        )}
      </dl>

      {lat != null && lon != null && Number.isFinite(lat) && Number.isFinite(lon) && (
        <a
          href={`https://www.openstreetmap.org/?mlat=${lat}&mlon=${lon}#map=16/${lat}/${lon}`}
          target="_blank"
          rel="noreferrer"
          className="mt-3 inline-block text-xs text-primary hover:underline"
        >
          View on map ↗
        </a>
      )}
    </article>
  );
}
