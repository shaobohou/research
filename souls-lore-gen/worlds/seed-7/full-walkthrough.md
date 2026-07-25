# Full Walkthrough — seed-7, the world of the Pale Root

*A complete, unedited transcript of one seeker ("warden") playing the exploration API in the default **spatial + purist** mode (template writer — no API key here). Every tool call and its literal output, in order. Reproduce with `uv run demos.py transcript`.*

> Loop: `survey` (map) → `travel` → `look`/`examine` → `ask` → `delve` → `theorize`. You learn a place's relics only by walking there; no one will ever tell you that you are right.

## ▶ `survey()`

```json
{
  "world": "seed-7 (root)",
  "epigraph": "Of the Pale Root little now is spoken, and less is true. Gather what the old things still remember, and be sparing with belief.",
  "ages": [
    "the Age of the Gift",
    "the Age of Names",
    "the Age of Dusk"
  ],
  "you_are_at": "the Pilgrim Roads",
  "places_known": [
    {
      "place": "Galomerebarrow",
      "status": "heard of",
      "relics_seen": 0
    },
    {
      "place": "Ghalaecaelhollow",
      "status": "heard of",
      "relics_seen": 0
    },
    {
      "place": "Kaemisvault",
      "status": "heard of",
      "relics_seen": 0
    },
    {
      "place": "Karaeosvault",
      "status": "heard of",
      "relics_seen": 0
    },
    {
      "place": "Toromundmarch",
      "status": "heard of",
      "relics_seen": 0
    },
    {
      "place": "Ulirwyncradle",
      "status": "heard of",
      "relics_seen": 0
    },
    {
      "place": "Verenethreach",
      "status": "heard of",
      "relics_seen": 0
    },
    {
      "place": "the Pilgrim Roads",
      "status": "here",
      "relics_seen": 1
    }
  ],
  "budget": {
    "steps": 8,
    "delves": 5,
    "asks": 8
  },
  "hint": "travel(place) to walk somewhere you have heard of; look() to see what lies where you stand."
}
```

## ▶ `examine("Hollow Crown")`
*we have walked nowhere; knowledge is gated by the body*

```json
{
  "error": "You have not found the Hollow Crown of Olagarcradle. It lies somewhere you have not yet walked."
}
```

## ▶ `travel("Galomerebarrow")`

```json
{
  "arrived": "Galomerebarrow",
  "steps_left": 7,
  "place": "Galomerebarrow",
  "relics_here": [],
  "ways_onward": [
    "the Pilgrim Roads",
    "Olagarcradle"
  ],
  "hint": "examine(name) to study a relic here; a relic's resting place is itself a clue."
}
```

## ▶ `travel("Ghalaecaelhollow")`

```json
{
  "arrived": "Ghalaecaelhollow",
  "steps_left": 6,
  "place": "Ghalaecaelhollow",
  "relics_here": [
    {
      "id": "a3",
      "name": "Graft of Queliamund",
      "type": "catalyst",
      "how_it_lies": "Kept long at Ghalaecaelhollow, and then kept poorly.",
      "examined": false
    }
  ],
  "ways_onward": [
    "the Pilgrim Roads"
  ],
  "hint": "examine(name) to study a relic here; a relic's resting place is itself a clue."
}
```

## ▶ `examine("Graft of Queliamund")`

```json
{
  "id": "a3",
  "name": "Graft of Queliamund",
  "type": "catalyst",
  "description": "A catalyst attuned to the old gift.\n\nThe Graft of Queliamund was wrought as regalia of Queliamund's throne. The name endures; little else does.",
  "how_it_lies": "Kept long at Ghalaecaelhollow, and then kept poorly.",
  "leads": [
    {
      "name": "Queliamund",
      "kind": "figure"
    }
  ]
}
```

## ▶ `travel("Kaemisvault")`

