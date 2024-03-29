from datetime import datetime
import discord
from db.shop_data import ShopData

from models.user import UserModel
from utils.challenges import is_challenge_completed
from utils.embeds import create_embed_for_challenges
from utils.emoji_map import EMOJI_MAP


class ChallengesView(discord.ui.View):
    """
    A view that allows a user to view their challenge, refresh their challenges,
    select a challenge, accept a challenge, view their progress, and claim rewards.
    Triggered with /challenges
    """
    async def on_timeout(self) -> None:
        self.clear_items()
        await self.message.edit(
            view=None
        )

    def create_challenge_option_select(self):
        selection_options = []
        for i, option in enumerate(self.challenges.options):
            selection_options.append(discord.SelectOption(
                label=option.description,
                value=str(i)
            ))

        select = discord.ui.Select(
            placeholder="Select a challenge",
            row=0,
            options=selection_options
        )

        select.callback = self.on_challenge_option_selected
        return select

    def __init__(self, profile: UserModel, timeout=120):
        super().__init__(timeout=timeout)

        self.profile = profile
        self.challenges = profile.challenges

        self.selected_option = None
        self.challenge_option_select = self.create_challenge_option_select()
        if len(self.challenges.options) > 0:
            self.add_item(self.challenge_option_select)

        self.accept_button = discord.ui.Button(
            style=discord.ButtonStyle.primary,
            label="Accept",
            row=4,
        )

        self.claim_button = discord.ui.Button(
            style=discord.ButtonStyle.success,
            label="Claim",
            row=4,
        )

        self.refresh_button = discord.ui.Button(
            style=discord.ButtonStyle.danger,
            label="Refresh",
            row=4,
        )

        self.accept_button.callback = self.on_accept_button_clicked
        self.claim_button.callback = self.on_claim_button_clicked
        self.refresh_button.callback = self.on_refresh_button_clicked

        can_refresh = (datetime.utcnow(
        ) - self.profile.challenges.last_refreshed_at).total_seconds() > 86400
        if can_refresh:
            self.add_item(self.refresh_button)

    async def on_challenge_option_selected(self, interaction: discord.Interaction):
        self.remove_item(self.refresh_button)
        self.remove_item(self.accept_button)
        self.remove_item(self.claim_button)

        self.selected_option = int(interaction.data["values"][0])

        is_accepted = self.challenges.options[self.selected_option].accepted
        self.accept_button.disabled = is_accepted
        self.add_item(self.accept_button)

        # Check if the challenge is completed
        is_completed = is_challenge_completed(
            self.challenges.options[self.selected_option])

        self.claim_button.disabled = not is_completed
        self.add_item(self.claim_button)

        # set default=True for the selected option
        for option in self.challenge_option_select.options:
            option.default = option.value == interaction.data["values"][0]

        await interaction.message.edit(view=self)
        await interaction.response.defer()

    async def on_accept_button_clicked(self, interaction: discord.Interaction):
        try:
            active_challenges = sum(
                option.accepted for option in self.challenges.options
            )
            max_active = self.challenges.max_active

            if active_challenges >= max_active:
                raise ValueError(
                    "You have reached the maximum amount of active challenges.")

            new_user = await UserModel.accept_challenge(
                self.profile.discord_id,
                self.selected_option,
            )

            if new_user:
                self.profile = new_user
                self.challenges = new_user.challenges
                self.clear_items()

                if len(self.challenges.options) > 0:
                    self.add_item(self.challenge_option_select)
            else:
                raise ValueError(
                    "There must have been an issue accepting the challenge.\nPlease try again or report this in the Discord.")

            await interaction.message.edit(
                embed=create_embed_for_challenges(
                    interaction.user.display_name, self.challenges
                ),
                view=self
            )

            await interaction.response.defer()
        except Exception as e:
            await interaction.message.edit(
                content=str(e),
                view=self
            )

            await interaction.response.defer()

    async def on_claim_button_clicked(self, interaction: discord.Interaction):
        try:
            (new_user, rewards) = await self.profile.claim_challenge_rewards(
                self.selected_option
            )

            if new_user:
                self.profile = new_user
                self.challenges = new_user.challenges

            self.clear_items()
            if len(self.challenges.options) > 0:
                self.challenge_option_select = self.create_challenge_option_select()
                self.add_item(self.challenge_option_select)

            all_shop = ShopData.all()
            rewards_text = "You have claimed:\n"
            if rewards:
                for reward_key, yields in rewards.items():
                    item_name = next(
                        (item.name for item in all_shop if item.key ==
                         reward_key), reward_key
                    )

                    rewards_text += f"{EMOJI_MAP.get(reward_key, '')} {yields.amount} {item_name}\n"

            await interaction.message.edit(
                content=rewards_text,
                embed=create_embed_for_challenges(
                    interaction.user.display_name,
                    self.challenges
                ),
                view=self
            )

            await interaction.response.defer()
        except Exception as e:
            await interaction.message.edit(
                content=str(e),
                view=self
            )

            await interaction.response.defer()

    async def on_refresh_button_clicked(self, interaction: discord.Interaction):
        try:
            new_user = await UserModel.refresh_challenges(
                self.profile.discord_id,
                self.profile.stats.get("xp", 0),
                self.profile.challenges.last_refreshed_at,
                self.profile.challenges.max_active
            )

            self.profile = new_user
            self.challenges = new_user.challenges

            self.clear_items()
            if len(self.challenges.options) > 0:
                self.challenge_option_select = self.create_challenge_option_select()
                self.add_item(self.challenge_option_select)

            await interaction.message.edit(
                embed=create_embed_for_challenges(
                    interaction.user.display_name, self.challenges),
                view=self
            )

            await interaction.response.defer()
        except Exception as e:
            await interaction.message.edit(
                content=str(e),
                view=self
            )

            await interaction.response.defer()
