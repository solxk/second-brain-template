# Board styles

How the task board looks. The board itself (`Scripts/tasks_board.html`) holds the structure and behaviour; a style only changes the look.

- `styles.json` lists the styles. Each has a `label` and a `blurb` (shown on the /styles picker), a Google Fonts `fonts` link, and options that switch parts of the page on:
  - `gauge`: `"ticks"` or `"arc"` for the "done today" ring;
  - `week`: the week strip above Today;
  - `side`: the Reminders, Waiting on others and By project summary cards;
  - `numbered`: numbers on the rows;
  - `arc`: four colours for the arc's gradient;
  - `dark`: `true` when the style has a dark palette as well. The board then follows the computer's light or dark setting and shows an Auto · Light · Dark switch (`.themes`) in the top corner; a pick of Light or Dark is remembered in that browser only. Without it the switch stays hidden and the style is always light.
- `<name>.css` is the style. It redefines the colour, font, radius and border tokens at the top of `tasks_board.html`, then lays out the parts inside `@media (min-width: 761px)`. Below that width every style uses the shared single-column phone layout.
- A style with `dark` puts its dark colours in a `:root[data-theme="dark"]` block, which a small script sets before the page draws. Every colour has to be a token for that to work, so Show Your Working adds five of its own: `--edge` (the ink line round sheets and controls), `--hard` (their offset shadow), `--grid` (the paper's ruling), `--rail` (the list rail's background) and `--tick` (the ticked checkbox's mark, an SVG data URI, so its colour can change with the palette).
- `previews/` holds the README screenshots.

vault.json's `board_style` picks the style. `python3 Scripts/tasks_board.py style` lists them and `style <name>` switches. `/?style=<name>` on the running board previews one without switching, and `/styles` shows them all side by side with the owner's own tasks.

The page's parts, for laying out a style: `.top` (brand, `#tabs`, `.stamp`, `.motto`), `.banner`, `.hero` (`.dateline`, `#greet`, `.summary`, `.stats`), `.capture`, `.gaugecard`, `.listcard` (`.viewhead`, `.week`, `main`), `.side` (`.side-reminders`, `.side-waiting`, `.side-folders`), and `.themes`, the light/dark switch. Rows carry `w-late` or `w-soon` when their date is overdue or today. In By project, a folder narrower than 520px puts each row's date under its title, so titles keep their width.