```json
{
  "arrived": "Kaemisvault",
  "steps_left": 5,
  "place": "Kaemisvault",
  "relics_here": [
    {
      "id": "a5",
      "name": "Sap of Saint Caliadis",
      "type": "talisman",
      "how_it_lies": "Kept in a reliquary at Kaemisvault, before which the candles will not stay lit.",
      "examined": false
    },
    {
      "id": "a6",
      "name": "Remnant Soul of Saint Caliadis",
      "type": "soul remnant",
      "how_it_lies": "Kept in a reliquary at Kaemisvault, before which the candles will not stay lit.",
      "examined": false
    }
  ],
  "ways_onward": [
    "the Pilgrim Roads"
  ],
  "hint": "examine(name) to study a relic here; a relic's resting place is itself a clue."
}
```

## ▶ `examine("Sap of Saint Caliadis")`

```json
{
  "id": "a5",
  "name": "Sap of Saint Caliadis",
  "type": "talisman",
  "description": "A talisman for the invoking of half-forgotten rites.\n\nAt the urging of Belwyn, the saint Caliadis of the Long Vigil was given to the Pale Root in the rite of restoration. For a generation, the waning slowed. It is said that the rite did not restore anything. It only fed the waning more slowly \u2014 and Belwyn suspected as much. Whether this was mercy or malice, none agree.",
  "how_it_lies": "Kept in a reliquary at Kaemisvault, before which the candles will not stay lit.",
  "leads": [
    {
      "name": "Belwyn",
      "kind": "figure"
    },
    {
      "name": "Caliadis",
      "kind": "figure"
    }
  ]
}
```

## ▶ `examine("Remnant Soul of Saint Caliadis")`

```json
{
  "id": "a6",
  "name": "Remnant Soul of Saint Caliadis",
  "type": "soul remnant",
  "description": "The lingering soul of one who would not wholly pass.\n\nAt the urging of Belwyn, the saint Caliadis of the Long Vigil was given to the Pale Root in the rite of restoration. For a generation, the waning slowed. What became of it after is not written.",
  "how_it_lies": "Kept in a reliquary at Kaemisvault, before which the candles will not stay lit.",
  "leads": [
    {
      "name": "Belwyn",
      "kind": "figure"
    },
    {
      "name": "Caliadis",
      "kind": "figure"
    }
  ]
}
```

## ▶ `travel("Karaeosvault")`

```json
{
  "arrived": "Karaeosvault",
  "steps_left": 4,
  "place": "Karaeosvault",
  "relics_here": [],
  "ways_onward": [
    "the Pilgrim Roads"
  ],
  "hint": "examine(name) to study a relic here; a relic's resting place is itself a clue."
}
```

## ▶ `travel("Toromundmarch")`

```json
{
  "arrived": "Toromundmarch",
  "steps_left": 3,
  "place": "Toromundmarch",
  "relics_here": [
    {
      "id": "a1",
      "name": "Sap of Ghalenmund",
      "type": "catalyst",
      "how_it_lies": "Kept long at Toromundmarch, and then kept poorly.",
      "examined": false
    },
    {
      "id": "a9",
      "name": "Soul of Ghalenmund",
      "type": "soul remnant",
      "how_it_lies": "Taken from a throne room at Toromundmarch where nothing else was disturbed.",
      "examined": false
    }
  ],
  "ways_onward": [
    "the Pilgrim Roads"
  ],
  "hint": "examine(name) to study a relic here; a relic's resting place is itself a clue."
}
```

## ▶ `examine("Sap of Ghalenmund")`

```json
{
  "id": "a1",
  "name": "Sap of Ghalenmund",
  "type": "catalyst",
  "description": "A catalyst attuned to the old gift.\n\nThe Sap of Ghalenmund was wrought as regalia of Ghalenmund's throne. Perhaps it is better that the tale ends there.",
  "how_it_lies": "Kept long at Toromundmarch, and then kept poorly.",
  "leads": [
    {
      "name": "Ghalenmund",
      "kind": "figure"
    }
  ]
}
```

## ▶ `examine("Soul of Ghalenmund")`

