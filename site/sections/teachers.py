"""For teachers (/teachers/) and the "Be the investigator" worksheet (/printables/judge-a-ufo-report/), 2026-10-25.

The worksheet is a free critical-thinking lesson built on four real Project Blue Book cases (case text condensed from
data/famous_cases.json and data/close_encounters.json, which carry the sources). Students weigh the evidence and give a
verdict; the last page is the answer key with what the Air Force decided. The same sheet is the free download on
Teachers Pay Teachers (PDF made from this page with tools/print_pdf.sh), which links back here.
"""
import re

CASES = [
    {'id': 'A', 'title': 'The pilot who chased a light', 'when': 'January 7, 1948', 'where': 'Fort Knox, Kentucky, USA', 'slug': '/ufo/cases/mantell-1948/',
     'text': 'Highway police called an Army airfield about a huge, round, shining object high in the sky. People in the control tower saw it too '
             'and could not say what it was. Four fighter planes went up to look. One pilot, Captain Thomas Mantell, kept climbing after it, '
             'higher than 22,000 feet, even though his plane had no oxygen for the pilot. His plane crashed and he was killed. Newspapers asked: '
             'what was he chasing?',
     'clues': ['Many people saw it from the ground, in daylight.', 'It stayed very high and seemed to move slowly.',
               'Something secret was being tested in the US at that time: giant research balloons that floated very high.'],
     'verdict': 'Explained (probably)', 'answer': 'Project Blue Book decided Captain Mantell was most likely chasing a Navy "Skyhook" balloon, a giant '
             'research balloon that was secret at the time. Sunlight shining on a balloon that high can make it glow like a metal object. '
             'His plane had no oxygen, so he blacked out as he climbed.',
     'lesson': 'Something can be real and still not be a spaceship. Secret projects make good UFOs.'},
    {'id': 'B', 'title': 'The monster on the hill', 'when': 'September 12, 1952', 'where': 'Flatwoods, West Virginia, USA', 'slug': '/encounters/flatwoods-1952/',
     'text': 'Some boys saw a bright light streak across the evening sky and come down on a hill. Seven people climbed up to look. Near the top they '
             'saw a pulsing red light. When a flashlight was pointed at it, they said they saw a figure about 10 feet tall with a glowing face '
             'inside a pointed hood. It hissed and moved toward them, and everyone ran. The sheriff searched that night and found nothing.',
     'clues': ['A bright meteor (a "shooting star") was seen across three states that same evening.', 'It was dark and the group was scared.',
               'Barn owls live in that area. They have round, pale faces, sit in trees, and hiss when they are frightened.'],
     'verdict': 'Explained (mostly)', 'answer': 'The Air Force record says the light in the sky was the meteor seen over Maryland, Pennsylvania and West '
             'Virginia that night. Later, an investigator suggested the "monster" was a barn owl on a branch, lit up by the flashlight, with '
             'leaves below it looking like a body. Not everyone agrees with the owl idea.',
     'lesson': 'Fear and darkness change what we see. One ordinary thing (a meteor) can start a much bigger story.'},
    {'id': 'C', 'title': 'Lights over the college town', 'when': 'August 25, 1951', 'where': 'Lubbock, Texas, USA', 'slug': '/ufo/cases/lubbock-lights-1951/',
     'text': 'Three science professors were sitting in a backyard at night when 20 to 30 soft, glowing lights flew over in a curved line, much faster '
             'than a plane. More groups passed by over the next few weeks. The professors tried to measure how high and fast they were. A student '
             'took photos of a V-shaped row of lights, and the pictures were printed in newspapers across the country.',
     'clues': ['The witnesses were scientists who were careful and honest.', 'The town had just put up new, very bright streetlights.',
               'Flocks of birds called plovers fly over Lubbock at night in late summer.'],
     'verdict': 'Not settled', 'answer': 'Project Blue Book officially left most of the Lubbock sightings as "unknown". The man in charge, Captain Edward '
             'Ruppelt, later wrote that he believed the lights were birds reflecting the new streetlights. People still argue about it, '
             'and some say the photos do not match birds.',
     'lesson': 'Smart, honest witnesses can still see something they cannot identify. "Unknown" does not mean "alien". It means "not enough proof either way".'},
    {'id': 'D', 'title': 'The police officer\'s landing', 'when': 'April 24, 1964', 'where': 'Socorro, New Mexico, USA', 'slug': '/encounters/socorro-zamora-1964/',
     'text': 'A police sergeant, Lonnie Zamora, was chasing a speeding car when he heard a roar and saw a flame in the sky. He drove to check and saw '
             'a shiny, egg-shaped object in a gully, with two small figures in white beside it. As he got closer it roared, shot out a blue and '
             'orange flame and flew away. Other officers came and found burned bushes and marks in the ground.',
     'clues': ['There was only one main witness, but he was a respected police officer.', 'There were real marks and burned plants.',
               'A missile test range was not far away. Some people think college students played a trick.'],
     'verdict': 'Unknown', 'answer': 'Project Blue Book could not identify it and listed it as "unknown". It is one of its most famous unsolved cases. '
             'People have suggested a secret test craft, a student hoax, and other ideas, but none has been proven.',
     'lesson': 'Some cases stay open. A good investigator is comfortable saying "we don\'t know yet".'},
]
QUESTIONS = ['Who saw it? How many people, and could they be mistaken?', 'What was the weather, the light, and the time of day?',
             'What ordinary things could look like this? (planes, balloons, stars, planets, birds, meteors, animals)',
             'Is there physical evidence: photos, marks, objects?', 'Did anything happen nearby at the same time that could explain it?']


