import { HeartPulse, Droplet, BadgeCheck } from "lucide-react";
import type { BloodGroup, History, Sex, User } from "@/types/user";

interface Props {
  user: User;
}

const SEX_LABEL: Record<Sex, string> = {
  male: "Male",
  female: "Female",
  other: "Other",
  prefer_not_to_say: "—",
};

function computeAge(iso: string | null | undefined): number | null {
  if (!iso) return null;
  const dob = new Date(iso);
  if (Number.isNaN(dob.getTime())) return null;
  const now = new Date();
  let age = now.getFullYear() - dob.getFullYear();
  const m = now.getMonth() - dob.getMonth();
  if (m < 0 || (m === 0 && now.getDate() < dob.getDate())) age -= 1;
  return age >= 0 ? age : null;
}

function bloodGroupBadge(bg: BloodGroup | null | undefined) {
  if (!bg || bg === "unknown") return "—";
  return bg;
}

export default function HealthCard({ user }: Props) {
  const age = computeAge(user.date_of_birth);
  const sex: Sex = user.sex ?? "prefer_not_to_say";
  const h: Partial<History> = user.history ?? {};

  return (
    <article
      className="rounded-3xl p-6 text-white shadow-xl relative overflow-hidden"
      style={{
        background:
          "linear-gradient(135deg, #0f766e 0%, #14b8a6 55%, #ed8936 140%)",
      }}
    >
      {/* Decorative watermark */}
      <HeartPulse
        className="absolute -right-6 -bottom-6 w-40 h-40 opacity-10"
        aria-hidden
      />

      <header className="flex items-start justify-between gap-3">
        <div>
          <div className="text-[11px] font-semibold uppercase tracking-[0.18em] opacity-80">
            MedAssist Health Card
          </div>
          <h2 className="mt-1 text-2xl font-bold">
            {user.full_name || user.username || "—"}
          </h2>
          {user.username && (
            <div className="text-sm opacity-90 mt-0.5 inline-flex items-center gap-1">
              <BadgeCheck className="w-3.5 h-3.5" />@{user.username}
            </div>
          )}
        </div>
        <div className="text-right">
          <div className="text-[11px] uppercase tracking-wider opacity-80">
            Blood group
          </div>
          <div className="inline-flex items-center gap-1.5 mt-1 px-3 py-1 rounded-full bg-white/15 backdrop-blur-sm font-bold">
            <Droplet className="w-4 h-4" />
            {bloodGroupBadge(h.blood_group ?? null)}
          </div>
        </div>
      </header>

      <dl className="mt-5 grid grid-cols-2 sm:grid-cols-4 gap-4 text-sm">
        <Stat label="Age" value={age != null ? `${age}` : "—"} />
        <Stat label="Sex" value={SEX_LABEL[sex]} />
        <Stat label="Conditions" value={`${h.conditions?.length ?? 0}`} />
        <Stat label="Allergies" value={`${h.allergies?.length ?? 0}`} />
      </dl>

      <section className="mt-5 grid grid-cols-1 sm:grid-cols-3 gap-3">
        <ChipBlock title="Conditions" items={h.conditions ?? []} />
        <ChipBlock title="Medications" items={h.medications ?? []} />
        <ChipBlock title="Allergies" items={h.allergies ?? []} />
      </section>

      <footer className="mt-5 flex items-center justify-between text-[11px] opacity-80">
        <span>{user.email}</span>
        <span>ID · {user.id.slice(0, 8)}</span>
      </footer>
    </article>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-[11px] uppercase tracking-wider opacity-80">{label}</div>
      <div className="text-xl font-semibold mt-0.5">{value}</div>
    </div>
  );
}

function ChipBlock({ title, items }: { title: string; items: string[] }) {
  return (
    <div className="rounded-xl bg-white/12 backdrop-blur-sm p-3">
      <div className="text-[11px] uppercase tracking-wider opacity-80 mb-2">
        {title}
      </div>
      {items.length === 0 ? (
        <div className="text-sm opacity-70">None recorded</div>
      ) : (
        <div className="flex flex-wrap gap-1.5">
          {items.map((c) => (
            <span
              key={c}
              className="px-2 py-0.5 rounded-full text-xs bg-white/20 border border-white/25"
            >
              {c}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
