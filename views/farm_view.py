import discord
from discord.ui.item import Item

from db.shop_data import ShopData
from images.render import render_farm
from models.farm import FarmModel
from models.user import UserModel
from utils.emoji_map import EMOJI_MAP


class FarmView(discord.ui.View):
    """
    A view that allows a user to view their farm, plant a crop, harvest a crop,
    and upgrade their farm. More features will be added in the future.
    Triggered with /farm
    """
    async def on_timeout(self):
        self.clear_items()
        await self.message.edit(
            content="",
            view=None
        )

    def __init__(self, farm: FarmModel, farm_owner: discord.User, timeout=120):
        super().__init__(timeout=timeout)

        self.farm = farm
        self.discord_user = farm_owner

        self.seed_select = None
        self.plant_button = discord.ui.Button(
            label="Plant", style=discord.ButtonStyle.primary, row=0, emoji=EMOJI_MAP["emote:potted"]
        )
        self.harvest_button = discord.ui.Button(
            label="Harvest", style=discord.ButtonStyle.green, row=0, emoji=EMOJI_MAP["tool:harvest"]
        )
        self.upgrade_button = discord.ui.Button(
            label="Upgrade", style=discord.ButtonStyle.secondary, row=0, emoji=EMOJI_MAP["ui:upgrade"]
        )
        self.back_button: Item = None

        self.plant_button.callback = self.on_plant_clicked
        self.harvest_button.callback = self.on_harvest_clicked
        self.upgrade_button.callback = self.on_upgrade_clicked
        # -- Plant select variables
        self.selected_plant = None
        self.selected_letter = None
        self.selected_number = None
        self.add_item(self.plant_button)
        self.add_item(self.harvest_button)
        self.add_item(self.upgrade_button)

        self.letter_dropdown = None
        self.numer_dropdown = None

    def remove_stage_one_buttons(self):
        self.remove_item(self.plant_button)
        self.remove_item(self.harvest_button)
        self.remove_item(self.upgrade_button)

    def add_stage_one_buttons(self):
        self.add_item(self.plant_button)
        self.add_item(self.harvest_button)
        self.add_item(self.upgrade_button)

    async def on_plant_clicked(self, interaction: discord.Interaction):
        self.remove_stage_one_buttons()
        self.remove_item(self.seed_select)

        self.back_button = self.create_back_button()
        self.add_item(self.back_button)

        self.shop_data = ShopData.buyable()
        seeds = [item for item in self.shop_data if "seed:" in item.key]

        self.seed_select = discord.ui.Select(
            placeholder="Choose a plant seed",
            row=1,
            options=[
                discord.SelectOption(
                    label=seed.name,
                    value=seed.key
                ) for seed in seeds
            ],
        )

        self.seed_select.callback = self.on_select_seed_callback

        self.add_item(self.seed_select)
        await interaction.response.edit_message(view=self)

    async def on_harvest_clicked(self, interaction: discord.Interaction):
        (harvest_yield, xp_earned) = self.farm.harvest()
        if not any(harvest_yield.values()):
            return await interaction.response.edit_message(
                content="You don't have anything to harvest!",
                view=self
            )

        await self.farm.save_plot()

        await UserModel.give_items(self.discord_user.id, harvest_yield, 0, stats={
            "xp": xp_earned,
            "harvest.xp": xp_earned,
            "harvest.count": 1,
            **{
                f"harvest.{item_key}": amount
                for item_key, amount in harvest_yield.items()
            }
        })

        await UserModel.increment_challenge_progress(
            self.discord_user.id, "harvest", "count")

        formatted_yield = ""
        for item, yields in harvest_yield.items():
            formatted_yield += f"{EMOJI_MAP[item]} {yields.amount}x\n"

        self.back_button = self.create_back_button()
        self.add_item(self.back_button)
        self.remove_stage_one_buttons()

        await interaction.response.edit_message(
            content=f"You harvested your farm and earned a total of +**{xp_earned} XP**!\n\n{formatted_yield}",
            embed=self.create_farm_embed(self.discord_user.display_name),
            files=[await render_farm(self.farm)],
            view=self
        )

    async def on_upgrade_clicked(self, interaction: discord.Interaction):
        await interaction.response.edit_message(
            content="This feature is not yet implemented.",
            view=self
        )

    async def on_select_seed_callback(self, interaction: discord.Interaction):
        self.selected_plant = next(
            plant for plant in self.shop_data if plant.key == interaction.data["values"][0])

        self.letter_dropdown = discord.ui.Select(
            placeholder="Choose a letter",
            row=1,
            options=[
                discord.SelectOption(
                    label=letter,
                    value=letter
                ) for letter in ["A", "B", "C", "D", "E", "F"]
            ],
        )
        self.letter_dropdown.callback = self.on_select_plot_letter

        self.numer_dropdown = discord.ui.Select(
            placeholder="Choose a number",
            row=2,
            options=[
                discord.SelectOption(
                    label=str(number),
                    value=str(number)
                ) for number in range(1, 7)
            ],
        )
        self.numer_dropdown.callback = self.on_select_plot_number

        self.remove_item(self.seed_select)
        self.add_item(self.letter_dropdown)
        self.add_item(self.numer_dropdown)

        await interaction.response.edit_message(content="Choose a letter and number to plant your crop.", view=self)

    async def check_if_plot_specified(self, interaction: discord.Interaction, nol="number"):
        if nol == "letter":
            self.selected_letter = interaction.data["values"][0]
        else:
            self.selected_number = interaction.data["values"][0]

        is_done = self.selected_letter and self.selected_number
        if is_done:
            self.remove_item(self.letter_dropdown)
            self.remove_item(self.numer_dropdown)

            location = f"{self.selected_letter}{self.selected_number}"
            if self.selected_plant and self.farm.plant(
                location,
                self.selected_plant
            ):
                await self.farm.save_plot()
                await UserModel.inc_stats(
                    self.farm.discord_id,
                    {
                        "xp": 10,  # TODO: Make this dynamic?
                        "plant.count": 1,
                        f"plant.{self.selected_plant.key}": 1,
                    }
                )

                self.selected_letter = None
                self.selected_number = None

                await UserModel.increment_challenge_progress(
                    self.farm.discord_id, "plant", self.selected_plant.key)

                await interaction.response.edit_message(
                    content=f"You planted {self.selected_plant.name} {EMOJI_MAP[self.selected_plant.key]} on {location}!",
                    files=[await render_farm(self.farm)],
                    view=self,
                    embed=self.create_farm_embed(
                        self.discord_user.display_name
                    ),
                )
        else:
            await interaction.response.defer()

    def create_farm_embed(self, farm_name):
        embed = discord.Embed(
            title=f"{farm_name}'s Farm",
            color=discord.Color.embed_background()
        )

        embed.set_image(url="attachment://farm.png")
        return embed

    async def on_select_plot_letter(self, interaction):
        for option in self.letter_dropdown.options:
            if option.value == interaction.data["values"][0]:
                option.default = True
            else:
                option.default = False

        await self.check_if_plot_specified(interaction, "letter")

    async def on_select_plot_number(self, interaction):
        for option in self.letter_dropdown.options:
            if option.value == interaction.data["values"][0]:
                option.default = True
            else:
                option.default = False

        await self.check_if_plot_specified(interaction, "number")

    def create_back_button(self):
        back_button = discord.ui.Button(
            label="Back", style=discord.ButtonStyle.secondary, row=4
        )
        back_button.callback = self.on_back_clicked
        return back_button

    async def on_back_clicked(self, interaction: discord.Interaction):
        self.remove_item(self.letter_dropdown)
        self.remove_item(self.numer_dropdown)
        self.remove_item(self.back_button)
        self.remove_item(self.seed_select)

        self.add_stage_one_buttons()

        await interaction.response.edit_message(
            content="",
            view=self
        )