def build(ctx):
    e, u = ctx.esc, ctx.url
    lines = lambda n: '<span class="pr-lines">' + '<i></i>' * n + '</span>'
    cards = ''.join(f'''<section class="jr-case">
  <h3><span class="jr-id">Case {c["id"]}</span> {e(c["title"])}</h3>
  <p class="jr-meta">{e(c["when"])} · {e(c["where"])}</p>
  <p>{e(c["text"])}</p>
  <p class="jr-clue-h"><b>Clues to think about</b></p><ul>{"".join(f"<li>{e(x)}</li>" for x in c["clues"])}</ul>
  <div class="jr-work"><p><b>Evidence that it was something ordinary:</b></p>{lines(2)}
  <p><b>Evidence that is hard to explain:</b></p>{lines(2)}
  <p class="jr-verdict"><b>Your verdict:</b> &#9744; Explained &nbsp; &#9744; Not enough information &nbsp; &#9744; Unknown</p>
  <p><b>Because:</b></p>{lines(1)}</div>
</section>''' for c in CASES)
    key = ''.join(f'''<div class="jr-ans"><h3>Case {c["id"]}: {e(c["title"])} <span class="jr-v">{e(c["verdict"])}</span></h3>
  <p>{e(c["answer"])}</p><p class="jr-lesson"><b>Big idea:</b> {e(c["lesson"])}</p>
  <p class="jr-more">Full case and sources: <a href="https://encounteratlas.com{e(c["slug"])}">encounteratlas.com{e(c["slug"])}</a></p></div>''' for c in CASES)
    body = f'''
<section class="band band-dark pr-head"><div class="wrap">
  <p class="crumb"><a href="{u('/teachers/')}">For teachers</a> / Printables</p>
  <h1>Be the investigator: judge a UFO report</h1>
  <p class="lede">A free printable lesson on weighing evidence, built on four real cases from the US Air Force's Project Blue Book. Students read each case, sort the clues and give a verdict. The last page is the answer key.</p>
  <p class="pr-actions"><button type="button" class="btn" onclick="window.print()">Print the worksheet</button>
  <a class="btn btn-ghost" href="{u('/static/printables/judge-a-ufo-report.pdf')}" download onclick="window.eaTrack&&eaTrack('worksheet_download',{{}})">Download the PDF</a></p>
</div></section>
<div class="band band-mist"><div class="wrap">
<!--sheet--><article class="pr-sheet jr">
  <header class="pr-title"><h2>Be the investigator: judge a UFO report</h2>
  <p>From 1952 to 1969 the US Air Force ran Project Blue Book to look into reports of strange things in the sky. Investigators asked the same
  questions every time. Use them on the four real cases below. There are no trick questions, and "we don't know" can be a good answer.</p></header>
  <div class="pr-check"><p><b>An investigator's questions</b></p><ol>{"".join(f"<li>{e(q)}</li>" for q in QUESTIONS)}</ol></div>
  <p class="jr-name">Name ____________________________ &nbsp; Class ____________ &nbsp; Date ____________</p>
  {cards}
  <section class="jr-wrap"><h3>Wrap-up</h3>
  <div class="pr-q"><p>1. Which case was the hardest to decide? Why?</p>{lines(2)}</div>
  <div class="pr-q"><p>2. Why might honest people see something that isn't what it looks like?</p>{lines(2)}</div>
  <div class="pr-q"><p>3. What would you need to call a case "solved"?</p>{lines(2)}</div></section>
  <section class="jr-key"><h2>Answer key: what the Air Force decided</h2>
  <p>Teachers: verdicts can differ from the Air Force's and still be good thinking. Give credit for clear reasons tied to the evidence.</p>
  {key}
  <div class="pr-send">
  <p><b>More cases, maps and real Air Force files</b> Free at encounteratlas.com: the full Project Blue Book list, every government UFO release, and the folklore behind 245 creatures. More classroom ideas at <a href="https://encounteratlas.com/teachers/">encounteratlas.com/teachers</a></p></div>
  </section>
</article><!--/sheet-->
</div></div>'''
    css = '''<style>
.jr-case { border: 1.5px solid #13261F; border-radius: 10px; padding: .6rem 1rem .8rem; margin: 1.1rem 0; }
.jr-case h3 { margin: .2rem 0; color: #13261F; } .jr-id { display: inline-block; background: #13261F; color: #F3F1E4; border-radius: 6px; padding: 0 .45rem; margin-right: .3rem; font-size: .85em; }
.jr-meta { margin: 0 0 .4rem; color: #555; font-size: .9rem; } .jr-case ul { margin: .2rem 0 .5rem; padding-left: 1.2rem; }
.jr-clue-h { margin: .4rem 0 0; } .jr-work p { margin: .5rem 0 0; } .jr-verdict { font-size: .95rem; }
.jr-name { margin: .8rem 0; } .jr-wrap h3, .jr-key h2 { color: #13261F; }
.jr-key { border-top: 3px dashed #9AA59E; margin-top: 1.6rem; padding-top: 1rem; }
.jr-ans { margin: .9rem 0; } .jr-ans h3 { margin: 0 0 .2rem; font-size: 1.05rem; color: #13261F; }
.jr-v { display: inline-block; background: #F2EEE2; border-radius: 999px; padding: 0 .6rem; font: 600 .8rem "Public Sans", sans-serif; margin-left: .3rem; vertical-align: middle; }
.jr-ans p { margin: .2rem 0; } .jr-lesson { color: #2D4A3E; } .jr-more { font-size: .82rem; color: #555; }
.pr-check ol { margin: 0; padding-left: 1.2rem; }
@media print {
  .jr-case { break-inside: avoid; padding: 4px 10px 6px; margin: 8px 0; font-size: 9.5pt; }
  .jr-case h3 { font-size: 12pt; } .jr-case ul { margin: 2px 0 4px; } .jr-work p { margin: 3px 0 0; }
  .jr-id { print-color-adjust: exact; -webkit-print-color-adjust: exact; }
  .jr-wrap { break-inside: avoid; } .jr-key { break-before: page; border-top: none; } .jr-v { print-color-adjust: exact; -webkit-print-color-adjust: exact; }
  .jr-ans { break-inside: avoid; font-size: 9.5pt; }
}
</style>'''
    head = f'<link rel="stylesheet" href="{u("/static/printables.css")}">' + css
    ctx.write('/printables/judge-a-ufo-report/', ctx.page('/printables/judge-a-ufo-report/', 'Be the investigator: a free UFO evidence worksheet', body,
              'A free printable critical-thinking lesson: students judge four real Project Blue Book UFO cases, weigh the clues and compare with the Air Force verdicts.',
              body_class='printables', head_extra=head))
    # Teachers Pay Teachers copy (2026-10-25): same sheet, but its links carry utm_source=tpt and the printed address is
    # encounteratlas.com/class (only in this copy), so visits from TPT downloads show up in GA4. Print it with
    # tools/print_pdf.sh /printables/judge-a-ufo-report/tpt/ <out.pdf> and upload that file to TPT.
    sheet = body[body.index('<!--sheet-->'):body.index('<!--/sheet-->')]
    tag = lambda m: m.group(1) + ('&' if '?' in m.group(2) else '?') + 'utm_source=tpt&utm_medium=worksheet&utm_campaign=judge-a-ufo-report"'
    tpt = re.sub(r'(href="https://encounteratlas\.com([^"]*))"', tag, sheet).replace('>encounteratlas.com/teachers<', '>encounteratlas.com/class<')
    ctx.write('/printables/judge-a-ufo-report/tpt/', ctx.page('/printables/judge-a-ufo-report/tpt/', 'Be the investigator: a free UFO evidence worksheet',
              f'<div class="band band-mist"><div class="wrap">{tpt}</div></div>', '', body_class='printables', head_extra=head,
              canonical=False, noindex=True))
    ctx.write('/class/', '<!doctype html><meta charset="utf-8"><meta name="robots" content="noindex"><title>For teachers</title>'
              '<link rel="canonical" href="https://encounteratlas.com/teachers/">'
              '<script>location.replace("/teachers/?utm_source=tpt&utm_medium=worksheet&utm_campaign=judge-a-ufo-report")</script>'
              '<meta http-equiv="refresh" content="0;url=/teachers/?utm_source=tpt&amp;utm_medium=worksheet&amp;utm_campaign=judge-a-ufo-report">'
              '<a href="/teachers/">Classroom ideas from Encounter Atlas</a>')

    tbody = f'''
<section class="band band-dark"><div class="wrap"><p class="crumb"><a href="{u('/about/')}">About</a> / For teachers</p>
<h1>For teachers: UFOs, cryptids and critical thinking</h1>
<p class="lede">Kids already love Bigfoot and flying saucers. That makes them a great way into evidence, sources and healthy doubt. Everything here is free, with no sign-up.</p></div></section>
<div class="band band-mist"><div class="wrap"><div class="prose">
<h2>Ready-to-print lessons</h2>
<ul>
<li><a href="{u('/printables/judge-a-ufo-report/')}"><b>Be the investigator: judge a UFO report</b></a>. Four real Air Force cases, a clue sheet and an answer key. Works well for grades 4 to 8 (ages 9 to 14), in one 45 to 60 minute lesson. <a href="{u('/static/printables/judge-a-ufo-report.pdf')}" download onclick="window.eaTrack&&eaTrack('worksheet_download',{{}})">PDF</a></li>
<li><a href="{u('/printables/after-an-encounter/')}">Encounter record sheet</a>. The form we give witnesses. Good for a lesson on observation and writing things down before memory changes.</li>
</ul>
<h2>Ideas by subject</h2>
<ul>
<li><b>Reading and media literacy:</b> compare an old newspaper story with what investigators found. Our <a href="{u('/history/')}">old newspaper stories</a> come from real 1800s and 1900s papers, many of them tall tales.</li>
<li><b>Math and data:</b> download the <a href="{u('/datasets/')}">Project Blue Book data</a> (a free spreadsheet of 10,622 Air Force files) and graph reports by year or state. Why did reports jump in 1952 and 1966?</li>
<li><b>Science:</b> try <a href="{u('/tools/was-it-a-planet/')}">Was it a planet?</a> and <a href="{u('/tools/skywatch/')}">Tonight's skywatch</a>, then go outside and find Venus, the most common "UFO" of all.</li>
<li><b>Social studies and culture:</b> every <a href="{u('/creatures/')}">creature page</a> covers where the legend comes from. Many creatures come from Indigenous traditions, and those pages explain them with respect, as living culture, not monsters.</li>
<li><b>Geography:</b> the <a href="{u('/map/')}">world map</a> and the <a href="{u('/us/')}">state and province pages</a> show which legends belong where.</li>
</ul>
<h2>A note on the content</h2>
<p>We don't claim sightings are real and we don't claim they aren't. Reader reports are moderated, but some describe frightening experiences, so preview pages before sharing them with younger students. The creature pages, official files and printables are written to be classroom-safe.</p>
<p>Made something with these, or want a worksheet on a topic we don't cover? <a href="{u('/contact/?about=teachers')}">Tell us</a>.</p>
</div></div></div>'''
    ctx.write('/teachers/', ctx.page('/teachers/', 'For teachers: UFO and cryptid lessons on critical thinking', tbody,
              'Free printable lessons and classroom ideas that use real UFO files and cryptid legends to teach evidence, sources and critical thinking.'))
