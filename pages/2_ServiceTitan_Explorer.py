import streamlit as st
from google.cloud import bigquery
import pandas as pd
from utils import get_client, render_sidebar

# --- CONFIG ---
PROJECT_ID = "the-brain-487614"
DATASET    = "servicetitan"

client = bigquery.Client(project=PROJECT_ID)
client = get_client() 
# --- PAGE SETUP ---
st.set_page_config(page_title="ServiceTitan Table Explorer", page_icon="🗄️", layout="wide")
st.title("🗄️ ServiceTitan Table Explorer")
st.markdown("Understand what data we have from the acquired company. Click any table to explore it.")

render_sidebar() 

# --- TABLE METADATA (plain English descriptions) ---
TABLE_INFO = {
    "customer": {
        "emoji": "👤",
        "category": "People",
        "simple": "Every customer — homeowners and businesses",
        "description": "40,000+ customers. Almost all residential homeowners in Massachusetts. Each customer has a unique ID that links to jobs, invoices, and memberships.",
        "key_columns": {
            "id": "Unique customer number (links to all other tables)",
            "name": "Customer name",
            "type": "Residential or Commercial",
            "active": "Is this customer still active?",
            "balance": "Amount they still owe the company",
            "created_on": "When they became a customer",
            "do_not_service": "Never send a technician to this person"
        },
        "links_to": ["location", "job", "invoice", "membership"]
    },
    "location": {
        "emoji": "🏠",
        "category": "People",
        "simple": "Physical addresses where work is done",
        "description": "One customer can have multiple locations (e.g. two houses). Each location has its own address. Jobs are done at locations, not customers directly.",
        "key_columns": {
            "id": "Unique address ID",
            "customer_id": "Which customer owns this address",
            "address_street/city/state/zip": "The actual address",
            "zone_id": "Which service zone",
            "active": "Still being serviced?"
        },
        "links_to": ["customer", "job", "membership"]
    },
    "job": {
        "emoji": "🔧",
        "category": "Operations",
        "simple": "Every piece of work ever scheduled — the central table",
        "description": "The most important table. Every install, repair, PM visit = one job. Everything connects to this. 22,756 jobs since 2019.",
        "key_columns": {
            "id": "Unique job number",
            "customer_id": "Which customer",
            "location_id": "Which address",
            "business_unit_id": "Which department (Generator Maintenance, Service, Install etc.)",
            "job_type_id": "What type of job",
            "campaign_id": "Which marketing campaign brought this customer",
            "job_status": "Completed, Cancelled, Scheduled",
            "no_charge": "Was this job free? (warranty/goodwill)",
            "summary": "Notes about the job written by office staff",
            "completed_on": "When it was finished"
        },
        "links_to": ["customer", "location", "business_unit", "job_type", "campaign", "appointment", "invoice", "timesheet"]
    },
    "appointment": {
        "emoji": "📅",
        "category": "Operations",
        "simple": "The scheduled date and time for a job visit",
        "description": "A job can have multiple appointments. Example: big install has one appointment to drop off the generator and another to wire it up.",
        "key_columns": {
            "id": "Unique appointment number",
            "job_id": "Which job",
            "customer_id": "Which customer",
            "start / ends": "When the appointment starts and ends",
            "arrival_window_start/end": "The window told to customer (e.g. 8am–10am)",
            "status": "Done, Scheduled, Cancelled"
        },
        "links_to": ["job", "appointment_assignment", "timesheet"]
    },
    "appointment_assignment": {
        "emoji": "👷",
        "category": "Operations",
        "simple": "Which technician is assigned to which appointment",
        "description": "Connects technicians to appointments. If 2 technicians go to one job, there are 2 rows here.",
        "key_columns": {
            "id": "Unique assignment",
            "appointment_id": "Which appointment",
            "job_id": "Which job",
            "technician_id": "Which technician",
            "technician_name": "Name (e.g. Kevin Mulligan)",
            "status": "Done, In Progress",
            "assigned_on": "When they were assigned"
        },
        "links_to": ["appointment", "job", "technician"]
    },
    "timesheet": {
        "emoji": "⏱️",
        "category": "Operations",
        "simple": "Records when a technician arrived and left each job",
        "description": "Tracks actual time on site. dispatched = left office, arrived = got to customer, done = finished. done_on is often null (not recorded!).",
        "key_columns": {
            "id": "Unique timesheet entry",
            "job_id": "Which job",
            "technician_id": "Which technician",
            "dispatched_on": "When they left to go to the job",
            "arrived_on": "When they got there",
            "done_on": "When they finished (often null!)",
            "canceled_on": "If the visit was cancelled"
        },
        "links_to": ["job", "appointment", "technician"]
    },
    "invoice": {
        "emoji": "🧾",
        "category": "Finance",
        "simple": "The bill sent to a customer after work is done",
        "description": "Where revenue lives. 26,500+ invoices. One job can have multiple invoices (deposit + final). invoice_type_name is NULL for installs — that is normal.",
        "key_columns": {
            "id": "Unique invoice number",
            "job_id": "Which job",
            "customer_id": "Which customer",
            "business_unit_id": "Which department",
            "total": "Amount charged to customer = REVENUE",
            "balance": "Amount still unpaid",
            "sales_tax": "Tax amount",
            "invoice_type_name": "PM Billing / Service / Warranty / COD / null for installs",
            "job_type": "Generator Install, PM, Repair etc.",
            "invoice_date": "When invoice was created"
        },
        "links_to": ["job", "customer", "business_unit", "invoice_item", "payment_applied_to"]
    },
    "invoice_item": {
        "emoji": "📋",
        "category": "Finance",
        "simple": "Each line item on an invoice — labor, parts, equipment",
        "description": "An invoice has multiple line items. This is where you can see the COST of each item. Critical for calculating gross profit.",
        "key_columns": {
            "id": "Unique line item",
            "invoice_id": "Which invoice",
            "type": "Equipment / Service / Material",
            "description": "What the item is",
            "price": "Price charged to customer",
            "cost": "What it cost the company — KEY for gross profit!",
            "quantity": "How many",
            "total": "quantity × price",
            "total_cost": "quantity × cost",
            "display_name": "Product name (e.g. 20KW Kohler RCA)"
        },
        "links_to": ["invoice"]
    },
    "payment": {
        "emoji": "💳",
        "category": "Finance",
        "simple": "Money actually received from customers",
        "description": "When a customer pays — check, credit card, ACH, financing (Greensky) — it goes here. Separate from invoice because payment often comes after.",
        "key_columns": {
            "id": "Unique payment",
            "customer_id": "Which customer paid",
            "total": "Amount paid",
            "type": "How they paid — Check, ACH, Credit Card, Online Payments, Greensky",
            "date": "When payment was received",
            "unapplied_amount": "Payment received but not yet matched to an invoice"
        },
        "links_to": ["customer", "payment_applied_to"]
    },
    "payment_applied_to": {
        "emoji": "🔗",
        "category": "Finance",
        "simple": "Links a payment to a specific invoice",
        "description": "Bridge between payments and invoices. One payment can be split across multiple invoices.",
        "key_columns": {
            "payment_id": "Which payment",
            "applied_to": "Which invoice the money goes to",
            "applied_amount": "How much of the payment goes to that invoice",
            "applied_on": "When it was applied"
        },
        "links_to": ["payment", "invoice"]
    },
    "estimate": {
        "emoji": "📝",
        "category": "Sales",
        "simple": "Price quotes given to customers before they decide to buy",
        "description": "Before a big install, the salesperson creates an estimate. Customer can Accept (Sold), Dismiss, or leave it Open. 28% close rate.",
        "key_columns": {
            "id": "Unique estimate",
            "customer_id": "Which customer",
            "job_id": "Which job it's attached to",
            "status_name": "Open / Sold / Dismissed",
            "subtotal": "Total price quoted",
            "summary": "Detailed description of what is included",
            "sold_on": "When customer agreed (null if not sold)",
            "sold_by": "Which salesperson sold it"
        },
        "links_to": ["customer", "job", "estimate_item"]
    },
    "estimate_item": {
        "emoji": "🔢",
        "category": "Sales",
        "simple": "Each line item inside a quote",
        "description": "Same structure as invoice_item but for estimates. Shows what labor and parts will be needed and at what cost.",
        "key_columns": {
            "estimate_id": "Which estimate",
            "description": "What the item is",
            "qty": "How many",
            "unit_rate": "Price per unit charged to customer",
            "unit_cost": "Cost to the company",
            "total": "Total revenue for this line",
            "total_cost": "Total cost for this line"
        },
        "links_to": ["estimate"]
    },
    "campaign": {
        "emoji": "📣",
        "category": "Marketing",
        "simple": "Marketing channels that bring in customers",
        "description": "How did the customer find the company? Google Ads, referral, trade show, Instagram etc. Every job is linked to a campaign.",
        "key_columns": {
            "id": "Unique campaign ID",
            "name": "Campaign name (e.g. Google Ads, Referral, Tradeshows)",
            "medium": "How the ad was delivered",
            "source": "Where it came from",
            "active": "Still running?"
        },
        "links_to": ["job", "call", "campaign_cost"]
    },
    "campaign_cost": {
        "emoji": "💰",
        "category": "Marketing",
        "simple": "How much was spent on each campaign each month",
        "description": "Tracks marketing spend for ROI calculation. Currently all daily_cost = 0 — the spend data has not been entered properly yet!",
        "key_columns": {
            "campaign_id": "Which campaign",
            "month / year": "Which month and year",
            "daily_cost": "Average daily spend — currently all $0, needs fixing!"
        },
        "links_to": ["campaign"]
    },
    "lead": {
        "emoji": "📞",
        "category": "Sales",
        "simple": "A potential customer who called or enquired",
        "description": "When someone calls in it creates a lead. Gets converted to a job or dismissed (wrong area, not interested, already have service etc.)",
        "key_columns": {
            "id": "Unique lead",
            "status": "Dismissed or converted to Job",
            "customer_id": "Which customer (null if new)",
            "call_id": "Which phone call created this lead",
            "campaign_id": "Which campaign brought them in",
            "business_unit_id": "Which department they enquired about",
            "call_reason_id": "Why they called"
        },
        "links_to": ["call", "campaign", "customer", "job"]
    },
    "call": {
        "emoji": "📱",
        "category": "Marketing",
        "simple": "Every phone call that came in or went out",
        "description": "79,000+ calls tracked. Shows who called, which campaign they came from, call duration, was it answered or abandoned.",
        "key_columns": {
            "lead_call_id": "Unique call ID",
            "lead_call_from": "Phone number that called",
            "lead_call_direction": "Inbound or Outbound",
            "lead_call_call_type": "Answered, Abandoned, Voicemail",
            "lead_call_duration": "How long the call lasted",
            "campaign_id": "Which campaign phone number they called",
            "lead_call_recording_url": "Link to call recording"
        },
        "links_to": ["campaign", "customer", "lead"]
    },
    "booking": {
        "emoji": "📓",
        "category": "Sales",
        "simple": "Online or third-party booking requests",
        "description": "When someone books via online form or Volca (call center). Many are Dismissed — wrong service, wrong area, or HVAC/plumbing requests they don't do yet.",
        "key_columns": {
            "id": "Unique booking",
            "name": "Person who booked",
            "source": "Where booking came from (e.g. Volca call center)",
            "status": "Dismissed or converted to Job",
            "job_id": "Which job it became (0 if dismissed)",
            "summary": "Notes about what they want",
            "is_first_time_client": "New customer?"
        },
        "links_to": ["job"]
    },
    "membership": {
        "emoji": "⭐",
        "category": "Sales",
        "simple": "Customers who have a maintenance contract (recurring revenue)",
        "description": "Members pay annually for regular PM visits. 1,749 active members. This is the predictable recurring revenue part of the business.",
        "key_columns": {
            "id": "Unique membership",
            "customer_id": "Which customer",
            "membership_type_id": "What plan they have",
            "status": "Active or Canceled",
            "from_date / to_date": "Start and end of membership",
            "billing_frequency": "Annual or OneTime",
            "cancellation_date": "When they cancelled (if cancelled)"
        },
        "links_to": ["customer", "membership_type", "location"]
    },
    "membership_type": {
        "emoji": "📄",
        "category": "Sales",
        "simple": "The different maintenance plan types available",
        "description": "Lookup table — list of plan names. Examples: 5 Year Warranty, Extended Warranty, 2/3/5 Year Generac Warranty.",
        "key_columns": {
            "id": "Unique plan type ID",
            "name": "Plan name",
            "active": "Still being sold?"
        },
        "links_to": ["membership"]
    },
    "business_unit": {
        "emoji": "🏢",
        "category": "Operations",
        "simple": "The different departments of the company",
        "description": "The company is divided into departments. Everything belongs to a business unit. This is how you separate Generator vs Electrical vs Solar revenue.",
        "key_columns": {
            "id": "Unique business unit ID",
            "name": "Department name (e.g. Generator - Maintenance)",
            "official_name": "Legal name (Premier Energy Solutions)",
            "tenant_name": "Company account = premiergeneratorinc",
            "email": "office@gopremierenergy.com",
            "quickbooks_class": "How it maps to QuickBooks accounting"
        },
        "links_to": ["job", "invoice", "technician"]
    },
    "job_type": {
        "emoji": "🗂️",
        "category": "Operations",
        "simple": "Categories of work — what kind of job is it?",
        "description": "Lookup table of job types. Every job has a type. Air Cooled Major PM, Generator Install, Diagnostic etc. are very different economically.",
        "key_columns": {
            "id": "Unique job type ID",
            "name": "Job type name",
            "duration": "Expected duration in seconds",
            "no_charge": "Is this always a free job?"
        },
        "links_to": ["job"]
    },
    "job_canceled_log": {
        "emoji": "❌",
        "category": "Operations",
        "simple": "Record of every cancelled job and why",
        "description": "When a job is cancelled, a reason is logged here. The memo field is very revealing — 'went with someone else', 'did it himself', etc.",
        "key_columns": {
            "id": "Unique cancellation record",
            "job_id": "Which job was cancelled",
            "reason_id": "Standardized reason code",
            "memo": "Free text notes — very revealing!",
            "created_on": "When it was cancelled"
        },
        "links_to": ["job", "job_cancel_reason"]
    },
    "job_split": {
        "emoji": "✂️",
        "category": "Operations",
        "simple": "How revenue credit is split between technicians on a job",
        "description": "If two techs work the same job, records what % each gets credit for. Most jobs show split=100 meaning one tech gets all credit.",
        "key_columns": {
            "job_id": "Which job",
            "technician_id": "Which technician",
            "split": "Percentage of revenue credit (100 = all of it)"
        },
        "links_to": ["job", "technician"]
    },
    "non_job_appointment": {
        "emoji": "🗓️",
        "category": "Operations",
        "simple": "Time blocks that are not customer jobs — meetings, training, etc.",
        "description": "When a technician has scheduled time that is not a customer visit. Important for capacity planning — e.g. Weekly Service Meeting every Monday.",
        "key_columns": {
            "id": "Unique entry",
            "technician_id": "Which technician",
            "name": "What it is (e.g. Weekly Service Meeting)",
            "start": "When it starts",
            "duration": "How long",
            "remove_technician_from_capacity_planning": "Should this block their availability?"
        },
        "links_to": ["technician", "timesheet_code"]
    },
    "timesheet_code": {
        "emoji": "🕐",
        "category": "Operations",
        "simple": "Categories of time — clock in, shop time, meal break etc.",
        "description": "Defines types of time entries. ClockIO = clock in/out. ShopTime = time in warehouse. Meal = unpaid break.",
        "key_columns": {
            "id": "Unique code",
            "code": "Short code (ClockIO, ShopTime, Meal)",
            "type": "ClockInOut, Paid, Unpaid",
            "rate_multiplier": "1 = normal, 1.5 = overtime"
        },
        "links_to": ["non_job_appointment"]
    },
    "employee": {
        "emoji": "👔",
        "category": "People",
        "simple": "Office staff and admin users (not field techs)",
        "description": "Office and admin people — dispatchers, managers, admins. Different from technicians. Note: some people appear in both tables (e.g. Derek McGovern).",
        "key_columns": {
            "id": "Unique employee",
            "name": "Employee name",
            "role": "Admin, Dispatcher etc.",
            "email": "Their work email",
            "active": "Still employed?"
        },
        "links_to": ["payroll", "payroll_adjustment"]
    },
    "payroll": {
        "emoji": "💵",
        "category": "Finance",
        "simple": "Pay periods for each employee/technician",
        "description": "Each row is one pay period for one person. burden_rate is 0 for everyone — this needs to be filled in to calculate true labor costs!",
        "key_columns": {
            "employee_id": "Which employee or technician",
            "started_on / ended_on": "Pay period dates",
            "status": "Pending, Approved, Expired",
            "burden_rate": "Loaded hourly cost — currently 0, needs fixing!"
        },
        "links_to": ["employee", "technician"]
    },
    "payroll_adjustment": {
        "emoji": "➕",
        "category": "Finance",
        "simple": "Extra payments outside regular pay — bonuses, stipends",
        "description": "Bonuses, on-call stipends, special payments. Examples: $100 On-Call Stipend, 4-hour minimum for after hours service.",
        "key_columns": {
            "employee_id": "Which technician or employee",
            "invoice_id": "Which job it relates to (if any)",
            "amount": "Dollar amount",
            "memo": "What it is for",
            "posted_on": "When it was applied"
        },
        "links_to": ["employee", "technician", "invoice"]
    },
    "purchase_order": {
        "emoji": "📦",
        "category": "Finance",
        "simple": "Orders placed with suppliers to buy parts or equipment",
        "description": "When a technician needs parts for a job they create a PO. The cost flows into the job's material cost.",
        "key_columns": {
            "id": "Unique PO number",
            "job_id": "Which job needs these parts",
            "technician_id": "Which tech ordered it",
            "vendor_id": "Which supplier",
            "total": "Total cost of order",
            "status": "Pending, Sent, Received"
        },
        "links_to": ["job", "technician", "purchase_order_item", "inventory_bill"]
    },
    "purchase_order_item": {
        "emoji": "🔩",
        "category": "Finance",
        "simple": "Each individual part on a purchase order",
        "description": "One PO can have multiple parts. Each part has a cost and SKU code.",
        "key_columns": {
            "purchase_order_id": "Which PO",
            "sku_name": "Part name",
            "sku_code": "Part number",
            "description": "What the part is for",
            "cost": "Cost to company",
            "quantity": "How many ordered"
        },
        "links_to": ["purchase_order"]
    },
    "inventory_bill": {
        "emoji": "🏭",
        "category": "Finance",
        "simple": "Bills from suppliers after parts are delivered",
        "description": "When parts arrive, the supplier sends a bill. Suppliers include Electrical Wholesalers Inc. and Concord Electric Supply.",
        "key_columns": {
            "id": "Unique bill",
            "job_id": "Which job the parts are for",
            "vendor_name": "Supplier name",
            "bill_amount": "Total bill",
            "tax_amount": "Tax on the bill",
            "due_date": "When payment is due",
            "ship_to_description": "Customer or job site name"
        },
        "links_to": ["job", "purchase_order", "inventory_bill_item"]
    },
    "inventory_bill_item": {
        "emoji": "📊",
        "category": "Finance",
        "simple": "Each item on a supplier bill",
        "description": "Shows exactly what was purchased. Reveals they buy 20KW Kohler generators (20RCA-QS6) for $4,340–$4,825 each, stored at Middleboro Warehouse.",
        "key_columns": {
            "inventory_bill_id": "Which bill",
            "name": "Product name (e.g. 20KW Kohler RCA)",
            "sku_code": "Product code (e.g. 20RCA-QS6)",
            "cost": "Cost per unit",
            "quantity": "How many",
            "inventory_location": "Where stored (e.g. Middleboro Warehouse)"
        },
        "links_to": ["inventory_bill"]
    },
    "project": {
        "emoji": "🏗️",
        "category": "Operations",
        "simple": "Groups multiple jobs together for big installations",
        "description": "A big install often has 2 jobs — site visit and actual install. A project groups them. Most have no name or status set.",
        "key_columns": {
            "id": "Unique project",
            "customer_id": "Which customer",
            "job_id": "Array of job IDs in this project",
            "status": "Project status (often null)",
            "start_date": "When project began"
        },
        "links_to": ["customer", "job"]
    },
    "tag_type": {
        "emoji": "🏷️",
        "category": "Operations",
        "simple": "Labels that can be put on customers or jobs",
        "description": "Like sticky notes. Used to flag things like Follow Up needed, Email Dormant, Recurring Services Booking.",
        "key_columns": {
            "id": "Unique tag",
            "name": "Tag name (e.g. Follow Up)",
            "code": "Short code (e.g. FOU)",
            "color": "Display color in ServiceTitan",
            "is_conversion_opportunity": "Is this marking a sales opportunity?"
        },
        "links_to": ["customer", "job"]
    },
    "zone": {
        "emoji": "🗺️",
        "category": "Operations",
        "simple": "Geographic service areas",
        "description": "Only 1 zone exists called Premier — geographic zones have not been set up properly yet. This limits routing and territory analysis.",
        "key_columns": {
            "id": "Unique zone",
            "name": "Zone name",
            "active": "Active?",
            "service_days_enabled": "Are service days configured?"
        },
        "links_to": ["location", "zone_zip"]
    },
    "zone_zip": {
        "emoji": "📮",
        "category": "Operations",
        "simple": "Zip codes that belong to each service zone",
        "description": "Maps zip codes to zones. Only 8 rows — zones are barely being used. When fully set up, this lets you see which zip codes are in which service territory.",
        "key_columns": {
            "zone_id": "Which zone this zip belongs to",
            "zip": "The zip code",
            "index": "Order within the zone"
        },
        "links_to": ["zone", "location"]
    },
    "call_reason": {
        "emoji": "💬",
        "category": "Operations",
        "simple": "Lookup list of reasons why customers call",
        "description": "Standardized reasons for inbound calls — e.g. Out of Service Area, Wants PM, Generator Not Running. Used to categorize leads and calls.",
        "key_columns": {
            "id": "Unique reason ID",
            "name": "Reason name (e.g. Out of Service Area)",
            "is_lead": "Does this call reason indicate a real lead?",
            "active": "Still being used?"
        },
        "links_to": ["call", "lead"]
    },
    "campaign_category": {
        "emoji": "📂",
        "category": "Marketing",
        "simple": "Categories that group campaigns together",
        "description": "Only 1 row — campaign categories are barely set up. When used properly, groups campaigns like Digital, Print, Referral for high-level reporting.",
        "key_columns": {
            "id": "Unique category ID",
            "name": "Category name",
            "type": "Type of category",
            "active": "Active?"
        },
        "links_to": ["campaign"]
    },
    "campaign_phone_number": {
        "emoji": "☎️",
        "category": "Marketing",
        "simple": "Phone numbers assigned to each campaign",
        "description": "Each campaign gets a unique tracking phone number. When a customer calls that number, the system knows which campaign brought them in. This is how call attribution works.",
        "key_columns": {
            "campaign_id": "Which campaign owns this number",
            "phone_number": "The tracking phone number"
        },
        "links_to": ["campaign", "call"]
    },
    "customer_contact": {
        "emoji": "📇",
        "category": "People",
        "simple": "Phone numbers and emails for each customer",
        "description": "A customer can have multiple contact methods — home phone, mobile, email. Each one is a separate row here. 81,000+ contact records.",
        "key_columns": {
            "id": "Unique contact record",
            "customer_id": "Which customer",
            "type": "Phone, Email, etc.",
            "value": "The actual phone number or email address",
            "phone_settings_do_not_text": "Do not send texts to this number",
            "phone_settings_phone_number": "Phone number digits"
        },
        "links_to": ["customer"]
    },
    "location_contact": {
        "emoji": "📍",
        "category": "People",
        "simple": "Phone numbers and contacts for each service location",
        "description": "Same as customer_contact but at the location level. 81,000+ records. A location might have a different contact than the customer (e.g. property manager).",
        "key_columns": {
            "id": "Unique contact record",
            "location_id": "Which location",
            "type": "Phone, Email etc.",
            "value": "The actual number or email",
            "memo": "Notes about this contact"
        },
        "links_to": ["location"]
    },
    "job_cancel_reason": {
        "emoji": "🚫",
        "category": "Operations",
        "simple": "Lookup list of reasons why jobs get cancelled",
        "description": "Standardized cancellation reasons used in the job_canceled_log. 11 reasons defined. Examples: Went with competitor, Customer not home, Weather.",
        "key_columns": {
            "id": "Unique reason ID",
            "name": "Reason name",
            "active": "Still being used?"
        },
        "links_to": ["job_canceled_log"]
    },
    "job_hold_reason": {
        "emoji": "⏸️",
        "category": "Operations",
        "simple": "Reasons why a job was put on hold",
        "description": "When a job is paused or held, a reason is recorded. 5 hold reasons defined. Examples: Waiting for parts, Waiting for permit, Customer requested delay.",
        "key_columns": {
            "id": "Unique reason ID",
            "name": "Reason name",
            "active": "Still being used?"
        },
        "links_to": ["job"]
    },
    "job_type_business_unit_id": {
        "emoji": "🔀",
        "category": "Operations",
        "simple": "Which job types are available in which business units",
        "description": "A bridge table linking job types to business units. Controls what job types can be created in each department. 86 rows.",
        "key_columns": {
            "job_type_id": "Which job type",
            "id": "Which business unit ID is allowed",
            "index": "Order"
        },
        "links_to": ["job_type", "business_unit"]
    },
    "job_type_skill": {
        "emoji": "🎯",
        "category": "Operations",
        "simple": "Skills required for each job type",
        "description": "Maps required skills to job types. Only 5 rows — not heavily used yet. Would allow matching jobs to technicians with the right skills.",
        "key_columns": {
            "job_type_id": "Which job type",
            "skill": "Skill name required",
            "index": "Order"
        },
        "links_to": ["job_type", "technician"]
    },
    "membership_type_billing_duration": {
        "emoji": "🔄",
        "category": "Sales",
        "simple": "Billing duration options for each membership plan",
        "description": "Defines how long each membership type can run — monthly, annual, multi-year. Links billing frequency to membership types.",
        "key_columns": {
            "membership_type_id": "Which membership plan",
            "billing_frequency": "How often they are billed (Annual, Monthly etc.)",
            "duration": "Length of the plan in months",
            "index": "Order"
        },
        "links_to": ["membership_type"]
    },
    "form_submission": {
        "emoji": "📨",
        "category": "Sales",
        "simple": "Online forms submitted by customers or technicians",
        "description": "When a technician completes a form on a job (inspection checklist, install form) or a customer submits a web form. 549 submissions.",
        "key_columns": {
            "id": "Unique submission",
            "form_id": "Which form template was used",
            "form_name": "Name of the form",
            "status": "Submitted, Draft etc.",
            "submitted_on": "When it was submitted",
            "created_by_id": "Who submitted it"
        },
        "links_to": ["form_submission_owner", "form_submission_unit_section"]
    },
    "form_submission_owner": {
        "emoji": "👥",
        "category": "Sales",
        "simple": "Who owns or is linked to each form submission",
        "description": "Links form submissions to the job, customer, or technician they belong to. One form can have multiple owners.",
        "key_columns": {
            "form_submission_id": "Which form submission",
            "id": "The owner entity ID (job, customer etc.)",
            "type": "What type of owner (Job, Customer, Technician)"
        },
        "links_to": ["form_submission"]
    },
    "form_submission_unit_section": {
        "emoji": "📑",
        "category": "Sales",
        "simple": "Sections within a form submission",
        "description": "A form has multiple sections (e.g. Equipment Check, Safety Inspection). Each section and its answers are stored here.",
        "key_columns": {
            "form_submission_id": "Which form submission",
            "id": "Unique section ID",
            "name": "Section name",
            "type": "Type of section",
            "value": "Answer or value entered",
            "comment": "Any comments added"
        },
        "links_to": ["form_submission", "form_submission_unit_sub_unit"]
    },
    "form_submission_unit_sub_unit": {
        "emoji": "📝",
        "category": "Sales",
        "simple": "Sub-sections within a form section",
        "description": "Nested form data — sections can have sub-sections with their own questions and answers. Stores the detailed inspection or checklist data.",
        "key_columns": {
            "form_submission_id": "Which form submission",
            "form_submission_unit_section_id": "Which section this belongs to",
            "id": "Unique sub-section ID",
            "name": "Sub-section name",
            "value": "Answer entered",
            "type": "Type of field"
        },
        "links_to": ["form_submission_unit_section"]
    },
    "project_status": {
        "emoji": "🟦",
        "category": "Operations",
        "simple": "Lookup list of possible project statuses",
        "description": "7 defined project statuses — e.g. In Progress, Completed, On Hold. Used to track where a multi-job project stands.",
        "key_columns": {
            "id": "Unique status ID",
            "name": "Status name",
            "orders": "Display order"
        },
        "links_to": ["project"]
    },
    "project_sub_status": {
        "emoji": "🟩",
        "category": "Operations",
        "simple": "More detailed sub-statuses within a project status",
        "description": "25 sub-statuses that give more detail within a main status. Example: In Progress → Waiting for Permit, Waiting for Equipment.",
        "key_columns": {
            "id": "Unique sub-status ID",
            "name": "Sub-status name",
            "status_id": "Which main status this belongs to",
            "orders": "Display order"
        },
        "links_to": ["project", "project_status"]
    },
    "task_priority": {
        "emoji": "🔺",
        "category": "Operations",
        "simple": "Priority levels for tasks",
        "description": "Lookup table with 4 priority levels for tasks — Low, Normal, High, Urgent. Simple reference table.",
        "key_columns": {
            "name": "Priority name (Low, Normal, High, Urgent)"
        },
        "links_to": []
    },
    "task_status": {
        "emoji": "🔘",
        "category": "Operations",
        "simple": "Possible statuses for tasks",
        "description": "5 task statuses — Open, In Progress, Completed, Cancelled etc. Simple lookup table.",
        "key_columns": {
            "name": "Status name"
        },
        "links_to": []
    },
    "task_type": {
        "emoji": "📌",
        "category": "Operations",
        "simple": "Categories of tasks",
        "description": "7 task types defining what kind of task it is — Follow Up Call, Site Visit, Office Task etc.",
        "key_columns": {
            "id": "Unique task type ID",
            "name": "Task type name",
            "active": "Still being used?",
            "excluded_task_resolution_id": "Which resolutions cannot be used with this type"
        },
        "links_to": ["task_resolution"]
    },
    "task_resolution": {
        "emoji": "✅",
        "category": "Operations",
        "simple": "How a task was resolved or closed",
        "description": "3 resolution types — how a task was completed or closed. Examples: Resolved, Unresolved, Converted to Job.",
        "key_columns": {
            "id": "Unique resolution ID",
            "name": "Resolution name",
            "type": "Type of resolution",
            "active": "Still being used?"
        },
        "links_to": ["task_type"]
    },
    "task_resolution_type": {
        "emoji": "🏁",
        "category": "Operations",
        "simple": "High level grouping of task resolution types",
        "description": "Only 2 rows — a simple lookup that groups task resolutions into broader categories.",
        "key_columns": {
            "name": "Resolution type name"
        },
        "links_to": ["task_resolution"]
    },
    "task_source": {
        "emoji": "📡",
        "category": "Operations",
        "simple": "Where a task originated from",
        "description": "4 task sources — where did this task come from? Examples: Manual, Phone Call, Email, System Generated.",
        "key_columns": {
            "id": "Unique source ID",
            "name": "Source name",
            "active": "Still being used?"
        },
        "links_to": []
    },
    "team": {
        "emoji": "👥",
        "category": "People",
        "simple": "Groups that technicians belong to",
        "description": "7 teams defined — groups technicians together. Examples: Office, Subcontractors, Field Team A. Used for scheduling and reporting.",
        "key_columns": {
            "id": "Unique team ID",
            "name": "Team name",
            "active": "Still active?",
            "created_by": "Who created this team"
        },
        "links_to": ["technician"]
    }
}

