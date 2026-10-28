# Kirana Ledger

Kirana Ledger is a frontend-only shop companion for inventory, sales, customers and Udhaar. It uses realistic sample data and browser-local state to demonstrate how a shopkeeper can manage everyday work by chatting with an assistant. No backend, account service, payment gateway or external AI service is required.

## Run locally

```sh
npm install
npm run dev
```

Create a production build with `npm run build`, or preview one with `npm run preview`.

## Frontend features

- Responsive desktop sidebar and mobile bottom navigation.
- Dashboard with sales, inventory, customer credit, recent activity and low-stock summaries.
- Chat-style assistant for recording sales, stock receipts, Udhaar and payments, and answering common shop questions.
- Searchable inventory and customer lists, product details and stock adjustments.
- Udhaar book, transaction filters, reports, low-stock alerts and editable shop settings.
- Login and a three-step onboarding experience, using mock frontend-only behavior.
- Changes are saved to local storage in the current browser.

The UI is organized so data access can later be replaced with API-backed services without changing the route structure or core page layout.
