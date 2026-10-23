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

**Why does the bot ignore me?**
Your Telegram user ID is not in `ALLOWED_USER_IDS`. The log shows the ID at
`WARNING` level, once per unknown sender.

**Why does the bot not react to plain text in a group?**
Telegram's privacy mode only delivers commands to bots in groups. Use a private
chat per person; everyone still works on the same Mealie list.

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
No. Unknown foods are stored as a note on the item; unknown units are kept as
part of the note; lists must exist in Mealie.

**Changes made in Mealie do not show up in Telegram.**
Tap *Refresh* (or any button) or send `/list` again. There are no push
notifications in version 1.

**Where did my `/list` message go?**
The bot deletes `/list`, `/lists` and `/clear` after handling them so that only
the list stays in the chat (`/start` and `/help` stay). Set
`DELETE_COMMANDS=false` to keep them.

**Where did the items I typed go?**
Once the items are on the list, the bot deletes your message; the history entry
records who added what. Messages that failed stay so you can fix and resend
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
