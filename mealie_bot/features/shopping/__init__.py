"""Shopping list feature."""

from mealie_bot.features import Feature
from mealie_bot.features.shopping.handlers import build_router

FEATURE = Feature(
    name="shopping",
    commands=("list", "clear", "lists"),
    help_key="help",
    build_router=build_router,
)
