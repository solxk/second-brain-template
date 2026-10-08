# Board styles

How the task board looks. The board itself (`Scripts/tasks_board.html`) holds the structure and behaviour; a style only changes the look.

- `styles.json` lists the styles. Each has a `label` and a `blurb` (shown on the /styles picker), a Google Fonts `fonts` link, and options that switch parts of the page on:
  - `gauge`: `"ticks"` or `"arc"` for the "done today" ring;
  - `week`: the week strip above Today;
  - `side`: the Reminders, Decisions and Board summary cards;
  - `numbered`: numbers on the rows;
  - `arc`: four colours for the arc's gradient.
- `<name>.css` is the style. It redefines the colour, font, radius and border tokens at the top of `tasks_board.html`, then lays out the parts inside `@media (min-width: 761px)`. Below that width every style uses the shared single-column phone layout.
- `previews/` holds the README screenshots.

vault.json's `board_style` picks the style. `python3 Scripts/tasks_board.py style` lists them and `style <name>` switches. `/?style=<name>` on the running board previews one without switching, and `/styles` shows them all side by side with the owner's own tasks.

The page's parts, for laying out a style: `.top` (brand, `#tabs`, `.stamp`, `.motto`), `.banner`, `.hero` (`.dateline`, `#greet`, `.summary`, `.stats`), `.capture`, `.gaugecard`, `.listcard` (`.viewhead`, `.week`, `main`), and `.side` (`.side-reminders`, `.side-decisions`, `.side-folders`). Rows carry `w-late` or `w-soon` when their date is overdue or today.