```json
{
  "id": "a9",
  "name": "Soul of Ghalenmund",
  "type": "soul remnant",
  "description": "The lingering soul of one who would not wholly pass.\n\nGhalenmund, god of secrets, locks, and the spaces between, descended below the world to look upon the Pale Root directly, and did not return. Whether this was mercy or malice, none agree.",
  "how_it_lies": "Taken from a throne room at Toromundmarch where nothing else was disturbed.",
  "leads": [
    {
      "name": "Ghalenmund",
      "kind": "figure"
    }
  ]
}
```

## ▶ `travel("Ulirwyncradle")`

```json
{
  "arrived": "Ulirwyncradle",
  "steps_left": 2,
  "place": "Ulirwyncradle",
  "relics_here": [
    {
      "id": "a10",
      "name": "Eloric's Set",
      "type": "armor",
      "how_it_lies": "Left behind at Ulirwyncradle, and never reclaimed.",
      "examined": false
    },
    {
      "id": "a11",
      "name": "Ring of the Graft Vigil",
      "type": "ring",
      "how_it_lies": "Left behind at Ulirwyncradle, and never reclaimed.",
      "examined": false
    }
  ],
  "ways_onward": [
    "the Pilgrim Roads"
  ],
  "hint": "examine(name) to study a relic here; a relic's resting place is itself a clue."
}
```

## ▶ `examine("Eloric's Set")`

```json
{
  "id": "a10",
  "name": "Eloric's Set",
  "type": "armor",
  "description": "Worn armor that remembers the shape of its last bearer.\n\nEloric the Unmarked, last-sworn of the Order of the Graft, set out for the place where Ghalenmund was lost, carrying the order's final blessing. Perhaps it is better that the tale ends there.",
  "how_it_lies": "Left behind at Ulirwyncradle, and never reclaimed.",
  "leads": [
    {
      "name": "Ghalenmund",
      "kind": "figure"
    },
    {
      "name": "Eloric",
      "kind": "figure"
    },
    {
      "name": "Order of the Graft",
      "kind": "faction"
    }
  ]
}
```

## ▶ `examine("Ring of the Graft Vigil")`

```json
{
  "id": "a11",
  "name": "Ring of the Graft Vigil",
  "type": "ring",
  "description": "A ring that grants a small, stubborn blessing.\n\nEloric the Unmarked, last-sworn of the Order of the Graft, set out for the place where Ghalenmund was lost, carrying the order's final blessing. It is said that Eloric was last seen at the edge of the deep roads. The order keeps a vigil that has not ended. Held long enough, it suggests the waning is no accident. The name endures; little else does.",
  "how_it_lies": "Left behind at Ulirwyncradle, and never reclaimed.",
  "leads": [
    {
      "name": "Ghalenmund",
      "kind": "figure"
    },
    {
      "name": "Eloric",
      "kind": "figure"
    },
    {
      "name": "Order of the Graft",
      "kind": "faction"
    }
  ]
}
```

## ▶ `travel("Verenethreach")`

```json
{
  "arrived": "Verenethreach",
  "steps_left": 1,
  "place": "Verenethreach",
  "relics_here": [
    {
      "id": "a2",
      "name": "Ring of Thaliagrim",
      "type": "weapon",
      "how_it_lies": "Kept long at Verenethreach, and then kept poorly.",
      "examined": false
    }
  ],
  "ways_onward": [
    "the Pilgrim Roads"
  ],
  "hint": "examine(name) to study a relic here; a relic's resting place is itself a clue."
}
```

## ▶ `examine("Ring of Thaliagrim")`

```json
{
  "id": "a2",
  "name": "Ring of Thaliagrim",
  "type": "weapon",
  "description": "A weapon of an older make, still keen despite its years.\n\nThe Ring of Thaliagrim was wrought as regalia of Thaliagrim's throne. Perhaps it is better that the tale ends there.",
  "how_it_lies": "Kept long at Verenethreach, and then kept poorly.",
  "leads": [
    {
      "name": "Thaliagrim",
      "kind": "figure"
    }
  ]
}
```

