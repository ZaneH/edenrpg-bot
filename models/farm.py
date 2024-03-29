from datetime import datetime
import pdb
from typing import Any, Dict, Optional, Tuple

from bson import ObjectId
from pydantic import BaseModel, Field

from db.database import Database
from models.pyobjectid import PyObjectId
from models.shop import ShopModel
from models.yieldmodel import YieldModel
from utils.plant_state import can_harvest
from utils.yields import get_yield_with_odds

COLLECTION_NAME = "farms"


class BasePlotItemData(BaseModel):
    """
    Potential data for a plot item. This model is used to represent the
    data attached to each plot item in the user's farm.
    """
    yields_remaining: Optional[int] = None
    last_harvested_at: Optional[datetime] = None
    yields: Dict[str, YieldModel] = {}
    death_yields: Optional[Dict[str, YieldModel]] = {}
    grow_time_hr: Optional[float] = None

    class Config:
        arbitrary_types_allowed = True
        from_attributes = True


class FarmPlotItem(BaseModel):
    """
    Represents a single plot item in the user's farm. This model contains
    info about what is currently planted in a plot space.

    `key` is the identifier for what is currently planted in the plot.
    Typically prefixed with `<type>:` where `<type>` is the type of item.
    `data` is any additional information about the plot space.
    """

    key: str
    data: Optional[BasePlotItemData] = None

    class Config:
        arbitrary_types_allowed = True
        from_attributes = True


class FarmModel(BaseModel):
    """
    Represents a user's farm in the database. This model contains info about
    what is currently planted in the user's farm.
    """
    id: PyObjectId = Field(default_factory=PyObjectId, alias='_id')
    discord_id: str
    plot: Dict[str, FarmPlotItem]

    @classmethod
    async def find_by_discord_id(cls, discord_id):
        collection = Database.get_instance().get_collection(COLLECTION_NAME)
        doc = await collection.find_one({
            "discord_id": str(discord_id)
        })

        return cls(**doc) if doc else None

    def harvest(self) -> Tuple[Dict[str, YieldModel], int]:
        """
        Harvests the user's farm. This method will remove any dead plot items
        and return the yields and xp earned from the harvest.

        :return: A tuple containing the yields and xp earned from the harvest.
        """
        harvest_yield: Dict[str, YieldModel] = {}
        dead_plot_items = []
        xp_earned = 0

        for plot_id, plot_item in self.plot.items():
            if plot_item.data:
                is_ready = can_harvest(
                    plot_item.key,
                    plot_item.data.last_harvested_at,
                    plot_item.data.grow_time_hr
                )

                if is_ready:
                    for yield_item in plot_item.data.yields.values():
                        xp_earned += yield_item.xp

                    plot_item.data.yields_remaining -= 1
                    plot_item.data.last_harvested_at = datetime.utcnow()

                    yields: Dict[str, YieldModel] | Any = getattr(
                        plot_item.data, "yields", {})
                    for k, v in yields.items():
                        if k in harvest_yield:
                            harvest_yield[k].amount += get_yield_with_odds(v)
                        else:
                            amount = get_yield_with_odds(v)
                            if amount > 0:
                                harvest_yield[k] = YieldModel(amount=amount)

                # Mark plot item as dead if no yields remaining
                if plot_item.data.yields_remaining <= 0:
                    dead_plot_items.append(plot_id)

        # Remove dead plot items (no yields remaining)
        for plot_item in dead_plot_items:
            # Check for death_yields and add them to the harvest_yield
            if self.plot[plot_item].data.death_yields:
                for k, v in self.plot[plot_item].data.death_yields.items():
                    # Key has already been added, just increment the amount
                    if k in harvest_yield:
                        harvest_yield[k].amount += get_yield_with_odds(v)
                    else:
                        amount = get_yield_with_odds(v)
                        if amount > 0:
                            harvest_yield[k] = YieldModel(amount=amount)

            # Remove the plot item from the plot
            del self.plot[plot_item]

        print(harvest_yield)
        return (harvest_yield, xp_earned)

    def plant(self, location: str, item: ShopModel):
        # Check if the plot location is already taken
        if self.plot.get(location):
            return False

        # Confirm this is a seed
        if not item.key.startswith("seed:"):
            return False

        yields = item.yields
        death_yields = item.death_yields
        yields_remaining = item.total_yields
        grow_time_hr = item.grow_time_hr

        self.plot[location] = FarmPlotItem(
            # Replace the seed type with 'plant:' after planting
            key=item.key.replace("seed:", "plant:"),
            data=BasePlotItemData(
                yields_remaining=yields_remaining,
                last_harvested_at=datetime.utcnow(),
                yields=yields,
                death_yields=death_yields,
                grow_time_hr=grow_time_hr
            )
        )

        return True

    async def save_plot(self):
        collection = Database.get_instance().get_collection(COLLECTION_NAME)
        await collection.update_one(
            {"_id": self.id},
            {"$set": {"plot": {k: v.model_dump() for k, v in self.plot.items()}}},
            upsert=True
        )

    class Config:
        arbitrary_types_allowed = True
        from_attributes = True
        json_encoders = {
            ObjectId: str
        }
