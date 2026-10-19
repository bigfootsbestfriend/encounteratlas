# Historic encounters: sources and licences

`data/historic.json` holds strange-creature, sea-serpent, wild-man, phantom-light and mystery-airship
reports from **US newspapers printed before 1927**. It is built by `collector/historic.py` and powers the
/history/ pages (`site/sections/historic.py`).

## Newspaper pages (public domain)

- **Library of Congress, Chronicling America** (National Digital Newspaper Program):
  https://www.loc.gov/collections/chronicling-america/
- Every page cited is a US newspaper published before 1927, so it is in the public domain in the US.
  LoC states it is unaware of any copyright restrictions on these historic newspapers.
- Each case keeps its citation: newspaper title, place of publication, date, page number and a link to the page
  scan at the Library of Congress, in the form
  `https://www.loc.gov/resource/<lccn>/<date>/ed-<n>/?sp=<sequence>`.
  `sequence` is the page's image sequence in that issue (the scan file number). It usually matches the printed
  page number, but not always.

## Full-text search: American Stories (CC BY 4.0)

In October 2026 the LoC search API (www.loc.gov ... `fo=json`) answered every request with a bot check, and
the old chroniclingamerica.loc.gov search returned 503. We did not try to get around the bot check. With Mike's
approval, the text search ran over **American Stories** instead:

- Dell, M., Carlson, J., Bryan, T., Silcock, E., Arora, A., Shen, Z., D'Amico-Wong, L., Le, Q., Querubin, P.,
  Heldring, L. *American Stories: A Large-Scale Structured Text Dataset of Historical U.S. Newspapers.* 2023.
  https://huggingface.co/datasets/dell-research-harvard/AmericanStories
- Licence: **CC BY 4.0** (attribution required; given here and in the /history/ page footers).
- It is article-level OCR of the same Chronicling America scans. We streamed only these years: **1839, 1869,
  1884, 1886, 1888, 1890, 1891, 1892, 1893, 1896, 1897, 1899, 1901, 1904, 1907, 1909, 1912, 1921 and 1925**. We kept matching articles in a local cache and never stored the full
  archives.

We use American Stories only to *find* pages. We don't republish its OCR text. What appears on the site:

- **Summaries:** 1 to 3 sentences, written by us in plain modern English after reading the article.
- **Quotes:** at most one short line per case (under 15 words) from the original page.

## How cases were chosen

- Keyword and context filters (`collector/historic.py scan`) flag candidate articles. Reprints of the same story
  are grouped by shared wording (`cluster`). We read each group by hand and kept the readable, on-topic ones.
- **Reprints:** a story that ran in many papers is **one case**, listing every paper we found that carried it.
  The first (earliest) printing we found is the main citation.
- **Hoaxes:** marked "probably a hoax or tall tale" when the paper itself treats it as a joke or hoax, or when
  later history says so (for example, the 1897 Aurora, Texas crash and the Leroy, Kansas "cow-napping" were
  admitted or shown to be inventions).
- **No claims:** nothing on these pages claims any creature or craft is real. They are what newspapers printed.

## Places

- Map pins mark where the event was said to happen, not where the paper was printed.
- Matched to **GeoNames** (cities1000 plus the full US gazetteer; CC BY 4.0) with the helpers in
  `collector/bluebook.py`.
- Lakes, bays and stretches of coast were placed by hand (`fixed: true`).
- Where only a county or state is known, the pin goes to the nearest named town or the state centre and is
  marked approximate (`approx: true`).

## Not used

No data from, or links to, BFRO, NUFORC, MUFON or any other sighting organisation or encounter map.

## New Zealand (added 2026-10-19)

- Papers Past, National Library of New Zealand: https://paperspast.natlib.govt.nz/ . Articles found through the DigitalNZ API (https://digitalnz.org/developers) and read in full. Each case links the original article; summaries are our own, hand-written in a small batch.
- Entries carry `"country": "NZ"` and `"state": "<region>, New Zealand"`; `page` is blank because Papers Past links go straight to the article. The Kermadec pin uses longitude 182.08 (not -177.92) so maps don't stretch across the date line.