## ▶ `travel("Olagarcradle")`

```json
{
  "arrived": "Olagarcradle",
  "steps_left": 0,
  "place": "Olagarcradle",
  "relics_here": [
    {
      "id": "a7",
      "name": "Hollow Crown of Olagarcradle",
      "type": "key item",
      "how_it_lies": "Found at the foot of a throne in Olagarcradle, beneath the dust of the banners.",
      "examined": false
    },
    {
      "id": "a8",
      "name": "Wrensila's Oathbreaker Blade",
      "type": "weapon",
      "how_it_lies": "Found at the foot of a throne in Olagarcradle, beneath the dust of the banners.",
      "examined": false
    }
  ],
  "ways_onward": [
    "the Pilgrim Roads"
  ],
  "hint": "examine(name) to study a relic here; a relic's resting place is itself a clue."
}
```

## ▶ `examine("Hollow Crown of Olagarcradle")`

```json
{
  "id": "a7",
  "name": "Hollow Crown of Olagarcradle",
  "type": "key item",
  "description": "An object of no use in battle, and of great consequence.\n\nWrensila the Quiet, sword-hand of Ostorthas, opened the gates of Galomerebarrow to the Order of the Graft over a grievance no chronicle agrees on. Some claim Olagarcradle fell. Ostorthas the Grey died at the foot of their own throne; the crown was carried away and never worn again. The name endures; little else does.",
  "how_it_lies": "Found at the foot of a throne in Olagarcradle, beneath the dust of the banners.",
  "leads": [
    {
      "name": "Ostorthas",
      "kind": "figure"
    },
    {
      "name": "Wrensila",
      "kind": "figure"
    },
    {
      "name": "Order of the Graft",
      "kind": "faction"
    },
    {
      "name": "Olagarcradle",
      "kind": "faction"
    },
    {
      "name": "Galomerebarrow",
      "kind": "place",
      "reachable": true
    }
  ]
}
```

## ▶ `examine("Wrensila's Oathbreaker Blade")`

```json
{
  "id": "a8",
  "name": "Wrensila's Oathbreaker Blade",
  "type": "weapon",
  "description": "A weapon of an older make, still keen despite its years.\n\nWrensila the Quiet, sword-hand of Ostorthas, opened the gates of Galomerebarrow to the Order of the Graft over a grievance no chronicle agrees on. Old verses hold that Olagarcradle fell. Ostorthas the Grey died at the foot of their own throne; the crown was carried away and never worn again. Those who keep it too long begin to doubt the sermons. What became of it after is not written.",
  "how_it_lies": "Found at the foot of a throne in Olagarcradle, beneath the dust of the banners.",
  "leads": [
    {
      "name": "Ostorthas",
      "kind": "figure"
    },
    {
      "name": "Wrensila",
      "kind": "figure"
    },
    {
      "name": "Order of the Graft",
      "kind": "faction"
    },
    {
      "name": "Olagarcradle",
      "kind": "faction"
    },
    {
      "name": "Galomerebarrow",
      "kind": "place",
      "reachable": true
    }
  ]
}
```

## ▶ `ask("Who was Ghalenmund?")`

```json
{
  "id": "frag:q1",
  "fragment": "Some claim Ghalenmund, god of secrets, locks, and the spaces between, claimed a portion of the gift and took a throne. Of Ghalenmund, the records otherwise keep their counsel.\n    \u2014 a marginal note, unsigned",
  "asks_left": 7
}
```

## ▶ `ask("Who was Belwyn?")`

```json
{
  "id": "frag:q2",
  "fragment": "Old verses hold that Belwyn the Unbowed was cast out of Church of Queliamund and founded the Cult of the Patient Below, teaching that the gods themselves caused the waning. Of Belwyn, the records otherwise keep their counsel.\n    \u2014 a marginal note, unsigned",
  "asks_left": 6
}
```

