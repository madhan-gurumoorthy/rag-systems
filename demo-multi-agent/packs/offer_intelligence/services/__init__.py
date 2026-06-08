"""Upstream service clients for the OL Triage pack.

Each module is a thin async client over one Walmart upstream API:
OL API, IQS/SIV, Uber Mappings, Uber Keys, Offer RT, Product Store
Read, Item Pricing Setup, Merloc (Rampart), Oasis Inventory, HAT Path.
Endpoint URLs and consumer IDs come from environment variables with
production defaults baked in.
"""
