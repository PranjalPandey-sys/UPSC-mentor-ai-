from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def home_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Ask a Doubt", callback_data="menu_doubt")],
        [InlineKeyboardButton("Submit Answer for Evaluation", callback_data="menu_evaluate")],
        [InlineKeyboardButton("Submit Essay", callback_data="menu_essay")],
        [InlineKeyboardButton("Ethics Case Study", callback_data="menu_ethics")],
        [InlineKeyboardButton("Current Affairs Summary", callback_data="menu_ca")],
        [InlineKeyboardButton("My Progress", callback_data="menu_progress")],
    ])


def back_home_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Home", callback_data="menu_home")],
    ])
