class PricingEngine:
    def __init__(self, pricing_rules):
        self.pricing_rules = pricing_rules

    def calculate_price(self, base_price, adjustments):
        final_price = base_price
        for adjustment in adjustments:
            final_price += self.apply_adjustment(final_price, adjustment)
        return final_price

    def apply_adjustment(self, price, adjustment):
        adjustment_type = adjustment.get('type')
        amount = adjustment.get('amount', 0)

        if adjustment_type == 'percentage':
            return price * (amount / 100)
        elif adjustment_type == 'fixed':
            return amount
        return 0

    def generate_quote(self, deal_details):
        base_price = deal_details.get('base_price', 0)
        adjustments = deal_details.get('adjustments', [])
        final_price = self.calculate_price(base_price, adjustments)

        quote = {
            'base_price': base_price,
            'adjustments': adjustments,
            'final_price': final_price
        }
        return quote

    def validate_pricing(self, final_price):
        if final_price < 0:
            raise ValueError("Final price cannot be negative.")
        return True

    def get_pricing_rules(self):
        return self.pricing_rules