import logging

from PIL import Image

from utils.plant_state import get_image_for_plot_item_state

GRID_SIZE = 32
PLOT_OFFSET = 29

logger = logging.getLogger(__name__)


def place_object(base, object_image, grid_x, grid_y):
    object = Image.open(object_image).convert("RGBA")
    w = object.width
    h = object.height
    x = grid_x * GRID_SIZE + PLOT_OFFSET - w // 2
    y = grid_y * GRID_SIZE + PLOT_OFFSET - h // 2

    additional_offset = {x: GRID_SIZE // 2, y: GRID_SIZE // 2}
    if h > GRID_SIZE:
        additional_offset[y] -= h // 4

    base.paste(object, (
        int(x + additional_offset[x]),
        int(y + additional_offset[y])
    ), object)

    return base


def generate_base_image():
    bl1 = Image.open("./images/files/base-1.png").convert("RGBA")
    bl2 = Image.open("./images/files/base-2.png").convert("RGBA")
    base = Image.new("RGBA", bl1.size)
    base.paste(bl1, (0, 0), bl1)
    base.paste(bl2, (0, 0), bl2)
    return base


def generate_image(plot_state):
    base_image = generate_base_image()

    # plot_state is a dict (A1, A2, B5, etc.)
    for plot_id, state in plot_state.items():
        col, row = plot_id[0], plot_id[1:]

        last_harvested_at = None
        grow_time_hr = None
        if state.data:
            last_harvested_at = state.data.last_harvested_at
            grow_time_hr = state.data.grow_time_hr

        try:
            item_image = get_image_for_plot_item_state(
                state.key,
                last_harvested_at,
                grow_time_hr
            )

            if item_image:
                base_image = place_object(
                    base_image,
                    f"./images/files/{item_image}",
                    ord(col) - 64,
                    int(row)
                )
        except Exception as e:
            logger.error(f"Error placing object for {plot_id}: {e}")

    return base_image
