"""Pinterest pin images (1000x1500) for the site's features and tools, same look as creature_pin.py.

usage: python3 tools/feature_pin.py [slug ...]
Writes site/static/pins/features/<slug>.jpg. FEATURES is also read by ~/Work/ea-promo (url, board) to pin them.
Numbers in the lines come from each page's own description; update them when the page changes.
"""
import os
import subprocess
import sys
import tempfile

from creature_pin import STATIC, card

OUT = os.path.join(STATIC, 'pins', 'features')
UFO, CRY, TRIP, NEWS = 'UFO Sightings & Files', 'Bigfoot & Cryptids', 'Monster Road Trips', 'Old Newspaper Monsters'
# slug, url, label, title, line, art (under static/), sky (a creature_og SKY key), board
FEATURES = [
    ('podcasts', '/podcasts/', 'PODCAST DIRECTORY', 'Bigfoot, UFO and Paranormal Podcasts',
     '250 shows, checked every week. Filter by topic and find episodes about any creature.', 'art/pic-recorder', 'fae', CRY),
    ('map', '/map/', 'THE MAP', 'Every Encounter on One Map',
     'Bigfoot, Dogman, UFO and cryptid reports, military cases and every Project Blue Book file.', 'art/pic-q-mountain', 'hominid', CRY),
    ('near-me', '/near-me/', 'NEAR ME', "What's Been Seen Near You?",
     'Reader reports, old newspaper stories and official UFO files around any town in the world.', 'art/pic-eyeshine', 'canid', CRY),
    ('report', '/report/', 'REPORT IT', 'Saw Something Strange?',
     'Tell us what happened. A person reads every report and your exact spot stays private.', 'art/pic-clipboard', 'other', CRY),
    ('road-trip', '/road-trip/', 'ROAD TRIP PLANNER', 'Plan a Monster Road Trip',
     'Every monster museum, famous sighting and mystery along your route, in the order you pass them.', 'art/pic-q-road', 'aquatic', TRIP),
    ('places', '/places/', 'PLACES TO VISIT', 'Monster Museums and Roadside Oddities',
     'Cryptid and UFO museums, festivals, roadside attractions and expeditions, mapped with prices.', 'art/pic-roadside', 'hominid', TRIP),
    ('events', '/events/', 'FESTIVALS', 'Bigfoot and UFO Festivals',
     'The Mothman Festival, Roswell, Rougarou Fest and more, month by month with dates.', 'art/pic-festival', 'fae', TRIP),
    ('expeditions', '/expeditions/', 'EXPEDITIONS', 'Bigfoot Expeditions and UFO Tours',
     'Guided Bigfoot trips, Loch Ness cruises, Sedona and Area 51 tours, with prices.', 'art/pic-expedition', 'aquatic', TRIP),
    ('on-this-day', '/on-this-day/', 'ON THIS DAY', 'Strange History, Every Day of the Year',
     'The UFO sightings, monster reports and mysteries that happened on each date.', 'art/pic-q-night', 'ufo', NEWS),
    ('history', '/history/', 'OLD NEWSPAPERS', 'Monsters in the Old Newspapers',
     '262 reports from 1839 to 1921: wild men, sea serpents, mystery airships and the Jersey Devil.', 'art/pic-newspaper', 'other', NEWS),
    ('stories', '/stories/', 'WITNESS STORIES', 'True Creature Encounters',
     'First-hand cryptid encounters, retold in full and credited to the people who lived them.', 'art/pic-q-woods', 'canid', CRY),
    ('encounters', '/encounters/', 'CLOSE ENCOUNTERS', 'Close Encounters with Beings',
     'Kelly-Hopkinsville, Flatwoods, Valensole, Pascagoula: what witnesses said and what investigators found.', 'art/flatwoods-monster', 'ufo', UFO),
    ('mysteries', '/mysteries/', 'MYSTERIES', 'Unexplained Mysteries, Every Theory Rated',
     'Tunguska, Dyatlov Pass, Oak Island, the Mary Celeste and more, on a map.', 'art/pic-q-unsure', 'entity', CRY),
    ('mystery-of-the-day', '/mystery-of-the-day/', 'MYSTERY OF THE DAY', 'A New Strange Case Every Day',
     'Read it, vote on what you think it was, and come back tomorrow for the verdict.', 'art/pic-q-sky', 'ufo', UFO),
    ('cards', '/cards/', 'COLLECTOR CARDS', 'Cryptid Cards You Collect in Real Life',
     '190 cards you can only get by visiting real sighting spots, with a shiny version of every one.', 'art/pic-footprint', 'hominid', CRY),
    ('what-did-i-see', '/tools/what-did-i-see/', 'WHAT DID I SEE?', 'What Did You See?',
     'Seven quick questions about a strange sighting, and what it sounds like, from cryptids to owls.', 'art/pic-e-starlink', 'canid', UFO),
    ('was-it-a-planet', '/tools/was-it-a-planet/', 'SKY CHECKER', 'Was It a Planet?',
     'Enter when, where and which way you looked to see what was really in the sky.', 'art/pic-e-planet', 'ufo', UFO),
    ('skywatch', '/tools/skywatch/', 'SKYWATCH', 'Is Tonight a Good Night to Skywatch?',
     'A score out of 10 for anywhere: clouds, the Moon, meteor showers and Space Station passes.', 'art/pic-telescope', 'ufo', UFO),
    ('size-comparison', '/tools/size-comparison/', 'SIZE COMPARISON', 'How Big Is Bigfoot, Really?',
     'Bigfoot, Dogman, Mothman and lake monsters next to a 6 ft person, in feet and metres.', 'art/pic-human', 'hominid', CRY),
    ('compare', '/compare/', 'SIDE BY SIDE', 'Which One Was It?',
     'Side-by-side guides to the cryptids and UFO types people mix up most.', 'art/pic-q-quad', 'other', CRY),
    ('guides', '/guides/', 'FIELD GUIDES', 'How to Look for Bigfoot and UFOs',
     'Field guides for Bigfoot research, skywatching, trail cameras, casting tracks and reporting.', 'art/pic-dg-torch', 'canid', CRY),
    ('gear', '/gear/', 'FIELD GEAR', 'Gear for Cryptid and UFO Hunting',
     'Trail cameras, thermal and night vision, audio recorders, casting kits and skywatching gear.', 'art/pic-trailcam', 'canid', CRY),
    ('journal', '/journal/', 'FIELD JOURNAL', 'Log Every Night Out',
     'Stakeouts, hikes and skywatching, even the empty nights. Weather and moon fill in for you.', 'art/pic-e-lantern', 'entity', CRY),
    ('books', '/books/', 'BOOKS', 'Books on Bigfoot, Lake Monsters and UFOs',
     'The best reads on cryptids, UFOs, aliens and fairies, plus a book of the week.', 'art/pic-folder', 'fae', CRY),
    ('canada', '/canada/', 'CANADA', "Canada's Cryptids and UFOs",
     'Sasquatch to Ogopogo, 17,170 mapped UFO reports by province, famous cases and places to visit.', 'art/ogopogo', 'aquatic', CRY),
    ('ufo-cases', '/ufo/cases/', 'FAMOUS UFO CASES', 'Famous UFO Cases Around the World',
     'From Nuremberg 1561 to Stephenville 2008: what witnesses saw and what investigators found.', 'art/ufo-saucer', 'ufo', UFO),
    ('blue-book', '/ufo/blue-book/', 'PROJECT BLUE BOOK', 'Every Project Blue Book File, Mapped',
     'All 10,622 US Air Force UFO case files from 1947 to 1969, by state and country.', 'art/pic-ufo-dataset', 'ufo', UFO),
    ('ufo-canada', '/ufo/canada/', 'CANADIAN UFO MAP', "Canada's UFO Sightings, Mapped",
     '17,170 sightings from 1989 to 2025 by province and town, with 1,699 unexplained cases.', 'art/pic-ufo-globe', 'ufo', UFO),
    ('military', '/military/', 'MILITARY ENCOUNTERS', 'Military UFO Encounters',
     'From WWII foo fighters to the Navy Tic Tac, with the official sources.', 'art/pic-mil-jet', 'ufo', UFO),
    ('hearings', '/ufo/hearings/', 'UFO HEARINGS', 'What Was Said Under Oath About UFOs',
     'Every public UFO hearing since 1966: who testified and key quotes from the transcripts.', 'art/pic-ufo-hearing', 'ufo', UFO),
    ('programs', '/ufo/programs/', 'GOVERNMENT PROGRAMMES', 'Every Government UFO Programme',
     '44 official programmes in 18 countries since 1946, from Blue Book to AARO, with what they found.', 'art/pic-ufo-report', 'ufo', UFO),
    ('releases', '/ufo/releases/', 'OFFICIAL FILES', 'Official UFO Files from 13 Countries',
     '51 government releases, from Project Blue Book to the 2026 Pentagon files, each linked to its source.', 'art/pic-ufo-film', 'ufo', UFO),
    ('people', '/ufo/people/', 'ON THE RECORD', 'Who Has Testified About UFOs',
     '25 pilots, whistleblowers, scientists and officials, with what each one said on the record.', 'art/pic-ufo-plane', 'ufo', UFO),
]


def main(argv):
    want = set(argv)
    os.makedirs(OUT, exist_ok=True)
    n = 0
    for slug, url, label, title, line, art, sky, board in FEATURES:
        if want and slug not in want:
            continue
        c = {'name': title, 'summary': line, 'cat': sky, 'art': art, 'label': label}
        with tempfile.TemporaryDirectory() as td:
            svg, png = os.path.join(td, 'c.svg'), os.path.join(td, 'c.png')
            open(svg, 'w').write(card(c))
            subprocess.run(['rsvg-convert', '-w', '1000', '-h', '1500', '-o', png, svg], check=True)
            subprocess.run(['magick', png, '-strip', '-quality', '82', os.path.join(OUT, slug + '.jpg')], check=True)
        n += 1
    print(f'{n} feature pins written to site/static/pins/features/')


if __name__ == '__main__':
    main(sys.argv[1:])