## ▶ `delve("Ghalenmund")`

```json
{
  "findings": [
    {
      "id": "frag:e26",
      "year": 19,
      "account": "An account survives from Belanien the Stray, a envoy, set down against instruction and hidden in a coffin lid."
    },
    {
      "id": "frag:e27",
      "year": 19,
      "account": "In the months after, pilgrims came in unusual numbers, and left in unusual silence."
    }
  ],
  "new_items": [],
  "new_ground": [
    "Athulrionbarrow"
  ],
  "delves_left": 4,
  "note": "New relics lie where the accounts place them \u2014 travel there to recover them."
}
```

## ▶ `travel("Athulrionbarrow")`
*new ground opened by the dig*

```json
{
  "error": "Your strength for the road is spent. (step budget exhausted \u2014 you may still study what you have found)"
}
```

## ▶ `delve("Belwyn")`

```json
{
  "findings": [
    {
      "id": "frag:e28",
      "year": 329,
      "account": "An account survives from Hesticael Long-memoried, a handmaid, set down against instruction and hidden in a ledger."
    },
    {
      "id": "frag:e29",
      "year": 329,
      "account": "In the months after, crows came in unusual numbers, and left in unusual silence."
    }
  ],
  "new_items": [
    {
      "id": "a13",
      "name": "Effects of Hesticael",
      "type": "ring",
      "lies_at": "Nycaelfen"
    }
  ],
  "new_ground": [
    "Nycaelfen"
  ],
  "delves_left": 3,
  "note": "New relics lie where the accounts place them \u2014 travel there to recover them."
}
```

## ▶ `travel("Nycaelfen")`
*new ground opened by the dig*

```json
{
  "error": "Your strength for the road is spent. (step budget exhausted \u2014 you may still study what you have found)"
}
```

## ▶ `theorize([... 5 claims ...])`
*purist mode — a fellow antiquary's reaction, never a verdict*

```json
{
  "reception": [
    {
      "claim": "The Graft of Queliamund was wrought as regalia of Queliamund's throne.",
      "reception": "The antiquary nods slowly. \"Aye. The stones I have read say the same.\""
    },
    {
      "claim": "At the urging of Belwyn, the saint Caliadis of the Long Vigil was given to the Pale Root in the rite of restoration.",
      "reception": "The antiquary nods slowly. \"Aye. The stones I have read say the same.\""
    },
    {
      "claim": "The Sap of Ghalenmund was wrought as regalia of Ghalenmund's throne.",
      "reception": "\"This much I will grant you \u2014 it agrees with what the old things remember.\""
    },
    {
      "claim": "The pruning-hooks of the church are not symbols; something is still cut from the Root each season, and burned unseen.",
      "reception": "The antiquary goes still, and will not meet your eye. \"Speak no further on this. Some doors are shut for cause.\""
    },
    {
      "claim": "The last knight became the god he went to find.",
      "reception": "\"On what? I have read no record that carries this. You reach past your evidence.\""
    }
  ],
  "closing": "The antiquary rises. \"Enough for tonight. You wander toward things better left buried.\"",
  "note": "This is one antiquary's reading, not a verdict. No one in this world will tell you that you are right."
}
```

## ▶ `progress()`

```json
{
  "explorer": "warden",
  "at": "Olagarcradle",
  "places_walked": "9/15",
  "relics_found": "10/13",
  "relics_examined": "10/13",
  "steps_left": 0,
  "asks_left": 6,
  "delves_left": 3,
  "theories_submitted": 1
}
```

## ▶ `compendium()`

# The Book of Found Things

*World seed-7 (root), as uncovered by the seeker "warden".*

> Of the Pale Root little now is spoken, and less is true. Gather what the old things still remember, and be sparing with belief.

*Places walked: 9 — relics examined: 10 — steps 8/8, asks 2/8, delves 2/5*

## Roads Walked

### Galomerebarrow

