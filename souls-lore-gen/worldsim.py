"""Seeded procedural history simulator (the "Dwarf Fortress" layer).

Generates a complete, internally consistent world chronicle: a cosmology,
gods, kingdoms, knightly orders, churches and cults, named figures, wars,
betrayals, ascensions, a spreading curse, and artifacts with provenance
chains. One central mystery is chosen and kept hidden; items may only ever
hint at it.

Everything is driven by a single random.Random(seed), so a given seed
reproduces the same world exactly.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field, asdict

# ---------------------------------------------------------------------------
# Name generation
# ---------------------------------------------------------------------------

ONSETS = [
    "Vel", "Mor", "Aldr", "Ser", "Ish", "Cal", "Yor", "Har", "Ath", "El",
    "Ny", "Ver", "Sol", "Thal", "Ran", "Quel", "Ban", "Fen", "Gal", "Ir",
    "Kar", "Nim", "Ost", "Ruth", "Syl", "Tor", "Ul", "Wren", "Ys", "Om",
    "Bel", "Cyr", "Dra", "Ez", "Ghal", "Hest", "Ka", "Lo", "Maz", "Ol",
]
MIDS = ["a", "e", "i", "o", "u", "ae", "ia", "or", "an", "en", "ir", "ul", "ess"]
ENDS = [
    "ric", "mund", "wyn", "dra", "lis", "veth", "gar", "moth", "sila", "dane",
    "rion", "thas", "mere", "grim", "cael", "noth", "vane", "dis", "hild", "os",
    "eth", "ara", "orn", "ien", "ula", "ach", "emis", "ott", "yne", "ast",
]

PLACE_SUFFIXES = [
    "hold", "spire", "deep", "reach", "fen", "gate", "barrow", "vault",
    "march", "hollow", "crown", "mere", "cradle", "shroud",
]


class Namer:
    """Deterministic name factory that never repeats a name within a world."""

    def __init__(self, rng: random.Random):
        self.rng = rng
        self.used: set[str] = set()

    def _raw(self) -> str:
        parts = [self.rng.choice(ONSETS)]
        if self.rng.random() < 0.55:
            parts.append(self.rng.choice(MIDS))
        parts.append(self.rng.choice(ENDS))
        return "".join(parts).capitalize()

    def person(self) -> str:
        while True:
            n = self._raw()
            if n not in self.used:
                self.used.add(n)
                return n

    def place(self) -> str:
        while True:
            n = self._raw() + self.rng.choice(PLACE_SUFFIXES)
            if n not in self.used:
                self.used.add(n)
                return n


# ---------------------------------------------------------------------------
# Cosmology archetypes
# ---------------------------------------------------------------------------
# Each archetype defines the primordial power, what it gave the world, how its
# waning manifests as a curse, and a menu of possible central mysteries.

ARCHETYPES = {
    "flame": {
        "primordial": "the First Ember",
        "gift": "warmth, disparity, and the colour of souls",
        "waning": "the Ember gutters; shadows lengthen and the dead forget to lie down",
        "curse_name": "the Gutter-mark",
        "curse_desc": "a grey brand that spreads over the heart; the marked wander until their names burn out",
        "adversary_title": "the Cinder-Eater",
        "relic_nouns": ["ember", "cinder", "brand", "pyre", "ash"],
        "mysteries": [
            "The Ember is not dying — the gods siphon it to prolong their reign, and the curse is the siphon's residue.",
            "The Ember was stolen, not given; its true keeper still waits below the world, and every rekindling deepens the debt.",
            "The first soul ever kindled was unwilling, and the Ember remembers; the curse is its slow act of accounting.",
        ],
    },
    "sea": {
        "primordial": "the Drowned Radiance",
        "gift": "memory, tide, and the salt that keeps names from dissolving",
        "waning": "the tide recedes from the world's edges; memories thin and the drowned begin to speak",
        "curse_name": "the Brine-hollowing",
        "curse_desc": "salt blooms beneath the skin; the afflicted forget faces first, then their own",
        "adversary_title": "the Still Water",
        "relic_nouns": ["pearl", "brine", "tide", "conch", "salt"],
        "mysteries": [
            "The Radiance never drowned — it was drowned, by the very gods who now pray for its return.",
            "The sea is one vast sleeper, and the gift of memory is only what leaks from its dream; waking it would end all names at once.",
            "Every prayer said over water is swallowed and hoarded; the Radiance answers none, because it is saving them for a single terrible reply.",
        ],
    },
    "root": {
        "primordial": "the Pale Root",
        "gift": "order, season, and the slow sap that binds moments in sequence",
        "waning": "the Root greys and splits; hours repeat, orchards fruit with last year's fruit",
        "curse_name": "the Ringing-rot",
        "curse_desc": "growth rings surface on the flesh of the afflicted, one for each hour they relive",
        "adversary_title": "the Ungrown",
        "relic_nouns": ["seed", "sap", "ring", "graft", "bough"],
        "mysteries": [
            "The Root grew from a buried corpse, and the order it grants is that corpse's refusal to be forgotten.",
            "The seasons were a cage built to hold something seasonless; the rot is the cage rusting.",
            "Whoever prunes the Root decides what may happen next; the gods' war was never for the Root but for the shears.",
        ],
    },
    "moon": {
        "primordial": "the Sundered Moon",
        "gift": "longing, tide of the blood, and light gentle enough to lie by",
        "waning": "the shards drift apart; nights arrive unscheduled and grief acquires weight",
        "curse_name": "the Silver Lament",
        "curse_desc": "moonlight pools in the eyes of the afflicted, who weep light until none is left to see by",
        "adversary_title": "the Unreflected",
        "relic_nouns": ["shard", "silver", "veil", "mirror", "lament"],
        "mysteries": [
            "The Moon was not sundered by war — it broke itself to escape what it saw approaching, and the shards are still fleeing.",
            "Each god keeps a shard and calls it holy; assembled, the shards spell out a name no god survives hearing.",
            "The gentle light was never the Moon's — it is borrowed, and the lender has begun to collect.",
        ],
    },
    "song": {
        "primordial": "the Founding Chord",
        "gift": "speech, covenant, and the resonance that holds stone to stone",
        "waning": "the Chord decays into echoes; oaths slip, bridges forget their arches",
        "curse_name": "the Unsinging",
        "curse_desc": "the voices of the afflicted fade to a hum, and what they built beside begins to loosen",
        "adversary_title": "the Discordant",
        "relic_nouns": ["chord", "bell", "hymn", "echo", "tongue"],
        "mysteries": [
            "The Chord is not fading — it is being sung backwards, deliberately, from somewhere beneath the oldest bell.",
            "Speech was the Chord's prison, not its gift; every word spent brings its silence, and its freedom, closer.",
            "The gods harmonised over a note that was already there; the world's true key belongs to the thing that hummed first.",
        ],
    },
}

GOD_DOMAINS = [
    "war and the keeping of thresholds",
    "graves and the ledger of names",
    "harvest, plenty, and the debt of plenty",
    "craft, measure, and the forge",
    "storms and unkept promises",
    "healing and the price of healing",
    "secrets, locks, and the spaces between",
    "the hunt and the mercy of endings",
    "law, chains, and the first covenant",
    "dream, omen, and the unlit hour",
]

FIGURE_ROLES_A2 = [
    "knight", "high priest", "heretic scholar", "king", "queen",
    "executioner", "court sorcerer", "gravewarden", "pilgrim saint",
    "oathbreaker general", "physician", "bell-keeper",
]

ITEM_TYPES = [
    "weapon", "armor", "ring", "talisman", "soul remnant",
    "key item", "consumable", "catalyst",
]


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class Figure:
    id: str
    name: str
    epithet: str
    role: str
    faction_id: str | None
    is_god: bool = False
    fate: str | None = None       # how their story ended, if it has
    fate_year: int | None = None


@dataclass
class Faction:
    id: str
    name: str
    kind: str                     # kingdom | order | church | cult
    seat: str
    founded_year: int
    founder_id: str | None
    fallen_year: int | None = None


@dataclass
class Event:
    id: str
    year: int
    kind: str
    text: str                     # what truly happened
    hidden: str | None = None     # a secret aspect known to almost no one
    participants: list[str] = field(default_factory=list)


@dataclass
class Artifact:
    id: str
    name: str
    item_type: str
    created_year: int
    origin_faction_id: str | None
    provenance: list[str]                 # event ids, in order
    knowledge: list[str]                  # true facts this item "knows"
    bias: str                             # perspective colouring the description
    false_rumor: str | None = None        # one deliberately wrong belief
    hints_mystery: bool = False           # may allude (only allude) to the mystery


@dataclass
class Age:
    name: str
    start: int
    end: int | None
    blurb: str


@dataclass
class World:
    seed: int
    archetype_key: str
    archetype: dict
    primordial_name: str
    mystery: str
    ages: list[Age] = field(default_factory=list)
    figures: list[Figure] = field(default_factory=list)
    factions: list[Faction] = field(default_factory=list)
    events: list[Event] = field(default_factory=list)
    artifacts: list[Artifact] = field(default_factory=list)

    # -- helpers -----------------------------------------------------------
    def fig(self, fid: str) -> Figure:
        return next(f for f in self.figures if f.id == fid)

    def fac(self, fid: str) -> Faction:
        return next(f for f in self.factions if f.id == fid)

    def ev(self, eid: str) -> Event:
        return next(e for e in self.events if e.id == eid)

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------

class _Gen:
    def __init__(self, seed: int, n_items: int):
        self.rng = random.Random(seed)
        self.namer = Namer(self.rng)
        self.n_items = max(6, n_items)
        self._ids: dict[str, int] = {}

        key = self.rng.choice(sorted(ARCHETYPES))
        arch = ARCHETYPES[key]
        self.world = World(
            seed=seed,
            archetype_key=key,
            archetype=arch,
            primordial_name=arch["primordial"],
            mystery=self.rng.choice(arch["mysteries"]),
        )
        self.year = 0

    # -- plumbing ----------------------------------------------------------
    def _id(self, prefix: str) -> str:
        self._ids[prefix] = self._ids.get(prefix, 0) + 1
        return f"{prefix}{self._ids[prefix]}"

    def event(self, kind: str, text: str, hidden: str | None = None,
              participants: list[str] | None = None) -> Event:
        e = Event(self._id("e"), self.year, kind, text, hidden, participants or [])
        self.world.events.append(e)
        return e

    def advance(self, lo: int, hi: int):
        self.year += self.rng.randint(lo, hi)

    # -- age 1: the gift ----------------------------------------------------
    def age_of_gift(self):
        w, rng = self.world, self.rng
        arch = w.archetype

        w.ages.append(Age(
            name="the Age of the Gift", start=0, end=None,
            blurb=f"{w.primordial_name} gave the world {arch['gift']}.",
        ))
        self.event("cosmogony",
                   f"{w.primordial_name} rose (or was raised — the tellings differ) and gave the world {arch['gift']}.")

        # Gods claim portions of the gift.
        n_gods = rng.randint(3, 4)
        domains = rng.sample(GOD_DOMAINS, n_gods)
        for dom in domains:
            g = Figure(self._id("f"), self.namer.person(),
                       f"god of {dom}", "god", None, is_god=True)
            w.figures.append(g)
            self.advance(3, 20)
            self.event("claiming",
                       f"{g.name}, {g.epithet}, claimed a portion of the gift and took a throne.",
                       participants=[g.id])

        # Each god founds a kingdom (or church) and forges regalia.
        for g in [f for f in w.figures if f.is_god]:
            self.advance(10, 40)
            kind = "kingdom" if rng.random() < 0.7 else "church"
            fac = Faction(self._id("k"), self.namer.place(), kind,
                          seat=self.namer.place(), founded_year=self.year,
                          founder_id=g.id)
            w.factions.append(fac)
            g.faction_id = fac.id
            self.event("founding",
                       f"{g.name} founded {fac.name} ({fac.kind}) at {fac.seat}.",
                       participants=[g.id])

            noun = rng.choice(arch["relic_nouns"])
            item_type = rng.choice(["weapon", "talisman", "catalyst", "ring"])
            art = Artifact(self._id("a"),
                           name=f"{noun.capitalize()} of {g.name}",
                           item_type=item_type,
                           created_year=self.year,
                           origin_faction_id=fac.id,
                           provenance=[], knowledge=[], bias="")
            w.artifacts.append(art)
            e = self.event("forging",
                           f"The {art.name} was wrought as regalia of {g.name}'s throne.",
                           participants=[g.id])
            art.provenance.append(e.id)

        # The war against the adversary.
        adversary = Figure(self._id("f"), self.namer.person(),
                           arch["adversary_title"], "adversary", None, is_god=True)
        w.figures.append(adversary)
        self.advance(30, 80)
        gods = [f for f in w.figures if f.is_god and f.role == "god"]
        champion = rng.choice(gods)
        secret_traitor = rng.choice([g for g in gods if g is not champion])
        war = self.event(
            "great war",
            f"{adversary.name}, {adversary.epithet}, rose against the thrones. "
            f"{champion.name} led the gods to war.",
            hidden=(f"{secret_traitor.name} treated with {adversary.name} in secret "
                    f"and was spared what followed."),
            participants=[adversary.id, champion.id, secret_traitor.id])

        self.advance(5, 15)
        sealed_at = self.namer.place()
        seal = self.event(
            "sealing",
            f"{adversary.name} was defeated and sealed beneath {sealed_at}; "
            f"the seal was bought with the lives of {rng.randint(3, 9)} champions.",
            participants=[adversary.id, champion.id])
        adversary.fate = f"sealed beneath {sealed_at}"
        adversary.fate_year = self.year

        # The champion's weapon becomes an artifact of the war.
        noun = rng.choice(arch["relic_nouns"])
        art = Artifact(self._id("a"),
                       name=f"{champion.name}'s War-{noun.capitalize()}",
                       item_type="weapon", created_year=self.year,
                       origin_faction_id=champion.faction_id,
                       provenance=[war.id, seal.id], knowledge=[], bias="")
        w.artifacts.append(art)

    # -- age 2: names and kings ---------------------------------------------
    def age_of_names(self):
        w, rng = self.world, self.rng
        arch = w.archetype

        self.advance(60, 150)
        w.ages[-1].end = self.year
        w.ages.append(Age(
            name="the Age of Names", start=self.year, end=None,
            blurb=("The gods withdrew to their high seats and mortals learned "
                   "to matter. Then the waning began: " + arch["waning"] + "."),
        ))
        self.event("waning",
                   f"The waning began: {arch['waning']}. "
                   f"Mortals called the affliction {arch['curse_name']}: {arch['curse_desc']}.")

        # Mortal factions: an order, a church, a cult.
        gods = [f for f in w.figures if f.is_god and f.role == "god"]
        mortals: list[Figure] = []

        def new_mortal(role: str, fac_id: str | None) -> Figure:
            f = Figure(self._id("f"), self.namer.person(),
                       rng.choice([
                           "the Unbowed", "the Twice-crowned", "the Grey",
                           "the Lantern-eyed", "of the Long Vigil", "the Kindly",
                           "the Forsworn", "Half-remembered", "the Adamant",
                           "of the Last Door", "the Saltborn", "the Quiet",
                       ]),
                       role, fac_id)
            w.figures.append(f)
            mortals.append(f)
            return f

        self.advance(10, 30)
        order_founder = new_mortal("knight", None)
        order = Faction(self._id("k"), f"Order of the {rng.choice(arch['relic_nouns']).capitalize()}",
                        "order", seat=self.namer.place(),
                        founded_year=self.year, founder_id=order_founder.id)
        w.factions.append(order)
        order_founder.faction_id = order.id
        self.event("founding",
                   f"{order_founder.name} {order_founder.epithet} founded the {order.name} "
                   f"at {order.seat}, sworn to stand against {arch['curse_name']}.",
                   participants=[order_founder.id])

        self.advance(5, 25)
        patron = rng.choice(gods)
        church = Faction(self._id("k"), f"Church of {patron.name}",
                         "church", seat=self.namer.place(),
                         founded_year=self.year, founder_id=None)
        w.factions.append(church)
        priest = new_mortal("high priest", church.id)
        self.event("founding",
                   f"The {church.name} was raised at {church.seat}; "
                   f"{priest.name} {priest.epithet} took its first pulpit, preaching that "
                   f"the waning is a trial and the faithful will be spared.",
                   participants=[priest.id, patron.id])

        self.advance(5, 25)
        heretic = new_mortal("heretic scholar", None)
        cult = Faction(self._id("k"), f"Cult of the {rng.choice(['Open Door', 'Second Dawn', 'Patient Below', 'True ' + arch['relic_nouns'][0].capitalize()])}",
                       "cult", seat=self.namer.place(),
                       founded_year=self.year, founder_id=heretic.id)
        w.factions.append(cult)
        heretic.faction_id = cult.id
        self.event("heresy",
                   f"{heretic.name} {heretic.epithet} was cast out of {church.name} "
                   f"and founded the {cult.name}, teaching that the gods themselves "
                   f"caused the waning.",
                   # The heretic is closer to the truth than the church — a
                   # classic Souls move — but not exactly right.
                   hidden="The heresy is nearer the truth than the sermon.",
                   participants=[heretic.id])

        # A mortal kingdom rises.
        self.advance(10, 30)
        monarch = new_mortal(rng.choice(["king", "queen"]), None)
        realm = Faction(self._id("k"), self.namer.place(), "kingdom",
                        seat=self.namer.place(), founded_year=self.year,
                        founder_id=monarch.id)
        w.factions.append(realm)
        monarch.faction_id = realm.id
        self.event("founding",
                   f"{monarch.name} {monarch.epithet} united the river-clans and was "
                   f"crowned in {realm.seat}; the realm took the name {realm.name}.",
                   participants=[monarch.id])

        # The great attempt: a ritual to restore the gift.
        self.advance(15, 45)
        ritualist = rng.choice([priest, heretic])
        vessel = new_mortal("pilgrim saint", ritualist.faction_id)
        rite = self.event(
            "rite of restoration",
            f"At the urging of {ritualist.name}, the saint {vessel.name} {vessel.epithet} "
            f"was given to {w.primordial_name} in the rite of restoration. "
            f"For a generation, the waning slowed.",
            hidden=(f"The rite did not restore anything. It only fed the waning more "
                    f"slowly — and {ritualist.name} suspected as much."),
            participants=[ritualist.id, vessel.id])
        vessel.fate = "given to the rite of restoration"
        vessel.fate_year = self.year

        # The saint's remains become relics.
        for noun, itype in [(rng.choice(arch["relic_nouns"]), "talisman"),
                            ("soul", "soul remnant")]:
            name = (f"{noun.capitalize()} of Saint {vessel.name}" if itype == "talisman"
                    else f"Remnant Soul of Saint {vessel.name}")
            art = Artifact(self._id("a"), name, itype, self.year,
                           origin_faction_id=ritualist.faction_id,
                           provenance=[rite.id], knowledge=[], bias="")
            w.artifacts.append(art)

        # War between realm and order/church, seeded by a betrayal.
        self.advance(20, 50)
        traitor = new_mortal("oathbreaker general", realm.id)
        betrayal = self.event(
            "betrayal",
            f"{traitor.name} {traitor.epithet}, sword-hand of {monarch.name}, opened the "
            f"gates of {realm.seat} to the {order.name} over a grievance no chronicle "
            f"agrees on.",
            hidden=(f"{traitor.name} acted on a promise from the {cult.name}: that the "
                    f"marked of their house would be spared {arch['curse_name']}. "
                    f"The promise was not kept."),
            participants=[traitor.id, monarch.id])

        self.advance(1, 4)
        fall = self.event(
            "fall of a kingdom",
            f"{realm.name} fell. {monarch.name} {monarch.epithet} died at the foot of "
            f"their own throne; the crown was carried away and never worn again.",
            participants=[monarch.id, traitor.id])
        monarch.fate = "slain at their own throne"
        monarch.fate_year = self.year
        realm.fallen_year = self.year

        # Artifacts of the fall.
        crown = Artifact(self._id("a"), f"Hollow Crown of {realm.name}",
                         "key item", self.year, origin_faction_id=realm.id,
                         provenance=[betrayal.id, fall.id], knowledge=[], bias="")
        w.artifacts.append(crown)
        blade = Artifact(self._id("a"), f"{traitor.name}'s Oathbreaker Blade",
                         "weapon", self.year, origin_faction_id=realm.id,
                         provenance=[betrayal.id, fall.id], knowledge=[], bias="")
        w.artifacts.append(blade)

        # The traitor's own end.
        self.advance(2, 10)
        self.event("fate",
                   f"{traitor.name} was found at {rng.choice([order.seat, cult.seat])} "
                   f"bearing {arch['curse_name']}, and was not spared.",
                   participants=[traitor.id])
        traitor.fate = f"succumbed to {arch['curse_name']}"
        traitor.fate_year = self.year

        self._age2_people = dict(order=order, church=church, cult=cult,
                                 heretic=heretic, priest=priest,
                                 order_founder=order_founder)

    # -- age 3: dusk ---------------------------------------------------------
    def age_of_dusk(self):
        w, rng = self.world, self.rng
        arch = w.archetype
        p = self._age2_people

        self.advance(40, 120)
        w.ages[-1].end = self.year
        w.ages.append(Age(
            name="the Age of Dusk", start=self.year, end=None,
            blurb=("The present age. The gods are silent, the roads belong to the "
                   "marked, and pilgrims walk toward rumours of a cure."),
        ))

        # A god falls or departs — the pivot into dusk.
        gods = [f for f in w.figures if f.is_god and f.role == "god" and not f.fate]
        fallen_god = rng.choice(gods)
        mode = rng.choice(["went below", "was unmade", "hollowed"])
        if mode == "went below":
            text = (f"{fallen_god.name}, {fallen_god.epithet}, descended below the world "
                    f"to look upon {w.primordial_name} directly, and did not return.")
            hidden = f"{fallen_god.name} found the truth of the waning, and chose to stay."
            fallen_god.fate = "descended below the world; did not return"
        elif mode == "was unmade":
            text = (f"{fallen_god.name}, {fallen_god.epithet}, was unmade upon their own "
                    f"throne. No wound was found, and no successor dared the seat.")
            hidden = ("What unmade the god was not violence but understanding — "
                      "a truth arrived at, all at once.")
            fallen_god.fate = "unmade upon their throne"
        else:
            text = (f"{fallen_god.name}, {fallen_god.epithet}, took {arch['curse_name']} — "
                    f"the first of the gods to bear it — and wandered from their seat.")
            hidden = "The curse does not distinguish gods from mortals. It never did."
            fallen_god.fate = f"took {arch['curse_name']} and wandered"
        fallen_god.fate_year = self.year
        pivot = self.event("twilight of a god", text, hidden=hidden,
                           participants=[fallen_god.id])

        # The fallen god's soul remnant.
        w.artifacts.append(Artifact(
            self._id("a"), f"Soul of {fallen_god.name}", "soul remnant",
            self.year, origin_faction_id=fallen_god.faction_id,
            provenance=[pivot.id], knowledge=[], bias=""))

        # A last hero sets out; their story is the age's open question.
        self.advance(10, 40)
        hero = Figure(self._id("f"), self.namer.person(),
                      rng.choice(["the Latecomer", "the Ashen", "of the Empty Scabbard",
                                  "the Unmarked", "Last-sworn"]),
                      "wandering knight", p["order"].id)
        w.figures.append(hero)
        quest = self.event(
            "last pilgrimage",
            f"{hero.name} {hero.epithet}, last-sworn of the {p['order'].name}, set out "
            f"for the place where {fallen_god.name} was lost, carrying the order's "
            f"final blessing.",
            participants=[hero.id, fallen_god.id])
        self.advance(3, 12)
        outcome = rng.choice([
            (f"{hero.name} was last seen at the edge of the deep roads. The order "
             f"keeps a vigil that has not ended.", "vanished on the deep roads"),
            (f"{hero.name} returned once, said nothing, left their sword upon the "
             f"order's altar, and walked into the dusk unarmed.", "walked into the dusk unarmed"),
            (f"Word came that {hero.name} fell to the marked, and then word came that "
             f"{hero.name} led the marked. The order believes neither.", "fate contested"),
        ])
        end_ev = self.event("hero's end", outcome[0], participants=[hero.id])
        hero.fate = outcome[1]
        hero.fate_year = self.year

        # Hero's gear becomes items.
        for itype, nm in [("armor", f"{hero.name}'s Set"),
                          ("ring", f"Ring of the {p['order'].name.split(' of the ')[-1]} Vigil")]:
            w.artifacts.append(Artifact(
                self._id("a"), nm, itype, self.year,
                origin_faction_id=p["order"].id,
                provenance=[quest.id, end_ev.id], knowledge=[], bias=""))

        # The cult stirs at the seal.
        adversary = next(f for f in w.figures if f.role == "adversary")
        self.advance(5, 30)
        stir = self.event(
            "the seal weakens",
            f"Pilgrims of the {p['cult'].name} were found digging at the seal of "
            f"{adversary.name}. The wardens hanged nine; the digging continued.",
            hidden=(f"The seal has been failing on its own since the waning began. "
                    f"The cult only follows the cracks."),
            participants=[adversary.id])

        # A humble consumable rounds out the set.
        w.artifacts.append(Artifact(
            self._id("a"),
            f"Warding {rng.choice(arch['relic_nouns']).capitalize()}",
            "consumable", self.year, origin_faction_id=p["church"].id,
            provenance=[stir.id], knowledge=[], bias=""))

    # -- knowledge assignment -------------------------------------------------
    def assign_knowledge(self):
        """Give each artifact its fragmentary, biased view of the true history."""
        w, rng = self.world, self.rng
        arch = w.archetype

        bias_by_kind = {
            "kingdom": "courtly and proud; flatters its founders, omits their crimes",
            "church": "liturgical; frames all loss as trial and all doubt as sin",
            "order": "austere and dutiful; honours oaths, distrusts miracles",
            "cult": "conspiratorial; blames the gods, half-right and overreaching",
            None: "a peddler's patter; wonder-struck, unreliable on names and dates",
        }

        false_rumors = [
            "names the wrong slayer for a famous death",
            "claims the relic was a gift when it was plunder",
            "places the event a whole age too early",
            "attributes the deed to a god who had no part in it",
            "insists the dead figure still lives, in hiding",
        ]

        # Trim or pad the artifact list to n_items, keeping type variety.
        arts = w.artifacts
        rng.shuffle(arts)
        arts.sort(key=lambda a: (a.item_type, a.created_year))
        if len(arts) > self.n_items:
            # Keep at least one of each type where possible.
            keep: list[Artifact] = []
            seen_types: set[str] = set()
            for a in arts:
                if a.item_type not in seen_types:
                    keep.append(a)
                    seen_types.add(a.item_type)
            rest = [a for a in arts if a not in keep]
            rng.shuffle(rest)
            keep.extend(rest[: self.n_items - len(keep)])
            w.artifacts = sorted(keep, key=lambda a: a.created_year)
        else:
            w.artifacts = sorted(arts, key=lambda a: a.created_year)

        # Decide which items may hint at the mystery (2-3 of them).
        hinters = rng.sample(w.artifacts, k=min(3, max(2, len(w.artifacts) // 5)))
        for a in hinters:
            a.hints_mystery = True

        for a in w.artifacts:
            fac = w.fac(a.origin_faction_id) if a.origin_faction_id else None
            a.bias = bias_by_kind[fac.kind if fac else None]

            facts: list[str] = []
            for eid in a.provenance:
                e = w.ev(eid)
                facts.append(f"(year {e.year}) {e.text}")
                # Provenance sometimes carries a whisper of the hidden layer.
                if e.hidden and rng.random() < 0.5:
                    facts.append(f"[half-known secret] {e.hidden}")
            # A fact about a participant's fate, for texture.
            part_ids = [pid for eid in a.provenance for pid in w.ev(eid).participants]
            fated = [w.fig(pid) for pid in part_ids if w.fig(pid).fate]
            if fated:
                f0 = rng.choice(fated)
                facts.append(f"{f0.name}, {f0.epithet}: fate — {f0.fate} (year {f0.fate_year}).")
            if fac:
                facts.append(f"This item is kept/told of by {fac.name} ({fac.kind}), seat at {fac.seat}.")
            facts.append(f"The affliction of this world: {arch['curse_name']} — {arch['curse_desc']}.")

            a.knowledge = facts
            if rng.random() < 0.35:
                a.false_rumor = rng.choice(false_rumors)

    # -- entry point -----------------------------------------------------------
    def run(self) -> World:
        self.age_of_gift()
        self.age_of_names()
        self.age_of_dusk()
        self.assign_knowledge()
        return self.world


def generate_world(seed: int, n_items: int = 14) -> World:
    return _Gen(seed, n_items).run()


# ---------------------------------------------------------------------------
# Chronicle rendering (the ground-truth document)
# ---------------------------------------------------------------------------

def render_chronicle(w: World) -> str:
    lines: list[str] = []
    lines.append(f"# The True Chronicle (seed {w.seed})")
    lines.append("")
    lines.append("> **Spoilers.** This is the ground truth the items only hint at.")
    lines.append("")
    lines.append(f"**Cosmology:** {w.primordial_name} — gift of {w.archetype['gift']}.")
    lines.append(f"**The waning:** {w.archetype['waning']}.")
    lines.append(f"**The curse:** {w.archetype['curse_name']} — {w.archetype['curse_desc']}.")
    lines.append("")
    lines.append(f"**THE CENTRAL MYSTERY (never stated by any item):** {w.mystery}")
    lines.append("")

    lines.append("## Ages")
    for a in w.ages:
        end = a.end if a.end is not None else "present"
        lines.append(f"- **{a.name}** (years {a.start}–{end}): {a.blurb}")
    lines.append("")

    lines.append("## Timeline")
    for e in w.events:
        lines.append(f"- **Year {e.year}** — *{e.kind}*: {e.text}")
        if e.hidden:
            lines.append(f"  - _Hidden:_ {e.hidden}")
    lines.append("")

    lines.append("## Dramatis Personae")
    for f in w.figures:
        fac = f" — of {w.fac(f.faction_id).name}" if f.faction_id else ""
        fate = f" Fate: {f.fate} (year {f.fate_year})." if f.fate else ""
        god = " [god]" if f.is_god else ""
        lines.append(f"- **{f.name}** {f.epithet}{god} ({f.role}){fac}.{fate}")
    lines.append("")

    lines.append("## Factions")
    for k in w.factions:
        fallen = f", fell year {k.fallen_year}" if k.fallen_year else ""
        lines.append(f"- **{k.name}** ({k.kind}), seat {k.seat}, founded year {k.founded_year}{fallen}.")
    lines.append("")
    return "\n".join(lines)
