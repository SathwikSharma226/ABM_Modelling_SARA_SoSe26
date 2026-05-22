# City Layouts

This folder holds **ASCII city maps** used by the simulation. Each character
represents one cell in the grid world.

## Legend

The legend must match the constants in [`../config.py`](../config.py).

| Symbol | Meaning |
|:------:|---------|
| `.`    | Street / walkable path |
| `#`    | Wall / building (blocks movement) |
| `P`    | Public area (walkable; waste accumulates more easily here) |
| `B`    | Dust bin (small fixed infrastructure) |
| `C`    | Dust container (large fixed infrastructure) |
| `D`    | Disposal point (transporter terminates waste here) |
| `A`    | Attractive point of interest (tourists gravitate here) |

## Files

| File | Description |
|------|-------------|
| [`default.txt`](default.txt) | A 30×30 sample city: a small downtown with a central plaza, surrounding building blocks, perimeter streets, bins along the main streets, two larger containers, and one disposal point at the edge. |

## Adding a New Layout

1. Create a new `.txt` file in this folder.
2. Use only the characters from the legend above. Lines may have different
   lengths — shorter lines are padded with `#` (buildings) at parse time.
3. Point [`../config.py`](../config.py) (`DEFAULT_LAYOUT_FILE`) at your new
   file, **or** pass the path to `WasteCityModel(layout_file=...)`.

> **Tip:** Make sure there is at least one `D` cell that is reachable from
> the bins, otherwise the transporter will not be able to dispose of waste.