CATEGORIES = ["All", "People", "Operations", "Finance", "Sales", "Marketing"]
CATEGORY_COLORS = {
    "People":     "🔵",
    "Operations": "🟢",
    "Finance":    "🟡",
    "Sales":      "🟣",
    "Marketing":  "🟠"
}

# --- SIDEBAR FILTERS ---
st.sidebar.header("🔍 Filter Tables")
selected_category = st.sidebar.selectbox("Category", CATEGORIES)
search_term = st.sidebar.text_input("Search table name", "").lower()
rows_to_show = st.sidebar.slider("Sample rows to load", min_value=5, max_value=50, value=10, step=5)

# --- FILTER TABLES ---
filtered_tables = {
    name: info for name, info in TABLE_INFO.items()
    if (selected_category == "All" or info["category"] == selected_category)
    and (search_term == "" or search_term in name.lower())
}

# --- OVERVIEW STATS ---
st.markdown("---")
col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Total Tables", "59")
col2.metric("Customer Records", "40,828")
col3.metric("Total Jobs", "22,756")
col4.metric("Total Invoices", "26,505")
col5.metric("Active Technicians", "35")

st.markdown("---")

# --- TABLE GRID ---
st.subheader(f"📋 Tables ({len(filtered_tables)} shown)")

cols = st.columns(4)
selected_table = st.session_state.get("selected_table", None)

