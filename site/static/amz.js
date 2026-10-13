// Amazon affiliate links: Canadian visitors go to amazon.ca with the Canadian tag. The HTML keeps the amazon.com
// link (one canonical link for search engines); the swap happens only at click time. Loaded on every page.
(() => {
  let ca = false;
  try {
    const tz = Intl.DateTimeFormat().resolvedOptions().timeZone || '';
    ca = /^America\/(Toronto|Montreal|Vancouver|Edmonton|Calgary|Winnipeg|Regina|Swift_Current|Halifax|Moncton|Glace_Bay|Goose_Bay|St_Johns|Whitehorse|Dawson|Dawson_Creek|Fort_Nelson|Creston|Yellowknife|Inuvik|Iqaluit|Rankin_Inlet|Cambridge_Bay|Resolute|Pangnirtung|Atikokan|Thunder_Bay|Nipigon|Rainy_River|Blanc-Sablon)$/.test(tz)
      || /-CA$/i.test(navigator.language || '');
  } catch (e) { /* no Intl: leave links alone */ }
  if (!ca) return;
  const swap = (e) => {
    const a = e.target.closest && e.target.closest('a[href*="amazon.com/"]');
    if (!a) return;
    const u = new URL(a.href);
    u.hostname = 'www.amazon.ca';
    if (u.searchParams.get('tag') === 'encountersatlas-20') u.searchParams.set('tag', 'encountersatlasca-20');
    if (u.searchParams.get('i') === 'instant-video') u.searchParams.delete('i'); // Prime Video isn't a department on amazon.ca
    a.href = u.toString();
  };
  document.addEventListener('click', swap, { capture: true });
  document.addEventListener('auxclick', swap, { capture: true }); // middle-click / open in new tab
})();