- (walked, nothing studied here)

### Ghalaecaelhollow

- **Graft of Queliamund** — *Kept long at Ghalaecaelhollow, and then kept poorly.*

### Kaemisvault

- **Sap of Saint Caliadis** — *Kept in a reliquary at Kaemisvault, before which the candles will not stay lit.*
- **Remnant Soul of Saint Caliadis** — *Kept in a reliquary at Kaemisvault, before which the candles will not stay lit.*

### Karaeosvault

- (walked, nothing studied here)

### Olagarcradle

- **Hollow Crown of Olagarcradle** — *Found at the foot of a throne in Olagarcradle, beneath the dust of the banners.*
- **Wrensila's Oathbreaker Blade** — *Found at the foot of a throne in Olagarcradle, beneath the dust of the banners.*

### Toromundmarch

- **Sap of Ghalenmund** — *Kept long at Toromundmarch, and then kept poorly.*
- **Soul of Ghalenmund** — *Taken from a throne room at Toromundmarch where nothing else was disturbed.*

### Ulirwyncradle

- **Eloric's Set** — *Left behind at Ulirwyncradle, and never reclaimed.*
- **Ring of the Graft Vigil** — *Left behind at Ulirwyncradle, and never reclaimed.*

### Verenethreach

- **Ring of Thaliagrim** — *Kept long at Verenethreach, and then kept poorly.*

### the Pilgrim Roads

- (walked, nothing studied here)

## Relics Examined

### Armors

**Eloric's Set**

Worn armor that remembers the shape of its last bearer.

Eloric the Unmarked, last-sworn of the Order of the Graft, set out for the place where Ghalenmund was lost, carrying the order's final blessing. Perhaps it is better that the tale ends there.

*Left behind at Ulirwyncradle, and never reclaimed.*

### Catalysts

**Sap of Ghalenmund**

A catalyst attuned to the old gift.

The Sap of Ghalenmund was wrought as regalia of Ghalenmund's throne. Perhaps it is better that the tale ends there.

*Kept long at Toromundmarch, and then kept poorly.*

**Graft of Queliamund**

A catalyst attuned to the old gift.

The Graft of Queliamund was wrought as regalia of Queliamund's throne. The name endures; little else does.

*Kept long at Ghalaecaelhollow, and then kept poorly.*

### Key Items

**Hollow Crown of Olagarcradle**

An object of no use in battle, and of great consequence.

Wrensila the Quiet, sword-hand of Ostorthas, opened the gates of Galomerebarrow to the Order of the Graft over a grievance no chronicle agrees on. Some claim Olagarcradle fell. Ostorthas the Grey died at the foot of their own throne; the crown was carried away and never worn again. The name endures; little else does.

*Found at the foot of a throne in Olagarcradle, beneath the dust of the banners.*

### Rings

**Ring of the Graft Vigil**

A ring that grants a small, stubborn blessing.

Eloric the Unmarked, last-sworn of the Order of the Graft, set out for the place where Ghalenmund was lost, carrying the order's final blessing. It is said that Eloric was last seen at the edge of the deep roads. The order keeps a vigil that has not ended. Held long enough, it suggests the waning is no accident. The name endures; little else does.

*Left behind at Ulirwyncradle, and never reclaimed.*

### Soul Remnants

**Remnant Soul of Saint Caliadis**

The lingering soul of one who would not wholly pass.

At the urging of Belwyn, the saint Caliadis of the Long Vigil was given to the Pale Root in the rite of restoration. For a generation, the waning slowed. What became of it after is not written.

*Kept in a reliquary at Kaemisvault, before which the candles will not stay lit.*

**Soul of Ghalenmund**

The lingering soul of one who would not wholly pass.

Ghalenmund, god of secrets, locks, and the spaces between, descended below the world to look upon the Pale Root directly, and did not return. Whether this was mercy or malice, none agree.

*Taken from a throne room at Toromundmarch where nothing else was disturbed.*

### Talismans

