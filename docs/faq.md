# FAQ

**Do I need to open a port or set up a webhook?**
No. The bot uses long polling, so it only makes outbound connections.

**Can I use my own Mealie user?**
Yes, but a dedicated user is better: everything the bot adds shows up in Mealie
under that user, and you can revoke its token without touching your own.

**Why does the bot ignore me?**
Your Telegram user ID is not in `ALLOWED_USER_IDS`. The log shows the ID at
`WARNING` level.

**Why does the bot not react to plain text in a group?**
Telegram's privacy mode only delivers commands to bots in groups. Use a private
chat per person; everyone still works on the same Mealie list.

**Which list is used?**
The one picked with `/lists`, otherwise `SHOPPING_LIST`, otherwise the first
list by name. The choice made with `/lists` resets when the bot restarts.

**Does the bot create foods, units or lists in Mealie?**
No. Unknown foods are stored as a note on the item; unknown units are kept as
part of the note; lists must exist in Mealie.

**Changes made in Mealie do not show up in Telegram.**
Tap *Refresh* or send `/list` again. There are no push notifications in version 1.

**Can I add recipes or a meal plan?**
Not yet. Version 1 is the shopping list only; the module structure leaves room
for more.

**How do I update?**
Change the image tag (and digest) in your Compose file and run
`docker compose up -d mealie-telegram-bot`. Releases are listed in
[CHANGELOG.md](../CHANGELOG.md).