for i, (tname, tinfo) in enumerate(filtered_tables.items()):
    col = cols[i % 4]
    with col:
        is_selected = selected_table == tname
        if st.button(
            f"{tinfo['emoji']} {tname}",
            key=f"btn_{tname}",
            use_container_width=True,
            type="primary" if is_selected else "secondary"
        ):
            if is_selected:
                st.session_state["selected_table"] = None
            else:
                st.session_state["selected_table"] = tname
            st.rerun()

# --- TABLE DETAIL VIEW ---
selected_table = st.session_state.get("selected_table", None)

if selected_table and selected_table in TABLE_INFO:
    info = TABLE_INFO[selected_table]
    st.markdown("---")

    # Header
    st.markdown(f"## {info['emoji']} `{selected_table}`")
    st.markdown(f"**{info['simple']}**")
    st.info(info["description"])

    # Two columns: columns explained + links
    col1, col2 = st.columns([2, 1])

    with col1:
        st.markdown("#### 📌 What each column means")
        for col_name, col_desc in info["key_columns"].items():
            st.markdown(f"- **`{col_name}`** — {col_desc}")

    with col2:
        st.markdown("#### 🔗 Connects to")
        for link in info["links_to"]:
            st.markdown(f"- `{link}`")

        st.markdown("#### 📁 Category")
        st.markdown(f"{CATEGORY_COLORS.get(info['category'], '⚪')} {info['category']}")

    # Live data from BigQuery
    st.markdown("---")
    st.markdown(f"#### 🔴 Live Data from BigQuery — `{selected_table}` ({rows_to_show} rows)")

    try:
        with st.spinner(f"Loading {rows_to_show} rows from {selected_table}..."):
            # Tables that have _fivetran_deleted
            has_deleted_col = selected_table not in [
                "campaign_phone_number", "payment_applied_to",
                "membership_type_billing_duration", "job_type_business_unit_id",
                "job_type_skill"
            ]
            where_clause = "WHERE _fivetran_deleted = FALSE" if has_deleted_col else ""

            query = f"""
                SELECT * FROM `{PROJECT_ID}.{DATASET}.{selected_table}`
                {where_clause}
                LIMIT {rows_to_show}
            """
            df = client.query(query).to_dataframe()

        st.success(f"✅ Loaded {len(df)} rows")

        # Show row count
        count_query = f"SELECT COUNT(*) as total FROM `{PROJECT_ID}.{DATASET}.{selected_table}`"
        total = client.query(count_query).to_dataframe()['total'][0]
        st.caption(f"📊 This table has **{total:,} total rows** in BigQuery")

        # Display dataframe
        st.dataframe(df, use_container_width=True, hide_index=True)

        # Download button
        csv = df.to_csv(index=False)
        st.download_button(
            label=f"⬇️ Download {selected_table} sample as CSV",
            data=csv,
            file_name=f"{selected_table}_sample.csv",
            mime="text/csv"
        )

    except Exception as e:
        st.error(f"❌ Could not load data: {e}")

else:
    st.markdown("")
    st.markdown("👆 **Click any table above to see its data and explanation**")