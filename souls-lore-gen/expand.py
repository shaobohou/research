"""Deterministic depth-on-demand: expand one event into a level of sub-events.

Each expansion is seeded from (world_seed, node_id), so expanding a given
node always yields the same skeleton — depth is materialized lazily but
reproducibly. The skeleton is deliberately plain; the LLM elaboration pass
(loregen.elaborate) enriches the prose and adds texture notes afterwards.

Expansions may also mint 1–2 new artifacts tied to the sub-events: new items
are the natural surface through which new depth reaches the player.
"""

from __future__ import annotations

import random

from ledger import Ledger, LedgerError
from worldsim import BIAS_BY_KIND, FALSE_RUMORS, Namer

MINOR_ROLES = [
    "chronicler", "siege captain", "lantern-bearer", "deserter",
    "handmaid", "gravedigger", "envoy", "quartermaster", "novice",
    "witness", "bell-ringer", "cartwright",
]

MINOR_EPITHETS = [
    "the Younger", "One-hand", "of the Rearguard", "the Meek",
    "Thrice-pardoned", "the Sleepless", "of No House", "the Plain",
    "Cinder-shod", "the Unlettered", "Long-memoried", "the Stray",
]


class Expander:
    def __init__(self, lg: Ledger, node_id: str):
        parent = lg.get(node_id)
        if parent["type"] != "event":
            raise LedgerError(f"{node_id} is not an event")
        if parent["expanded"]:
            kids = ", ".join(cid for cid, _ in lg.children_of(node_id))
            raise LedgerError(
                f"{node_id} is already expanded; deepen one of its children "
                f"instead ({kids})")
        self.lg = lg
        self.node_id = node_id
        self.parent = parent
        self.depth = parent["depth"] + 1
        # Deterministic per-node stream: same node -> same skeleton,
        # regardless of when it is expanded.
        self.rng = random.Random(f"{lg.meta['seed']}:{node_id}")
        self.namer = Namer(self.rng, used=set(lg.meta["used_names"]))
        self.source = f"expansion:{node_id}"

    # -- helpers ---------------------------------------------------------------

    def _year(self, back: int = 6) -> int:
        """A year in the window leading up to (and including) the parent."""
        y = self.parent["year"]
        return max(0, y - self.rng.randint(0, back))

    def _minor(self, role: str | None = None) -> str:
        name = self.namer.person()
        # Namer.used only guards this expander; the ledger claims it globally.
        return self.lg.add_figure(
            name, self.rng.choice(MINOR_EPITHETS),
            role or self.rng.choice(MINOR_ROLES),
            None, self.depth, self.source)

    def _alive(self, year: int) -> list[str]:
        """Parent participants who can still act in `year`."""
        out = []
        for pid in self.parent["participants"]:
            p = self.lg.get(pid)
            if p["fate_year"] is None or year <= p["fate_year"]:
                out.append(pid)
        return out

    def _event(self, kind: str, year: int, text: str,
               hidden: str | None = None,
               participants: list[str] | None = None) -> str:
        return self.lg.add_event(kind, year, text, hidden,
                                 participants or [], self.node_id,
                                 self.depth, self.source)

    def _artifact(self, name: str, item_type: str, year: int,
                  provenance: list[str], hint_chance: float = 0.3) -> str:
        rng = self.rng
        hints = None
        if rng.random() < hint_chance:
            hints = min(self.depth, len(self.lg.meta["veils"]) - 1)
        facts = []
        for eid in provenance:
            e = self.lg.get(eid)
            facts.append(f"(year {e['year']}) {e['text']}")
            if e["hidden"] and rng.random() < 0.5:
                facts.append(f"[half-known secret] {e['hidden']}")
        facts.append(f"The affliction of this world: "
                     f"{self.lg.meta['curse_name']} — {self.lg.meta['curse_desc']}.")
        return self.lg.add_artifact(
            name, item_type, year, None, provenance, facts,
            BIAS_BY_KIND[None],
            rng.choice(FALSE_RUMORS) if rng.random() < 0.35 else None,
            hints, self.depth, self.source)

    # -- templates ----------------------------------------------------------------

    def _t_great_war(self) -> tuple[list[str], list[str]]:
        rng, p = self.rng, self.parent
        events, items = [], []
        battle_place = self.namer.place()
        y1 = self._year(4)
        captain = self._minor("siege captain")
        events.append(self._event(
            "battle", y1,
            f"The war's worst day was at {battle_place}, where the line held "
            f"for a night and a morning under {self.lg.get(captain)['name']} "
            f"{self.lg.get(captain)['epithet']}, and then did not hold.",
            participants=[captain] + self._alive(y1)[:1]))
        y2 = min(p["year"], y1 + rng.randint(1, 3))
        duelists = self._alive(y2)[:2]
        events.append(self._event(
            "champion's duel", y2,
            "Before the last assault, champions met between the hosts, as the "
            "old law required. What was said there was not recorded; what was "
            "done there decided the war.",
            hidden="The duel was not fought to a death but to a bargain.",
            participants=duelists))
        items.append(self._artifact(
            f"Torn Standard of {battle_place}", "talisman", y1,
            [events[0]], hint_chance=0.2))
        return events, items

    def _t_betrayal(self) -> tuple[list[str], list[str]]:
        rng = self.rng
        events, items = [], []
        y1 = self._year(5)
        gobetween = self._minor("envoy")
        events.append(self._event(
            "secret council", y1,
            f"Twice before the gates opened, a go-between came by night — "
            f"{self.lg.get(gobetween)['name']} {self.lg.get(gobetween)['epithet']}, "
            f"who carried no letters and remembered everything.",
            participants=[gobetween] + self._alive(y1)[:1]))
        y2 = min(self.parent["year"], y1 + rng.randint(1, 4))
        events.append(self._event(
            "the price named", y2,
            "The grievance the chronicles cannot agree on was, by one account, "
            "no grievance at all, but a promise concerning the marked.",
            hidden="The promise was made in another's name, without their knowledge.",
            participants=self._alive(y2)[:1]))
        items.append(self._artifact(
            f"Unsigned Letter of {self.namer.place()}", "key item", y2,
            events[:], hint_chance=0.4))
        return events, items

    def _t_rite(self) -> tuple[list[str], list[str]]:
        events, items = [], []
        y1 = self._year(3)
        attendant = self._minor("novice")
        events.append(self._event(
            "the choosing", y1,
            f"The saint was not the first choice. The first choice ran, and "
            f"was let run; the chronicles kept the saint's serenity and lost "
            f"the running.",
            hidden="The one who ran was never pursued, by design.",
            participants=[attendant]))
        y2 = self.parent["year"]
        events.append(self._event(
            "the procession", y2,
            f"The procession took the long road, through every village, so "
            f"that all might see what their deliverance cost. "
            f"{self.lg.get(attendant)['name']} walked at the saint's left hand "
            f"and never afterward spoke of it.",
            participants=[attendant] + self._alive(y2)[:2]))
        items.append(self._artifact(
            f"Processional {self.rng.choice(self.lg.meta['relic_nouns']).capitalize()}",
            "talisman", y2, [events[1]], hint_chance=0.35))
        return events, items

    def _t_twilight(self) -> tuple[list[str], list[str]]:
        events, items = [], []
        y1 = self._year(8)
        petitioner = self._minor("witness")
        events.append(self._event(
            "last audience", y1,
            f"In the god's final season, audiences grew strange: petitioners "
            f"were answered before they spoke, and one — "
            f"{self.lg.get(petitioner)['name']} {self.lg.get(petitioner)['epithet']} — "
            f"was sent away with an apology no one understood.",
            participants=[petitioner] + self._alive(y1)[:1]))
        y2 = self.parent["year"]
        events.append(self._event(
            "the empty seat", y2,
            "The throne was found attended: candles lit, regalia arranged, "
            "as if for a guest expected momentarily. Nothing was disturbed. "
            "Nothing has been disturbed since.",
            hidden="The arrangement was the god's own last act, and it was an answer."))
        items.append(self._artifact(
            f"Candle of the {self.namer.place()} Vigil", "consumable", y2,
            [events[1]], hint_chance=0.5))
        return events, items

    def _t_sealing(self) -> tuple[list[str], list[str]]:
        rng = self.rng
        events, items = [], []
        y = self.parent["year"]
        names = [self._minor("champion") for _ in range(2)]
        listed = " and ".join(
            f"{self.lg.get(n)['name']} {self.lg.get(n)['epithet']}" for n in names)
        events.append(self._event(
            "the paying of the price", y,
            f"Of the champions spent on the seal, most are a list now; two are "
            f"still prayed to by name — {listed} — though none can say what "
            f"distinguishes the remembered dead from the rest.",
            participants=names))
        for n in names:
            f = self.lg.get(n)
            f["fate"] = "given to the seal"
            f["fate_year"] = y
        events.append(self._event(
            "the wardens' charge", min(self.lg.meta["present_year"], y),
            "A wardenship was sworn over the seal, hereditary and unthanked. "
            "Its rolls have never once been complete.",
            hidden="The first warden asked to be bound to the seal, not appointed over it."))
        items.append(self._artifact(
            f"Warden's {rng.choice(self.lg.meta['relic_nouns']).capitalize()}-ring",
            "ring", y, events[:], hint_chance=0.3))
        return events, items

    def _t_generic(self) -> tuple[list[str], list[str]]:
        rng = self.rng
        events, items = [], []
        y1 = self._year()
        witness = self._minor()
        w = self.lg.get(witness)
        events.append(self._event(
            "testimony", y1,
            f"An account survives from {w['name']} {w['epithet']}, a "
            f"{w['role']}, set down against instruction and hidden in a "
            f"{rng.choice(['psalter', 'ledger', 'wall', 'coffin lid'])}.",
            participants=[witness]))
        y2 = min(self.parent["year"], y1 + rng.randint(0, 3))
        events.append(self._event(
            "aftermath", y2,
            f"In the months after, {rng.choice(['pilgrims', 'crows', 'debt-collectors', 'singers'])} "
            f"came in unusual numbers, and left in unusual silence.",
            hidden=("What they came for was not what the chronicles assumed."
                    if rng.random() < 0.5 else None)))
        if rng.random() < 0.5:
            items.append(self._artifact(
                f"Effects of {w['name']}", rng.choice(["ring", "consumable"]),
                y1, [events[0]], hint_chance=0.25))
        return events, items

    TEMPLATES = {
        "great war": _t_great_war,
        "betrayal": _t_betrayal,
        "rite of restoration": _t_rite,
        "twilight of a god": _t_twilight,
        "sealing": _t_sealing,
    }

    def run(self) -> tuple[list[str], list[str]]:
        """Returns (child_event_ids, new_artifact_ids)."""
        template = self.TEMPLATES.get(self.parent["kind"], Expander._t_generic)
        events, items = template(self)
        # Every dig opens a fresh locale off the deep roads — new ground the
        # seeker can then walk to. Its accounts and relics rest there, so
        # depth-on-demand grows the *map*, not just the timeline.
        locale = self.namer.place()
        pid = self.lg.next_id("p")
        self.lg.entities[pid] = {"type": "place", "name": locale,
                                 "source": self.source}
        if locale not in self.lg.meta["used_names"]:
            self.lg.meta["used_names"].append(locale)
        for cid in events:
            self.lg.get(cid)["place"] = pid
        for aid in items:
            a = self.lg.get(aid)
            a["site"] = pid
            a["placement"] = (f"Recovered at {locale}, off the deep roads, "
                              f"where the account had lain hidden.")
        self.parent["expanded"] = True
        return events, items


def expand_event(lg: Ledger, node_id: str) -> tuple[list[str], list[str]]:
    return Expander(lg, node_id).run()
