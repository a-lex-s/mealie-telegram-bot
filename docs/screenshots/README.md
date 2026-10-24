# Screenshots

The README shows three views of the bot. This directory holds one screenshot
of each; to replace one, take it again as described below and keep the file
name.

| File | What it shows | How to get there |
|---|---|---|
| `list-collapsed.png` | The live list: progress bar, collapsed categories with their colour circles, the *Done* quote and the *Refresh* / *Done* buttons | send `/list` |
| `list-expanded.png` | Two categories opened, items as buttons, short names sharing a row, and the *Sort* button under *Other* | tap `🔵 🥛 Dairy` and `📦 Other` |
| `add-items.png` | The end of your message `500 g flour, baking powder, 3 lemons` with the list right below it: the *Added* quote, the added categories opened and the *Undo* button | send that message |

Optional dark variants are named `<name>-dark.png`.

## Test data

Create a shopping list **Groceries** in Mealie with English labels and foods
(delete them afterwards if your instance is not in English):

* Labels with colours, so the buttons show their circles: `Dairy` (`#5bc0de`,
  🔵), `Baking` (`#e8b84a`, 🟠), `Fruit & vegetables` (`#5cb85c`, 🟢)
* Units `l`, `g` and `can`, so `500 g flour` is read with its unit (the bot
  does not create units yet)
* Foods with a singular name and a plural name (the buttons show the
  singular): `milk`, `egg`/`eggs`, `yoghurt`, `butter` (Dairy), `tomato`/`tomatoes`,
  `banana`/`bananas`, `lemon`/`lemons` (Fruit & vegetables), `flour`,
  `baking powder` (Baking)
* Open items: `milk` 2 l, `egg` 6, `yoghurt` (Dairy); `bread` (no food, so it
  lands in *Other*)
* Ticked off: `butter`, `tomato` 2 cans, `banana`
* Foods without items yet: `flour`, `baking powder` and `lemon`; the third
  screenshot adds them

Nothing else: no real products you buy, no other lists in the picture.

## Taking the pictures

1. Run the bot in English against your Mealie, with the time zone set so the
   "as of" time looks sane (see [Running locally](../development.md#running-locally)):

   ```fish
   set -x BOT_LANGUAGE en
   set -x TZ Europe/Berlin
   python -m mealie_bot
   ```

2. Use a Telegram client with the default light theme at phone width (about
   370 px or more); on Telegram Desktop make the window narrow so the buttons
   wrap like on a phone.
3. Send `/start` once, then follow the table above in order. Before the third
   screenshot the three foods must not be on the list yet (tap *Undo* if you
   retake it).
4. Capture the chat area (`Win`+`Shift`+`S` on Windows): no history entry
   (it carries your Telegram first name), no system bar. The chat header is
   fine as long as the bot has a generic name such as "Mealie Bot". Your own
   messages show no name in a private chat.
5. Round the corners slightly (radius about 18 px) with a transparent
   outside, save as PNG, at most 400 kB each (run the file through `oxipng`
   or `pngquant` if it is bigger). `pytest tests/test_readme.py` checks name,
   format and size.

Check the pictures before committing: no real names, user names, IDs,
hostnames or list names other than *Groceries*.
