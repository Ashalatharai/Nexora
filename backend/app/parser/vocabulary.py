from app.models.inventory import ITEM_ALIASES

# Known grocery units mapped to their standard canonical representations
KNOWN_UNITS = {
    "packets": "pkt",
    "packet": "pkt",
    "pkts": "pkt",
    "pkt": "pkt",
    "bags": "bag",
    "bag": "bag",
    "bottles": "bottle",
    "bottle": "bottle",
    "bars": "bar",
    "bar": "bar",
    "kg": "kg",
    "kgs": "kg",
    "kilos": "kg",
    "kilo": "kg",
    "litres": "litre",
    "litre": "litre",
    "liters": "litre",
    "liter": "litre",
    "l": "litre",
    "pieces": "pcs",
    "piece": "pcs",
    "pcs": "pcs",
    "pc": "pcs",
    "boxes": "box",
    "box": "box",
    "cans": "can",
    "can": "can",
    "tins": "tin",
    "tin": "tin",
}

# Plural to singular normalization for grocery items
PLURAL_TO_SINGULAR = {
    "soaps": "soap",
    "biscuits": "biscuit",
    "shampoos": "shampoo",
    "chocolates": "chocolate",
    "chips": "chips",
    "eggs": "egg",
    "breads": "bread",
    "apples": "apple",
    "onions": "onion",
    "potatoes": "potato",
    "tomatoes": "tomato",
    "maggis": "maggi",
    "milks": "milk",
    "oils": "oil",
    "rices": "rice",
    "sugars": "sugar",
    "teas": "tea",
}

# Conversational noise words in Kirana shop chats
NOISE_WORDS = {
    "i", "we", "please", "kindly", "today", "now", "just", "bhai", "bhaiya",
    "were", "was", "the", "a", "an", "items", "item"
}

# Word numbers commonly spoken by shopkeepers
WORD_TO_NUMBER = {
    "one": 1.0,
    "two": 2.0,
    "three": 3.0,
    "four": 4.0,
    "five": 5.0,
    "six": 6.0,
    "seven": 7.0,
    "eight": 8.0,
    "nine": 9.0,
    "ten": 10.0,
    "eleven": 11.0,
    "twelve": 12.0,
    "fifteen": 15.0,
    "twenty": 20.0,
    "twenty-five": 25.0,
    "thirty": 30.0,
    "forty": 40.0,
    "fifty": 50.0,
    "hundred": 100.0,
    "dozen": 12.0,
    "half": 0.5,
}
