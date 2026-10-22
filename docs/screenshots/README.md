# Screenshots

The README shows three views of the bot. Put a real screenshot of each one in
this directory; until it exists, the README uses the SVG mockup of the same
name from `docs/images/`.

| File | What it shows | How to get there |
|---|---|---|
| `list-collapsed.png` | The live list: progress bar, collapsed categories, the *Done* quote and the *Refresh* / *Done* / *Remove* buttons | send `/list` |
| `list-expanded.png` | One category opened, items as buttons, short names sharing a row | tap `🥛 Dairy` |
| `add-items.png` | Your message `500 g flour, baking powder, 3 lemons` with the list right below it: the *Added* quote, the added categories opened and the *Undo* button | send that message |

Optional dark variants are named `<name>-dark.png`.

## Test data

Create a shopping list **Groceries** in Mealie with English labels and foods
(delete them afterwards if your instance is not in English):

* Labels: `Dairy`, `Baking`, `Fruit & vegetables`
* Open items: `milk` 2 l, `eggs` 6, `yoghurt` (Dairy); `bread` (no food, so it
  lands in *Other*)
* Ticked off: `butter`, `tomatoes` 2 cans, `bananas`
* Foods without items yet: `flour` (Baking), `baking powder` (Baking), `lemons`
  (Fruit & vegetables); the third screenshot adds them

Nothing else: no real products you buy, no other lists in the picture.

## Taking the pictures

1. Run the bot in English against your Mealie, with the time zone set so the
   "as of" time looks sane (see [Running locally](../development.md#running-locally)):

   ```fish
   set -x BOT_LANGUAGE en
   set -x TZ Europe/Berlin
   python -m mealie_bot
   ```

2. Use Telegram Desktop with the default light theme at 100 % zoom. Make the
   window narrow so the chat column is about 500 px wide; the buttons then
   wrap like on a phone.
3. Send `/start` once, then follow the table above in order. Before the third
   screenshot the three foods must not be on the list yet (tap *Undo* if you
   retake it).
4. Capture only the message bubbles (`Win`+`Shift`+`S` on Windows): no chat
   header with the bot's name, no history entry (it carries your Telegram
   first name), no system bar. Your own messages show no name in a private
   chat, so they are fine.
5. Save as PNG, about 600 to 900 px wide, at most 400 kB each (run the file
   through `oxipng` or `pngquant` if it is bigger). `pytest tests/test_readme.py`
   checks name, format and size.
6. Replace `docs/images/<name>.svg` with `docs/screenshots/<name>.png` in the
   README table and delete the mockup; the test fails if the README still
   points at a mockup whose screenshot exists.

Check the pictures before committing: no real names, user names, IDs,
hostnames or list names other than *Groceries*.
