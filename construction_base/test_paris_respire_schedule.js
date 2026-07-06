#!/usr/bin/env node
/** Tests horaires Paris Respire (logique alignée sur index.html). */
const PARIS_WEEKDAY_IDX = { Sun: 0, Mon: 1, Tue: 2, Wed: 3, Thu: 4, Fri: 5, Sat: 6 };
const PARIS_RESPIRE_BUFFER_MIN = 60;

function parisDateParts(now) {
  const parts = { year: 0, month: 0, day: 0, hour: 0, minute: 0, weekday: "", weekdayIdx: -1 };
  new Intl.DateTimeFormat("en-US", {
    timeZone: "Europe/Paris",
    weekday: "short",
    year: "numeric",
    month: "numeric",
    day: "numeric",
    hour: "numeric",
    minute: "numeric",
    hour12: false,
  }).formatToParts(now).forEach((p) => {
    if (p.type !== "literal") parts[p.type] = p.value;
  });
  parts.year = +parts.year;
  parts.month = +parts.month;
  parts.day = +parts.day;
  parts.hour = +parts.hour;
  parts.minute = +parts.minute;
  parts.weekdayIdx = PARIS_WEEKDAY_IDX[parts.weekday] ?? -1;
  return parts;
}

function parisWeekdayOn(year, month, day) {
  const wd = new Intl.DateTimeFormat("en-US", {
    timeZone: "Europe/Paris",
    weekday: "short",
  }).format(new Date(Date.UTC(year, month - 1, day, 12, 0, 0)));
  return PARIS_WEEKDAY_IDX[wd] ?? -1;
}

function lastSundayOfMonthParis(year, month) {
  const lastDay = new Date(year, month, 0).getDate();
  for (let d = lastDay; d >= 1; d--) {
    if (parisWeekdayOn(year, month, d) === 0) return d;
  }
  return 0;
}

function firstSundayOnOrAfterParis(year, month, startDay) {
  const lastDay = new Date(year, month, 0).getDate();
  for (let d = startDay; d <= lastDay; d++) {
    if (parisWeekdayOn(year, month, d) === 0) return d;
  }
  return 0;
}

function parseParisRespireHourToken(token) {
  const m = String(token || "").match(/(\d{1,2})\s*h(?:\s*(\d{2}))?/i);
  if (!m) return null;
  const h = +m[1];
  const min = m[2] ? +m[2] : 0;
  if (h > 23 || min > 59) return null;
  return h * 60 + min;
}