**Sap of Saint Caliadis**

A talisman for the invoking of half-forgotten rites.

At the urging of Belwyn, the saint Caliadis of the Long Vigil was given to the Pale Root in the rite of restoration. For a generation, the waning slowed. It is said that the rite did not restore anything. It only fed the waning more slowly — and Belwyn suspected as much. Whether this was mercy or malice, none agree.

*Kept in a reliquary at Kaemisvault, before which the candles will not stay lit.*

### Weapons

**Ring of Thaliagrim**

A weapon of an older make, still keen despite its years.

The Ring of Thaliagrim was wrought as regalia of Thaliagrim's throne. Perhaps it is better that the tale ends there.

*Kept long at Verenethreach, and then kept poorly.*

**Wrensila's Oathbreaker Blade**

A weapon of an older make, still keen despite its years.

Wrensila the Quiet, sword-hand of Ostorthas, opened the gates of Galomerebarrow to the Order of the Graft over a grievance no chronicle agrees on. Old verses hold that Olagarcradle fell. Ostorthas the Grey died at the foot of their own throne; the crown was carried away and never worn again. Those who keep it too long begin to doubt the sermons. What became of it after is not written.

*Found at the foot of a throne in Olagarcradle, beneath the dust of the banners.*

## Accounts Unearthed

### On the trail of Ghalenmund

- *(year 19, testimony)* An account survives from Belanien the Stray, a envoy, set down against instruction and hidden in a coffin lid.
- *(year 19, aftermath)* In the months after, pilgrims came in unusual numbers, and left in unusual silence.

### On the trail of Belwyn

- *(year 329, testimony)* An account survives from Hesticael Long-memoried, a handmaid, set down against instruction and hidden in a ledger.
- *(year 329, aftermath)* In the months after, crows came in unusual numbers, and left in unusual silence.
- **Brought back:** Effects of Hesticael (ring)

## Words of the Archives

**Who was Ghalenmund, and what became of them?**

> Some claim Ghalenmund, god of secrets, locks, and the spaces between, claimed a portion of the gift and took a throne. Of Ghalenmund, the records otherwise keep their counsel.
>     — a marginal note, unsigned

**Who was Belwyn, and what became of them?**

> Old verses hold that Belwyn the Unbowed was cast out of Church of Queliamund and founded the Cult of the Patient Below, teaching that the gods themselves caused the waning. Of Belwyn, the records otherwise keep their counsel.
>     — a marginal note, unsigned

## Theories Ventured

### Theory 1

- The Graft of Queliamund was wrought as regalia of Queliamund's throne.
- At the urging of Belwyn, the saint Caliadis of the Long Vigil was given to the Pale Root in the rite of restoration.
- The Sap of Ghalenmund was wrought as regalia of Ghalenmund's throne.
- The pruning-hooks of the church are not symbols; something is still cut from the Root each season, and burned unseen.
- The last knight became the god he went to find.

## Beyond the Charted Roads

3 relics remain somewhere unwalked, their names not yet even known to you.

Strength remaining: 0 steps, 3 delves, 6 asks. The rest of the world keeps its counsel.


---

## Epilogue — the truth (SPOILERS)

Checked against `chronicle.md` and the veils:

- **The mortal age, largely recovered.** The seeker found the fallen god (his soul *"taken from a throne room where nothing else was disturbed"* — a departure, not a death), the rite that fed a saint to the Root while its own priest *"suspected as much,"* and — by following the one cross-link into the fallen kingdom — the betrayal itself.
- **The veil, answered only by silence.** The fourth claim is **veil 1 of 3** verbatim. In purist mode the antiquary did not confirm it; they went quiet and told the seeker to speak no further. That refusal is the only signal of hidden truth a seeker gets, and it is deniable. Veils 2 and 3 were never approached — correct for a first pilgrimage.
- **The overreach, correctly doubted** — *"the last knight became the god he went to find"* drew *"you reach past your evidence"*, a doubt rather than a verdict.
