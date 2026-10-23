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
No. Unknown foods are stored as a note on the item; an unknown unit goes into
the note while the food (and its category) is still matched; lists must exist
in Mealie. A food created in Mealie is picked up within a minute.

**Changes made in Mealie do not show up in Telegram.**
Tap *Refresh* (or any button) or send `/list` again. Changes made through the
bot by the other person do show up: their change re-renders your list message
in place. There are no push notifications in version 1.

**Where did my `/list` message go?**
The bot deletes `/list`, `/lists` and `/clear` right away so that only the
list stays in the chat, and the list message is then updated in place
(`/start` and `/help` stay). Set `DELETE_COMMANDS=false` to keep them; the
list is then re-sent below them.

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
Changes within 15 minutes share one entry.

**Can I add recipes or a meal plan?**
Not yet. Version 1 is the shopping list only; the module structure leaves room
for more.

**How do I update?**
Change the image tag (and digest) in your Compose file and run
`docker compose up -d mealie-telegram-bot`. Releases are listed in
[CHANGELOG.md](../CHANGELOG.md).
