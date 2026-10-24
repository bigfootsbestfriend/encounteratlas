// Mystery of the day (site/sections/motd.py, /mystery-of-the-day/): one case a day from a shuffled list.
// motd_items.js is written by the site build from data/motd_schedule.json; keep the pick logic in step with
// motd.py and site/static/motd.js. A day is the UTC day number (Unix ms / 86400000, rounded down).
// Each era starts on a day and cycles through its order; a new era starts the day after the case list changes,
// so past days keep the case they had.
import { MOTD } from './motd_items.js';

export const MOTD_SLUGS = new Set(MOTD.eras.flatMap((e) => e.order));

export const utcDay = (ms = Date.now()) => Math.floor(ms / 86400000);

export function motdSlugFor(day) {
  let era = null;
  for (const e of MOTD.eras) if (e.from <= day) era = e;
  if (!era || !era.order.length) return null;
  return era.order[(day - era.from) % era.order.length];
}

// Today's case keeps its results hidden from everyone until the next UTC day ("facts revealed next day").
export const motdIsToday = (slug, ms = Date.now()) => motdSlugFor(utcDay(ms)) === slug;