function parseParisRespireHourRange(text) {
  if (!text || typeof text !== "string") return null;
  const t = text.trim();
  if (/\//.test(t) || /12h\s*-\s*1h/i.test(t)) return null;
  const matches = [...t.matchAll(/(\d{1,2})\s*h(?:\s*(\d{2}))?/gi)];
  if (matches.length < 2) return null;
  const startMin = parseParisRespireHourToken(matches[0][0]);
  const endMin = parseParisRespireHourToken(matches[1][0]);
  if (startMin == null || endMin == null || endMin <= startMin) return null;
  return { startMin, endMin };
}

function isParisRespireJourMatch(code, parts) {
  const wd = parts.weekdayIdx;
  if (wd < 0) return false;
  const c = String(code || "").trim();
  if (c === "01") return wd === 0;
  if (c === "03") return wd === 3;
  if (c === "05") return wd === 0 && parts.day <= 7;
  if (c === "10") return wd === 5 || wd === 6;
  if (c === "11") return wd === 6 || wd === 0;
  return false;
}

function isParisRespireJourExcluded(props, parts) {
  const saison = String(props.periode_estivale || "").toLowerCase();
  if (/sauf\s+1er\s+dimanche/.test(saison) && parts.weekdayIdx === 0 && parts.day <= 7) return true;
  return false;
}

function isParisRespireSaisonActive(periode, parts) {
  if (!periode) return false;
  const p = periode.toLowerCase().normalize("NFD").replace(/\p{M}/gu, "").replace(/œ/g, "oe");
  const { year, month, day } = parts;
  if (/avril/.test(p) && /septembre/.test(p) && !/dernier dimanche de mars/.test(p) && !/1er dimanche d.?avril/.test(p)) {
    return month >= 4 && month <= 9;
  }
  if (/avril.{0,6}a[oô]ut/.test(p)) return month >= 4 && month <= 8;
  if (/juillet.{0,6}a[oô]ut/.test(p)) return month >= 7 && month <= 8;
  if (/juin.{0,6}septembre/.test(p)) return month >= 6 && month <= 9;
  if (/dernier dimanche de mars/.test(p) && /novembre/.test(p)) {
    const startD = lastSundayOfMonthParis(year, 3);
    if (!startD) return false;
    if (month < 3) return false;
    if (month > 3 && month < 11) return true;
    if (month === 3) return day >= startD;
    if (month === 11) return true;
    return false;
  }
  if (/1er dimanche d.?avril/.test(p) && /dernier dim/.test(p) && /septembre/.test(p)) {
    const startD = firstSundayOnOrAfterParis(year, 4, 1);
    const endD = lastSundayOfMonthParis(year, 9);
    if (!startD || !endD) return false;
    const afterStart = month > 4 || (month === 4 && day >= startD);
    const beforeEnd = month < 9 || (month === 9 && day <= endD);
    return afterStart && beforeEnd;
  }
  return false;
}

function resolveParisRespireHours(props, parts) {
  const type = String(props.type_secteurs || "").trim();
  const saison = props.periode_estivale;
  const hAnnee = props.horaires_annee;
  const hEte = props.horaires_ete;
  if (type === "Dates spécifiques" || props.dates_specifiques) return null;
  if (type === "Estival" && !hAnnee) {
    if (!saison || !hEte || !isParisRespireSaisonActive(saison, parts)) return null;
    return hEte;
  }
  if (saison && hEte && isParisRespireSaisonActive(saison, parts)) return hEte;
  if (hAnnee) return hAnnee;
  return null;
}

function isMinutesInParisRespireWindow(minutes, startMin, endMin, bufferMin) {
  const start = Math.max(0, startMin - bufferMin);
  const end = Math.min(24 * 60, endMin + bufferMin);
  return minutes >= start && minutes <= end;
}

function isParisRespireZoneActiveNow(props, now) {
  if (!props) return false;
  const parts = parisDateParts(now);
  if (isParisRespireJourExcluded(props, parts)) return false;
  if (!isParisRespireJourMatch(props.jours, parts)) return false;
  const hoursText = resolveParisRespireHours(props, parts);
  if (!hoursText) return false;
  const range = parseParisRespireHourRange(hoursText);
  if (!range) return false;
  const minutes = parts.hour * 60 + parts.minute;
  return isMinutesInParisRespireWindow(minutes, range.startMin, range.endMin, PARIS_RESPIRE_BUFFER_MIN);
}

const marais = {
  nom: "MARAIS",
  type_secteurs: "Toute l'année",
  jours: "01",
  horaires_annee: "de 10h à 18h",
  periode_estivale: "avril-septembre (sauf 1er dimanche du mois)",
  horaires_ete: "de 10h à 19h30",
};

const tests = [
  { label: "Marais 2e dimanche midi juillet", at: "2026-07-12T12:00:00+02:00", want: true },
  { label: "Marais 2e dimanche 09h30 (buffer -1h)", at: "2026-07-12T09:30:00+02:00", want: true },
  { label: "Marais 1er dimanche juillet (exclu)", at: "2026-07-05T12:00:00+02:00", want: false },
  { label: "Marais lundi midi", at: "2026-07-06T12:00:00+02:00", want: false },
  { label: "Marais dimanche 21h (hors buffer)", at: "2026-07-12T21:00:00+02:00", want: false },
  { label: "Foire du Trône (doute)", at: "2026-07-05T12:00:00+02:00", want: false, props: {
    type_secteurs: "Dates spécifiques",
    jours: "03",
    horaires_annee: "12h-1h / 12h-23h",
    dates_specifiques: "Pendant la Foire du Trône",
  }},
];

let failed = 0;
for (const t of tests) {
  const props = t.props || marais;
  const got = isParisRespireZoneActiveNow(props, new Date(t.at));
  const ok = got === t.want;
  if (!ok) {
    failed++;
    console.error(`FAIL ${t.label}: got ${got}, want ${t.want}`);
  } else {
    console.log(`OK   ${t.label}`);
  }
}
process.exit(failed ? 1 : 0);
