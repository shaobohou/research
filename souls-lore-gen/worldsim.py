"""Seeded procedural history simulator — a beat grammar, not a script.

A history is *assembled* rather than executed. Each BEAT declares an era it
can occur in, a precondition over world state, a weight, and whether it may
repeat; the generator repeatedly picks an eligible beat and applies it. So one
world's adversary is sealed beneath a mountain, another's is bargained with
and walks free, and a third never rose at all. Some worlds have no church.
Some kingdoms fall to plague rather than treachery. Nothing downstream may
assume a particular beat happened.

Everything is driven by a single random.Random(seed), so a given seed
reproduces the same world exactly.

Institutions carry INTERESTS — what they need the past to have been. A beat
records which factions it `damages`, and a damaged faction is the one that
distorts that event when it retells it. Motive, not noise.
"""

from __future__ import annotations

import random
from dataclasses import asdict, dataclass, field

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

    def __init__(self, rng: random.Random, used: set[str] | None = None):
        self.rng = rng
        self.used: set[str] = set(used or ())

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
# Veil chains are institution-agnostic ("those who keep the rites" rather than
# "the church"), because a world may have no church.

ARCHETYPES = {
    "flame": {
        "primordial": "the First Ember",
        "gift": "warmth, disparity, and the colour of souls",
        "waning": "the Ember gutters; shadows lengthen and the dead forget to lie down",
        "curse_name": "the Gutter-mark",
        "curse_desc": "a grey brand that spreads over the heart; the marked wander until their names burn out",
        "adversary_title": "the Cinder-Eater",
        "relic_nouns": ["ember", "cinder", "brand", "pyre", "ash"],
        "veils": [
            "The rites of rekindling consume souls faster than the Ember returns them, and those who keep the rites keep the arithmetic hidden.",
            "The Ember is not dying — it is being siphoned to prolong the reign of those who drink from it, and the curse is the siphon's residue.",
            "The siphon was the Ember's own bargain: it feeds its drinkers so that something older, asleep in its heart, stays asleep. They know, and keep drinking.",
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
        "veils": [
            "The drownings are not offerings. They are silencings — of what the drowned heard in the tide.",
            "The Radiance never drowned — it was drowned, by the very powers that now pray for its return.",
            "They drowned it in mercy, at its own asking: it had begun to remember the world before this one, and memory is contagious.",
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
        "veils": [
            "The pruning-hooks are not symbols; something is still cut from the Root each season, and burned unseen.",
            "The Root grew from a buried corpse, and the order it grants is that corpse's refusal to be forgotten.",
            "The corpse is not dead but dreaming in sequence; the seasons are its heartbeats, and the rot began when it started to wake.",
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
        "veils": [
            "The shards that are kept and venerated are not relics but ransoms, paid to keep the nights scheduled.",
            "The gentle light was never the Moon's — it is borrowed, and the lender has begun to collect.",
            "The Moon broke itself to hide the lender's name among its shards; assembled, they would speak it, and the debt would come due at once.",
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
        "veils": [
            "The bells are not rung in honour of the Chord but to drown out something singing underneath it.",
            "The Chord is not fading — it is being sung backwards, deliberately, from somewhere beneath the oldest bell.",
            "The backwards singer is the Chord's own first note, cast out so the harmony could begin; it does not want silence — it wants its place back.",
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

EPITHETS = [
    "the Unbowed", "the Twice-crowned", "the Grey", "the Lantern-eyed",
    "of the Long Vigil", "the Kindly", "the Forsworn", "Half-remembered",
    "the Adamant", "of the Last Door", "the Saltborn", "the Quiet",
]

ITEM_TYPES = [
    "weapon", "armor", "ring", "talisman", "soul remnant",
    "key item", "consumable", "catalyst",
]

BIAS_BY_KIND = {
    "kingdom": "courtly and proud; flatters its founders, omits their crimes",
    "church": "liturgical; frames all loss as trial and all doubt as sin",
    "order": "austere and dutiful; honours oaths, distrusts miracles",
    "cult": "conspiratorial; blames the powers above, half-right and overreaching",
    None: "a peddler's patter; wonder-struck, unreliable on names and dates",
}

# What each kind of institution needs the past to have been. A faction whose
# interest an event damages is the faction that misremembers that event.
INTERESTS_BY_KIND = {
    "kingdom": ["the legitimacy of its royal line",
                "the blamelessness of the realm in its own fall"],
    "church": ["the efficacy of its rites",
               "the sanctity of its founder",
               "that suffering is a trial and not a bill"],
    "order": ["the honour of its oath",
              "that its vigil was never futile"],
    "cult": ["that the powers above are the cause of all this",
             "that its own bargains were kept"],
}

FALSE_RUMORS = [
    "names the wrong slayer for a famous death",
    "claims the relic was a gift when it was plunder",
    "places the event a whole age too early",
    "attributes the deed to a power that had no part in it",
    "insists the dead figure still lives, in hiding",
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
    fate: str | None = None
    fate_year: int | None = None


@dataclass
class Faction:
    id: str
    name: str
    kind: str                      # kingdom | order | church | cult
    seat: str
    founded_year: int
    founder_id: str | None
    fallen_year: int | None = None
    interests: list[str] = field(default_factory=list)


@dataclass
class Event:
    id: str
    year: int
    kind: str
    text: str
    hidden: str | None = None
    participants: list[str] = field(default_factory=list)   # who ACTED
    # Named without acting — a destination the dead once was, a sealed
    # adversary others dig toward. Kept distinct so the causal rule
    # ("no one acts after their fate") stays enforceable.
    referents: list[str] = field(default_factory=list)
    # Factions whose interests this event injures. They are the ones who will
    # get it wrong when they retell it.
    damages: list[str] = field(default_factory=list)


@dataclass
class Artifact:
    id: str
    name: str
    item_type: str
    created_year: int
    origin_faction_id: str | None
    provenance: list[str]
    knowledge: list[str]
    bias: str
    false_rumor: str | None = None
    hints_mystery: bool = False


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
    veils: list[str] = field(default_factory=list)
    used_names: list[str] = field(default_factory=list)
    ages: list[Age] = field(default_factory=list)
    figures: list[Figure] = field(default_factory=list)
    factions: list[Faction] = field(default_factory=list)
    events: list[Event] = field(default_factory=list)
    artifacts: list[Artifact] = field(default_factory=list)

    def fig(self, fid: str) -> Figure:
        return next(f for f in self.figures if f.id == fid)

    def fac(self, fid: str) -> Faction:
        return next(f for f in self.factions if f.id == fid)

    def ev(self, eid: str) -> Event:
        return next(e for e in self.events if e.id == eid)

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# The grammar engine
# ---------------------------------------------------------------------------

AGE_DEFS = [
    ("the Age of the Gift", 6, 10),
    ("the Age of Names", 7, 11),
    ("the Age of Dusk", 4, 7),
]


class _Gen:
    def __init__(self, seed: int, n_items: int):
        self.rng = random.Random(seed)
        self.namer = Namer(self.rng)
        self.n_items = max(6, n_items)
        self._ids: dict[str, int] = {}
        self.flags: set[str] = set()
        self.counts: dict[str, int] = {}

        key = self.rng.choice(sorted(ARCHETYPES))
        arch = ARCHETYPES[key]
        self.world = World(
            seed=seed, archetype_key=key, archetype=arch,
            primordial_name=arch["primordial"],
            mystery=arch["veils"][1], veils=list(arch["veils"]),
        )
        self.year = 0
        self.era = 0

    # -- plumbing ------------------------------------------------------------

    def _id(self, prefix: str) -> str:
        self._ids[prefix] = self._ids.get(prefix, 0) + 1
        return f"{prefix}{self._ids[prefix]}"

    def event(self, kind: str, text: str, hidden: str | None = None,
              participants: list[str] | None = None,
              referents: list[str] | None = None,
              damages: list[str] | None = None) -> Event:
        e = Event(self._id("e"), self.year, kind, text, hidden,
                  participants or [], referents or [], damages or [])
        self.world.events.append(e)
        return e

    def advance(self, lo: int, hi: int):
        self.year += self.rng.randint(lo, hi)

    def figure(self, role: str, faction_id: str | None,
               is_god: bool = False, epithet: str | None = None) -> Figure:
        f = Figure(self._id("f"), self.namer.person(),
                   epithet or self.rng.choice(EPITHETS), role, faction_id,
                   is_god=is_god)
        self.world.figures.append(f)
        return f

    def faction(self, name: str, kind: str, founder: Figure | None) -> Faction:
        k = Faction(self._id("k"), name, kind, seat=self.namer.place(),
                    founded_year=self.year,
                    founder_id=founder.id if founder else None,
                    interests=list(INTERESTS_BY_KIND.get(kind, [])))
        self.world.factions.append(k)
        return k

    def artifact(self, name: str, item_type: str, faction: Faction | None,
                 provenance: list[Event]) -> Artifact:
        a = Artifact(self._id("a"), name, item_type, self.year,
                     faction.id if faction else None,
                     [e.id for e in provenance], [], "")
        self.world.artifacts.append(a)
        return a

    def noun(self) -> str:
        return self.rng.choice(self.world.archetype["relic_nouns"])

    # -- state queries -------------------------------------------------------

    def gods(self, alive: bool | None = None) -> list[Figure]:
        gs = [f for f in self.world.figures if f.is_god and f.role == "god"]
        if alive is True:
            gs = [g for g in gs if not g.fate]
        return gs

    def facs(self, kind: str | None = None, standing: bool = True) -> list[Faction]:
        ks = self.world.factions
        if kind:
            ks = [k for k in ks if k.kind == kind]
        if standing:
            ks = [k for k in ks if not k.fallen_year]
        return list(ks)

    def n(self, beat: str) -> int:
        return self.counts.get(beat, 0)

    # ==================================================================
    # BEATS. Each is (era, weight, max_times, precondition, apply).
    # ==================================================================

    # ---- Era 0: the Age of the Gift ----------------------------------

    def _ok_claiming(self):
        return len(self.gods()) < 5

    def _do_claiming(self):
        dom = self.rng.choice([d for d in GOD_DOMAINS
                               if d not in {g.epithet[7:] for g in self.gods()}]
                              or GOD_DOMAINS)
        g = self.figure("god", None, is_god=True, epithet=f"god of {dom}")
        self.advance(3, 20)
        self.event("claiming",
                   f"{g.name}, {g.epithet}, claimed a portion of the gift and "
                   f"took a throne.", participants=[g.id])

    def _ok_divine_house(self):
        return any(g.faction_id is None for g in self.gods(alive=True))

    def _do_divine_house(self):
        g = next(g for g in self.gods(alive=True) if g.faction_id is None)
        self.advance(10, 40)
        kind = "kingdom" if self.rng.random() < 0.6 else "church"
        k = self.faction(self.namer.place(), kind, g)
        g.faction_id = k.id
        self.event("founding",
                   f"{g.name} founded {k.name} ({k.kind}) at {k.seat}.",
                   participants=[g.id])
        # regalia
        art_type = self.rng.choice(["weapon", "talisman", "catalyst", "ring"])
        e = self.event("forging",
                       f"The {self.noun().capitalize()} of {g.name} was wrought "
                       f"as regalia of {g.name}'s throne.", participants=[g.id])
        self.artifact(f"{self.noun().capitalize()} of {g.name}", art_type, k, [e])

    def _ok_war(self):
        return len(self.gods()) >= 2 and "war" not in self.flags

    def _do_war(self):
        arch = self.world.archetype
        adv = self.figure("adversary", None, is_god=True,
                          epithet=arch["adversary_title"])
        self.advance(30, 80)
        gs = self.gods(alive=True)
        champ = self.rng.choice(gs)
        traitor = self.rng.choice([g for g in gs if g is not champ]) if len(gs) > 1 else None
        hidden = (f"{traitor.name} treated with {adv.name} in secret and was "
                  f"spared what followed." if traitor else None)
        self.event("great war",
                   f"{adv.name}, {adv.epithet}, rose against the thrones. "
                   f"{champ.name} led the powers to war.",
                   hidden=hidden,
                   participants=[adv.id, champ.id] + ([traitor.id] if traitor else []))
        self.flags.add("war")
        self.state_adv = adv
        self.state_champ = champ
        noun = self.noun()
        self.artifact(f"{champ.name}'s War-{noun.capitalize()}", "weapon",
                      None, [self.world.events[-1]])

    def _ok_war_end(self):
        return "war" in self.flags and "war_resolved" not in self.flags

    def _war_closer(self) -> Figure | None:
        """Wars can outlast the god who led them. Whoever finishes it must be
        alive to do so; if no power is left standing, none is named."""
        if not self.state_champ.fate:
            return self.state_champ
        alive = self.gods(alive=True)
        return self.rng.choice(alive) if alive else None

    def _ok_mutual_ruin(self):
        # only the living can destroy one another
        return self._ok_war_end() and not self.state_champ.fate

    def _do_sealing(self):
        adv = self.state_adv
        closer = self._war_closer()
        self.advance(5, 15)
        where = self.namer.place()
        n = self.rng.randint(3, 9)
        who = (f"{closer.name}, who took up the war after "
               f"{self.state_champ.name} fell, " if closer and closer is not
               self.state_champ else "")
        self.event("sealing",
                   f"{who}sealed {adv.name} beneath {where} at the war's end; "
                   f"the seal was bought with the lives of {n} champions."
                   if who else
                   f"{adv.name} was defeated and sealed beneath {where}; the "
                   f"seal was bought with the lives of {n} champions.",
                   participants=[adv.id] + ([closer.id] if closer else []))
        adv.fate = f"sealed beneath {where}"
        adv.fate_year = self.year
        self.flags.update({"war_resolved", "sealed"})
        self.sealed_at = where

    def _do_truce(self):
        adv = self.state_adv
        closer = self._war_closer()
        self.advance(5, 15)
        self.event("the bargain",
                   f"{adv.name} was not defeated. A bargain was struck whose "
                   f"terms no chronicle records, and {adv.name} withdrew "
                   f"unbroken into the deep places.",
                   hidden=(f"The price of the bargain was paid in something the "
                           f"powers have never named, and are still paying."),
                   participants=[adv.id] + ([closer.id] if closer else []))
        adv.fate = "withdrew unbroken under terms unrecorded"
        adv.fate_year = self.year
        self.flags.update({"war_resolved", "bargained"})

    def _do_mutual_ruin(self):
        adv, champ = self.state_adv, self.state_champ
        self.advance(5, 15)
        self.event("mutual ruin",
                   f"{adv.name} and {champ.name} destroyed one another at the "
                   f"war's end. Neither throne nor grave was left to either.",
                   hidden=f"{champ.name} chose it, knowing the cost.",
                   participants=[adv.id, champ.id])
        for f in (adv, champ):
            f.fate = "unmade at the war's end"
            f.fate_year = self.year
        self.flags.update({"war_resolved", "ruined"})

    def _ok_schism(self):
        return len(self.gods(alive=True)) >= 3 and "schism" not in self.flags

    def _do_schism(self):
        a, b = self.rng.sample(self.gods(alive=True), 2)
        self.advance(20, 60)
        loser = self.rng.choice([a, b])
        winner = b if loser is a else a
        self.event("divine schism",
                   f"{a.name} and {b.name} fell to war over a single domain. "
                   f"{winner.name} kept it; {loser.name} was cast down and is "
                   f"named in no liturgy since.",
                   hidden=f"The domain was never {winner.name}'s to keep.",
                   participants=[a.id, b.id])
        loser.fate = "cast down in the schism"
        loser.fate_year = self.year
        self.flags.add("schism")

    # ---- Era 1: the Age of Names -------------------------------------

    def _ok_waning(self):
        return "waning" not in self.flags

    def _do_waning(self):
        arch = self.world.archetype
        self.advance(20, 60)
        self.event("waning",
                   f"The waning began: {arch['waning']}. Mortals called the "
                   f"affliction {arch['curse_name']}: {arch['curse_desc']}.")
        self.flags.add("waning")

    def _ok_order(self):
        return "waning" in self.flags and not self.facs("order")

    def _do_order(self):
        arch = self.world.archetype
        f = self.figure("knight", None)
        self.advance(10, 30)
        k = self.faction(f"Order of the {self.noun().capitalize()}", "order", f)
        f.faction_id = k.id
        self.event("founding",
                   f"{f.name} {f.epithet} founded the {k.name} at {k.seat}, "
                   f"sworn to stand against {arch['curse_name']}.",
                   participants=[f.id])

    def _ok_church(self):
        return bool(self.gods()) and len(self.facs("church")) < 2

    def _do_church(self):
        patron = self.rng.choice(self.gods())
        self.advance(5, 25)
        k = self.faction(f"Church of {patron.name}", "church", None)
        pr = self.figure("high priest", k.id)
        self.event("founding",
                   f"The {k.name} was raised at {k.seat}; {pr.name} {pr.epithet} "
                   f"took its first pulpit, preaching that the waning is a trial "
                   f"and the faithful will be spared.",
                   participants=[pr.id], referents=[patron.id])

    def _ok_heresy(self):
        return bool(self.facs("church")) and not self.facs("cult")

    def _do_heresy(self):
        church = self.rng.choice(self.facs("church"))
        self.advance(5, 25)
        h = self.figure("heretic scholar", None)
        k = self.faction(
            f"Cult of the {self.rng.choice(['Open Door', 'Second Dawn', 'Patient Below', 'True ' + self.noun().capitalize()])}",
            "cult", h)
        h.faction_id = k.id
        self.event("heresy",
                   f"{h.name} {h.epithet} was cast out of {church.name} and "
                   f"founded the {k.name}, teaching that the powers above "
                   f"themselves caused the waning.",
                   hidden="The heresy is nearer the truth than the sermon.",
                   participants=[h.id], damages=[church.id])

    def _ok_kingdom(self):
        return len([k for k in self.world.factions if k.kind == "kingdom"
                    and k.founder_id and not self.world.fig(k.founder_id).is_god]) < 2

    def _do_kingdom(self):
        m = self.figure(self.rng.choice(["king", "queen"]), None)
        self.advance(10, 30)
        k = self.faction(self.namer.place(), "kingdom", m)
        m.faction_id = k.id
        self.event("founding",
                   f"{m.name} {m.epithet} united the river-clans and was crowned "
                   f"in {k.seat}; the realm took the name {k.name}.",
                   participants=[m.id])

    def _ok_rite(self):
        return "waning" in self.flags and (self.facs("church") or self.facs("cult")) \
            and self.n("rite") < 2

    def _do_rite(self):
        keeper = self.rng.choice(self.facs("church") or self.facs("cult"))
        urger = next((f for f in self.world.figures
                      if f.faction_id == keeper.id and not f.is_god
                      and not f.fate), None) \
            or self.figure("high priest", keeper.id)
        self.advance(15, 45)
        saint = self.figure("pilgrim saint", keeper.id)
        e = self.event(
            "rite of restoration",
            f"At the urging of {urger.name}, the saint {saint.name} "
            f"{saint.epithet} was given to {self.world.primordial_name} in the "
            f"rite of restoration. For a generation, the waning slowed.",
            hidden=(f"The rite did not restore anything. It only fed the waning "
                    f"more slowly — and {urger.name} suspected as much."),
            participants=[urger.id, saint.id], damages=[keeper.id])
        saint.fate = "given to the rite of restoration"
        saint.fate_year = self.year
        self.artifact(f"{self.noun().capitalize()} of Saint {saint.name}",
                      "talisman", keeper, [e])
        self.artifact(f"Remnant Soul of Saint {saint.name}", "soul remnant",
                      keeper, [e])

    def _ok_betrayal(self):
        return bool(self.facs("kingdom")) and len(self.world.factions) >= 2 \
            and "betrayed" not in self.flags

    def _do_betrayal(self):
        realm = self.rng.choice(self.facs("kingdom"))
        monarch = self.world.fig(realm.founder_id) if realm.founder_id else None
        other = self.rng.choice([k for k in self.world.factions if k is not realm])
        self.advance(20, 50)
        t = self.figure("oathbreaker general", realm.id)
        promiser = self.rng.choice(self.facs("cult") or [other])
        self.event(
            "betrayal",
            f"{t.name} {t.epithet}, sword-hand of "
            f"{monarch.name if monarch else 'the crown'}, opened the gates of "
            f"{realm.seat} to the {other.name} over a grievance no chronicle "
            f"agrees on.",
            hidden=(f"{t.name} acted on a promise from the {promiser.name}: that "
                    f"the marked of their house would be spared "
                    f"{self.world.archetype['curse_name']}. The promise was not kept."),
            participants=[t.id] + ([monarch.id] if monarch else []),
            damages=[realm.id, promiser.id])
        self.flags.add("betrayed")
        self.betrayed_realm = realm
        self.traitor = t

    def _ok_fall(self):
        return bool(self.facs("kingdom")) and self.n("fall") < 1

    def _do_fall(self):
        if "betrayed" in self.flags and self.betrayed_realm in self.facs("kingdom"):
            realm, cause = self.betrayed_realm, "betrayal"
        else:
            realm = self.rng.choice(self.facs("kingdom"))
            cause = self.rng.choice(["plague", "succession"])
        monarch = self.world.fig(realm.founder_id) if realm.founder_id else None
        self.advance(1, 6)
        if cause == "betrayal":
            who = (f"{monarch.name}, {monarch.epithet}," if monarch
                   else "Its sovereign")
            text = (f"{realm.name} fell. {who} died at the foot of their own "
                    f"throne; the crown was carried away and never worn again.")
            hidden = None
        elif cause == "plague":
            text = (f"{realm.name} was not conquered. "
                    f"{self.world.archetype['curse_name']} took the capital "
                    f"street by street, and the gates were shut from within by "
                    f"those still able.")
            hidden = ("The order to shut the gates came from inside the palace, "
                      "and the sovereign was on the wrong side of them.")
        else:
            text = (f"{realm.name} came apart over a succession no one could "
                    f"prove. Three claimants were crowned in one year; none of "
                    f"the three is buried anywhere the realm admits.")
            hidden = "The eldest claim was the true one, and was the first buried."
        e = self.event(f"fall of a kingdom", text, hidden=hidden,
                       participants=[], referents=[monarch.id] if monarch else [],
                       damages=[realm.id])
        if monarch:
            monarch.fate = ("slain at their own throne" if cause == "betrayal"
                            else f"lost in the {cause}")
            monarch.fate_year = self.year
        realm.fallen_year = self.year
        self.artifact(f"Hollow Crown of {realm.name}", "key item", realm, [e])
        if cause == "betrayal":
            self.artifact(f"{self.traitor.name}'s Oathbreaker Blade", "weapon",
                          realm, [e])
            self.advance(2, 10)
            self.event("fate",
                       f"{self.traitor.name} was found bearing "
                       f"{self.world.archetype['curse_name']}, and was not spared.",
                       participants=[self.traitor.id])
            self.traitor.fate = f"succumbed to {self.world.archetype['curse_name']}"
            self.traitor.fate_year = self.year

    def _ok_wardens(self):
        return "sealed" in self.flags and "wardens" not in self.flags

    def _do_wardens(self):
        self.advance(10, 40)
        e = self.event("the wardens' charge",
                       f"A wardenship was sworn over the seal beneath "
                       f"{self.sealed_at}, hereditary and unthanked. Its rolls "
                       f"have never once been complete.",
                       hidden="The first warden asked to be bound to the seal, "
                              "not appointed over it.")
        self.artifact(f"Warden's {self.noun().capitalize()}-ring", "ring",
                      None, [e])
        self.flags.add("wardens")

    def _ok_golden(self):
        return "waning" in self.flags and "golden" not in self.flags

    def _do_golden(self):
        self.advance(20, 50)
        self.event("a season of plenty",
                   f"For thirty years the waning simply stopped. Orchards bore, "
                   f"the marked recovered, and it was called a mercy. Then it "
                   f"resumed, exactly where it had left off.",
                   hidden="Something was being paid during those thirty years, "
                          "and the payments were recorded nowhere.")
        self.flags.add("golden")

    # ---- Era 2: the Age of Dusk --------------------------------------

    def _ok_twilight(self):
        return bool(self.gods(alive=True)) and self.n("twilight") < 2

    def _do_twilight(self):
        g = self.rng.choice(self.gods(alive=True))
        self.advance(20, 60)
        mode = self.rng.choice(["below", "unmade", "marked"])
        if mode == "below":
            text = (f"{g.name}, {g.epithet}, descended below the world to look "
                    f"upon {self.world.primordial_name} directly, and did not "
                    f"return.")
            hidden = f"{g.name} found the truth of the waning, and chose to stay."
            fate = "descended below the world; did not return"
        elif mode == "unmade":
            text = (f"{g.name}, {g.epithet}, was unmade upon their own throne. "
                    f"No wound was found, and no successor dared the seat.")
            hidden = ("What unmade them was not violence but understanding — a "
                      "truth arrived at, all at once.")
            fate = "unmade upon their throne"
        else:
            text = (f"{g.name}, {g.epithet}, took "
                    f"{self.world.archetype['curse_name']} — the first of the "
                    f"powers to bear it — and wandered from their seat.")
            hidden = ("The curse does not distinguish powers from mortals. It "
                      "never did.")
            fate = f"took {self.world.archetype['curse_name']} and wandered"
        e = self.event("twilight of a god", text, hidden=hidden,
                       participants=[g.id])
        g.fate, g.fate_year = fate, self.year
        self.artifact(f"Soul of {g.name}", "soul remnant",
                      self.world.fac(g.faction_id) if g.faction_id else None, [e])
        self.lost_god = g

    def _ok_pilgrimage(self):
        return bool(self.facs("order")) and "pilgrimage" not in self.flags

    def _do_pilgrimage(self):
        order = self.rng.choice(self.facs("order"))
        self.advance(10, 40)
        hero = self.figure("wandering knight", order.id,
                           epithet=self.rng.choice(
                               ["the Latecomer", "the Ashen", "of the Empty Scabbard",
                                "the Unmarked", "Last-sworn"]))
        target = getattr(self, "lost_god", None)
        dest = (f"the place where {target.name} was lost" if target
                else "the deep roads, where the affliction is said to begin")
        q = self.event("last pilgrimage",
                       f"{hero.name} {hero.epithet}, last-sworn of the "
                       f"{order.name}, set out for {dest}, carrying the order's "
                       f"final blessing.",
                       participants=[hero.id],
                       referents=[target.id] if target else [])
        self.advance(3, 12)
        outcome, fate = self.rng.choice([
            (f"{hero.name} was last seen at the edge of the deep roads. The "
             f"order keeps a vigil that has not ended.", "vanished on the deep roads"),
            (f"{hero.name} returned once, said nothing, left their sword upon "
             f"the order's altar, and walked into the dusk unarmed.",
             "walked into the dusk unarmed"),
            (f"Word came that {hero.name} fell to the marked, and then word came "
             f"that {hero.name} led them. The order believes neither.",
             "fate contested"),
        ])
        e = self.event("hero's end", outcome, participants=[hero.id],
                       damages=[order.id])
        hero.fate, hero.fate_year = fate, self.year
        self.artifact(f"{hero.name}'s Set", "armor", order, [q, e])
        self.artifact(f"Ring of the {order.name.split('of the ')[-1]} Vigil",
                      "ring", order, [q, e])
        self.flags.add("pilgrimage")

    def _ok_seal_weakens(self):
        return "sealed" in self.flags and "seal_weakens" not in self.flags

    def _do_seal_weakens(self):
        adv = self.state_adv
        diggers = self.facs("cult")
        who = diggers[0].name if diggers else "pilgrims of no known house"
        self.advance(5, 30)
        e = self.event("the seal weakens",
                       f"Diggers of the {who} were found at the seal of "
                       f"{adv.name}. The wardens hanged nine; the digging "
                       f"continued.",
                       hidden=("The seal has been failing on its own since the "
                               "waning began. The diggers only follow the cracks."),
                       referents=[adv.id])
        self.artifact(f"Warding {self.noun().capitalize()}", "consumable",
                      diggers[0] if diggers else None, [e])
        self.flags.add("seal_weakens")

    def _ok_heir(self):
        return any(k.fallen_year for k in self.world.factions) and "heir" not in self.flags

    def _do_heir(self):
        fallen = self.rng.choice([k for k in self.world.factions if k.fallen_year])
        self.advance(10, 30)
        claimant = self.figure("claimant", None)
        e = self.event("an heir returns",
                       f"{claimant.name} {claimant.epithet} came to the ruin of "
                       f"{fallen.seat} bearing a claim to {fallen.name}, and was "
                       f"neither crowned nor turned away.",
                       hidden=f"The claim is false, and {claimant.name} knows it.",
                       participants=[claimant.id], damages=[fallen.id])
        self.artifact(f"{claimant.name}'s Forged Writ", "key item", fallen, [e])
        self.flags.add("heir")

    def _ok_marked(self):
        return "waning" in self.flags and "marked" not in self.flags

    def _do_marked(self):
        self.advance(10, 30)
        self.event("the marked keep the roads",
                   f"The afflicted stopped hiding. They keep the wayhouses now, "
                   f"and take no toll from those already bearing "
                   f"{self.world.archetype['curse_name']}.",
                   hidden="Among them are some who were never afflicted at all.")
        self.artifact(f"Wayhouse {self.noun().capitalize()}", "consumable",
                      None, [self.world.events[-1]])
        self.flags.add("marked")

    # ==================================================================

    def beats(self):
        G = _Gen
        return [
            # era, weight, cap, name, ok, do
            (0, 6, 5, "claiming", G._ok_claiming, G._do_claiming),
            (0, 5, 5, "divine house", G._ok_divine_house, G._do_divine_house),
            (0, 4, 1, "war", G._ok_war, G._do_war),
            (0, 3, 1, "sealing", G._ok_war_end, G._do_sealing),
            (0, 2, 1, "truce", G._ok_war_end, G._do_truce),
            (0, 1, 1, "ruin", G._ok_mutual_ruin, G._do_mutual_ruin),
            # a war may also outlast its age and be settled in the next
            (1, 4, 1, "sealing", G._ok_war_end, G._do_sealing),
            (1, 3, 1, "truce", G._ok_war_end, G._do_truce),
            (0, 2, 1, "schism", G._ok_schism, G._do_schism),
            (1, 9, 1, "waning", G._ok_waning, G._do_waning),
            (1, 5, 1, "order", G._ok_order, G._do_order),
            (1, 5, 2, "church", G._ok_church, G._do_church),
            (1, 4, 1, "heresy", G._ok_heresy, G._do_heresy),
            (1, 5, 2, "kingdom", G._ok_kingdom, G._do_kingdom),
            (1, 4, 2, "rite", G._ok_rite, G._do_rite),
            (1, 4, 1, "betrayal", G._ok_betrayal, G._do_betrayal),
            (1, 4, 1, "fall", G._ok_fall, G._do_fall),
            (1, 3, 1, "wardens", G._ok_wardens, G._do_wardens),
            (1, 2, 1, "golden", G._ok_golden, G._do_golden),
            (2, 6, 2, "twilight", G._ok_twilight, G._do_twilight),
            (2, 5, 1, "pilgrimage", G._ok_pilgrimage, G._do_pilgrimage),
            (2, 4, 1, "seal weakens", G._ok_seal_weakens, G._do_seal_weakens),
            (2, 3, 1, "heir", G._ok_heir, G._do_heir),
            (2, 3, 1, "marked", G._ok_marked, G._do_marked),
        ]

    def run(self) -> World:
        w, rng = self.world, self.rng
        arch = w.archetype

        # the one mandatory beat: something gave, and there was a world
        w.ages.append(Age(AGE_DEFS[0][0], 0, None,
                          f"{w.primordial_name} gave the world {arch['gift']}."))
        self.event("cosmogony",
                   f"{w.primordial_name} rose (or was raised — the tellings "
                   f"differ) and gave the world {arch['gift']}.")

        table = self.beats()
        for era, (age_name, lo, hi) in enumerate(AGE_DEFS):
            if era > 0:
                self.advance(40, 150)
                w.ages[-1].end = self.year
                blurb = ("The powers withdrew to their high seats and mortals "
                         "learned to matter."
                         if era == 1 else
                         "The present age. What remains keeps the roads, and "
                         "pilgrims walk toward rumours of a cure.")
                w.ages.append(Age(age_name, self.year, None, blurb))
            self.era = era
            for _ in range(rng.randint(lo, hi)):
                pool = [(wt, nm, do) for (e, wt, cap, nm, ok, do) in table
                        if e == era and self.n(nm) < cap and ok(self)]
                if not pool:
                    break
                total = sum(p[0] for p in pool)
                pick = rng.uniform(0, total)
                acc = 0.0
                for wt, nm, do in pool:
                    acc += wt
                    if pick <= acc:
                        do(self)
                        self.counts[nm] = self.n(nm) + 1
                        break

        self.assign_knowledge()
        w.used_names = sorted(self.namer.used)
        return w

    # -- knowledge packets ---------------------------------------------------

    def assign_knowledge(self):
        w, rng = self.world, self.rng
        arch = w.archetype

        arts = w.artifacts
        rng.shuffle(arts)
        if len(arts) > self.n_items:
            keep, seen = [], set()
            for a in arts:
                if a.item_type not in seen:
                    keep.append(a)
                    seen.add(a.item_type)
            rest = [a for a in arts if a not in keep]
            rng.shuffle(rest)
            keep.extend(rest[: self.n_items - len(keep)])
            arts = keep
        w.artifacts = sorted(arts, key=lambda a: a.created_year)

        if w.artifacts:
            for a in rng.sample(w.artifacts,
                                k=min(3, max(2, len(w.artifacts) // 5))):
                a.hints_mystery = True

        for a in w.artifacts:
            fac = w.fac(a.origin_faction_id) if a.origin_faction_id else None
            a.bias = BIAS_BY_KIND[fac.kind if fac else None]

            facts: list[str] = []
            damaged = False
            for eid in a.provenance:
                e = w.ev(eid)
                facts.append(f"(year {e.year}) {e.text}")
                if e.hidden and rng.random() < 0.5:
                    facts.append(f"[half-known secret] {e.hidden}")
                if fac and fac.id in e.damages:
                    damaged = True
            part_ids = [pid for eid in a.provenance
                        for pid in (w.ev(eid).participants + w.ev(eid).referents)]
            fated = [w.fig(p) for p in part_ids if w.fig(p).fate]
            if fated:
                f0 = rng.choice(fated)
                facts.append(f"{f0.name}, {f0.epithet}: fate — {f0.fate} "
                             f"(year {f0.fate_year}).")
            if fac:
                facts.append(f"This item is kept/told of by {fac.name} "
                             f"({fac.kind}), seat at {fac.seat}.")
                if fac.interests:
                    facts.append("[keeper's interests] " + "; ".join(fac.interests))
            facts.append(f"The affliction of this world: {arch['curse_name']} — "
                         f"{arch['curse_desc']}.")
            a.knowledge = facts

            # Motive, not noise: a keeper misremembers what injures it. Others
            # only rarely garble anything.
            if damaged and rng.random() < 0.75:
                a.false_rumor = rng.choice(FALSE_RUMORS)
            elif rng.random() < 0.12:
                a.false_rumor = rng.choice(FALSE_RUMORS)


def generate_world(seed: int, n_items: int = 14) -> World:
    return _Gen(seed, n_items).run()

# Chronicle/codex rendering lives in ledger.py — the ledger is the single
# source of truth once a world exists on disk.
