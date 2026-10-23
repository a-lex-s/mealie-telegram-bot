"""Shopping list feature."""

from mealie_bot.features import Feature
from mealie_bot.features.shopping.handlers import build_router

FEATURE = Feature(
    name="shopping",
    commands=("list", "clear", "lists"),
    start_key="start.shopping",
    help_key="help.shopping",
    build_router=build_router,
)
