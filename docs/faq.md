# FAQ

**Do I need to open a port or set up a webhook?**
No. The bot uses long polling, so it only makes outbound connections.

**Can I use my own Mealie user?**
Yes, but a dedicated user is better: everything the bot adds shows up in Mealie
under that user, and you can revoke its token without touching your own.

**Does Mealie have to run in the same Compose stack?**
No. Set `MEALIE_URL` to any URL the bot can reach, for example
`https://mealie.example.com` behind a reverse proxy. The TLS certificate is
verified; self-signed certificates are not supported. The API token travels in
every request, so use HTTPS for anything outside a private network.

**The container exits with "Permission denied" on the secret file.**
The bot runs as UID 10001 and the secret files are mounted with their host
permissions. Make them readable for that user: `chmod 644 secrets/*`.

**Why does the bot ignore me?**
Your Telegram user ID is not in `ALLOWED_USER_IDS`. The log shows the ID at
`WARNING` level, once per unknown sender.

**Private chats or a group?**
Both work. With a private chat per person, each person has their own list
message and history; a change made by one person quietly updates the other's
list message, and their history names who did it. A group with both people and
the bot gives one shared list message and one history with names.

**Why does the bot not react to plain text in a group?**
Telegram's privacy mode only delivers commands to bots in groups. Turn it off
for the bot in @BotFather (`/setprivacy`), then remove and re-add the bot to
the group. To delete handled messages there (`DELETE_COMMANDS`,
`DELETE_ITEM_MESSAGES`), make the bot a group administrator that may delete
messages.

**Can I add the bot to a group?**
Only if everyone in the group may see the list: the list message, the history
and the first names of the people who changed it are visible to all members,
even to those who are not in `ALLOWED_USER_IDS` (their own messages are
ignored). Private chats are the intended setup.

**The bot stops with "Cannot read TELEGRAM_BOT_TOKEN_FILE: Permission denied".**
The secret files must be readable by user ID 10001, which the container runs
as. See *Secret files* in [configuration.md](configuration.md).

**Which list is used?**
The one picked with `/lists`, otherwise `SHOPPING_LIST`, otherwise the first
list by name. The choice made with `/lists` resets when the bot restarts.

**Does the bot create foods, units or lists in Mealie?**
When adding items: only with `SHOPPING_CREATE_FOODS=true`, which creates a food
without a category for each unknown name (*Undo* deletes it again). By default
unknown foods are stored as a note on the item; an unknown unit goes into the
note while the food (and its category) is still matched; lists must exist in
Mealie. A food created in Mealie is picked up within a minute. Sorting a
product into a category (`Ketchup → Condiments` or the *Sort* button) does
create the food, and `/category`, the question after an unknown category or
*New category…* in the picker creates a label. The bot never creates units or
lists.

**Everything lands in "Other". How do I get categories?**
Categories are Mealie labels on foods. Send `Ketchup → Condiments` (or `->`,
`>`; several products with commas) and the product keeps that category for
good. To sort many at once, open *Other* and tap *🏷️ Sort (n)*: the list
message asks about one item after the other, one tap each. `/categories`
shows what exists and how many products have no category.

**My own categories show only a coloured circle or 📦.**
The emoji comes from a built-in keyword table (German and English), from
`LABEL_EMOJI`, or from an emoji at the start of the label name in Mealie.
Without a match the label's colour from Mealie stands in as a circle
(`🟢 Eigenes`); give the label a colour in Mealie and the circle appears.
Only a label with neither colour nor emoji gets 📦. `LABEL_ICONS` switches circles
or emojis off (see [configuration.md](configuration.md)).

**Changes made in Mealie do not show up in Telegram.**
Tap *Refresh* (or any button) or send `/list` again. Changes made through the
bot by the other person do show up: their change re-renders your list message
in place. There are no push notifications in version 1.

**Where did my `/list` message go?**
The bot deletes `/list`, `/lists`, `/clear`, `/category` and `/categories`
right away so that only the list stays in the chat (`/start` and `/help` stay). Set `DELETE_COMMANDS=false`
to keep them.

**I cleared the chat history and the list is gone.**
Send `/list`. Every command posts the list as a new message, so it comes back
even if Telegram kept the old message on the bot's side only. The history
that was in the chat is gone with the cleared messages.

**Where did the items I typed go?**
As soon as the items are in Mealie, the bot deletes your message and sends the
list again below; the old list message becomes the history entry that records
who added what. Messages that failed stay so you can fix and resend
them. Set `DELETE_ITEM_MESSAGES=false` to keep all of them.

**The times in the list are off.**
Set the container's time zone with `TZ`, for example `TZ=Europe/Berlin`.

**What are the small "📜" messages above the list?**
History entries. When the list moves to the bottom of the chat, the old list
message is rewritten into a summary of who added, ticked off or removed what.
Changes within 15 minutes share one entry. After a day (`HISTORY_FOLD_HOURS`)
an entry is folded into one *Earlier changes* message, so the chat holds that
message, the recent entries and the list. You may delete the history message;
the bot starts a new one. Entries from before a restart of the bot stay, and
after a restart the bot starts a new *Earlier changes* message.

**Can I add recipes or a meal plan?**
Not yet. Version 1 is the shopping list only; the module structure leaves room
for more.

**How do I update?**
Change the image tag (and digest) in your Compose file and run
`docker compose up -d mealie-telegram-bot`. Releases are listed in
[CHANGELOG.md](../CHANGELOG.md). Send `/version` afterwards to see which
release and commit is running.
