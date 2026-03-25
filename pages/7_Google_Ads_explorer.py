import streamlit as st
from google.cloud import bigquery
from google.oauth2 import service_account
import pandas as pd
from utils import get_client, render_sidebar

# --- CONFIG ---
PROJECT_ID = "the-brain-487614"
DATASET    = "Google_ads"



client = get_client()

# --- PAGE SETUP ---
st.set_page_config(page_title="Google Ads Table Explorer", page_icon="📊", layout="wide")
st.title("📊 Google Ads Table Explorer")
st.markdown("Understand what data we have from Google Ads. Click any table to explore it.")

# --- TABLE INFO ---
TABLE_INFO = {
    "p_ads_Customer_9403250839": {
        "emoji": "🏢",
        "category": "Account",
        "simple": "The Google Ads account itself",
        "description": "Top-level account info. Only 2 rows. Most importantly — check that customer_auto_tagging_enabled = TRUE. If this is FALSE, GCLIDs will not be tracked and the entire PBOS attribution chain breaks.",
        "key_columns": {
            "customer_id": "Google Ads account ID (9403250839)",
            "customer_descriptive_name": "Account name",
            "customer_currency_code": "Currency (USD)",
            "customer_time_zone": "Account timezone",
            "customer_auto_tagging_enabled": "CRITICAL — must be TRUE for GCLID tracking to work",
            "customer_manager": "Is this a manager (MCC) account"
        },
        "links_to": ["p_ads_Campaign_9403250839"]
    },
    "p_ads_Campaign_9403250839": {
        "emoji": "📣",
        "category": "Structure",
        "simple": "All campaigns in the account",
        "description": "56 campaigns. Almost all PAUSED — only LocalServicesCampaign is ENABLED and spending. Each campaign has a unique campaign_id that links to all stats tables. Budget is stored in micros — divide by 1,000,000 for dollars.",
        "key_columns": {
            "campaign_id": "Unique campaign ID — the join key to every stats table",
            "campaign_name": "Human-readable name e.g. 'PES - Search - Generators'",
            "campaign_status": "ENABLED / PAUSED / REMOVED",
            "campaign_advertising_channel_type": "SEARCH / DISPLAY / PERFORMANCE_MAX / LOCAL_SERVICES",
            "campaign_bidding_strategy_type": "MAXIMIZE_CONVERSIONS / TARGET_CPA / MANUAL_CPC",
            "campaign_budget_amount_micros": "Daily budget — divide by 1,000,000 for dollars",
            "campaign_start_date": "When campaign started",
            "campaign_end_date": "When it ends (null = no end date)"
        },
        "links_to": ["p_ads_CampaignStats_9403250839", "p_ads_AdGroup_9403250839", "p_ads_Ad_9403250839", "p_ads_Keyword_9403250839"]
    },
    "p_ads_AdGroup_9403250839": {
        "emoji": "📁",
        "category": "Structure",
        "simple": "Ad groups within campaigns",
        "description": "110 ad groups. Each campaign is divided into ad groups — a campaign about 'Generators' might have ad groups for 'Generator Install', 'Generator Repair', 'Kohler Generators' etc. Keywords and ads live inside ad groups.",
        "key_columns": {
            "ad_group_id": "Unique ad group ID",
            "ad_group_name": "Ad group name",
            "ad_group_status": "ENABLED / PAUSED / REMOVED",
            "ad_group_type": "SEARCH_STANDARD / DISPLAY_STANDARD",
            "campaign_id": "Parent campaign — join to Campaign table",
            "campaign_bidding_strategy_type": "Bidding strategy inherited from campaign"
        },
        "links_to": ["p_ads_Campaign_9403250839", "p_ads_Ad_9403250839", "p_ads_Keyword_9403250839"]
    },
    "p_ads_Ad_9403250839": {
        "emoji": "📝",
        "category": "Structure",
        "simple": "All ad creatives — headlines, descriptions, landing pages",
        "description": "316 ads. These are Responsive Search Ads — Google mixes and matches headlines automatically. Headlines and descriptions are stored as JSON arrays inside the column. Use JSON_EXTRACT_SCALAR to pull out text. Ad strength tells you how well the ad will perform.",
        "key_columns": {
            "ad_group_ad_ad_id": "Unique ad ID",
            "ad_group_id": "Parent ad group ID",
            "campaign_id": "Parent campaign ID",
            "ad_group_ad_status": "ENABLED / PAUSED",
            "ad_group_ad_ad_type": "RESPONSIVE_SEARCH_AD / EXPANDED_TEXT_AD",
            "ad_group_ad_ad_strength": "EXCELLENT / GOOD / AVERAGE / POOR — Google's rating of ad quality",
            "ad_group_ad_ad_responsive_search_ad_headlines": "JSON array of up to 15 headlines",
            "ad_group_ad_ad_responsive_search_ad_descriptions": "JSON array of up to 4 descriptions",
            "ad_group_ad_ad_final_urls": "JSON array of landing page URLs",
            "ad_group_ad_policy_summary_approval_status": "APPROVED / UNDER_REVIEW / DISAPPROVED"
        },
        "links_to": ["p_ads_AdGroup_9403250839", "p_ads_Campaign_9403250839"]
    },
    "p_ads_Keyword_9403250839": {
        "emoji": "🔑",
        "category": "Structure",
        "simple": "All keywords — what search terms trigger your ads",
        "description": "2,866 keywords across all campaigns. This is the most important structural table for PBOS. Quality score (1-10) tells you if you're paying the 'stupidity tax'. Score 1-4 = paying too much. Score 7-10 = Google rewards you with lower costs. Also contains negative keywords (is_negative = TRUE) which block certain searches.",
        "key_columns": {
            "ad_group_criterion_criterion_id": "Unique keyword ID",
            "ad_group_id": "Parent ad group ID",
            "campaign_id": "Parent campaign ID",
            "ad_group_criterion_keyword_text": "The actual keyword e.g. 'generac generator'",
            "ad_group_criterion_keyword_match_type": "BROAD / PHRASE / EXACT — how strictly Google matches searches",
            "ad_group_criterion_negative": "TRUE = negative keyword (blocked), FALSE = normal keyword",
            "ad_group_criterion_status": "ENABLED / PAUSED / REMOVED",
            "ad_group_criterion_quality_info_quality_score": "1-10 score. Low = paying the stupidity tax",
            "ad_group_criterion_quality_info_creative_quality_score": "Ad relevance — ABOVE_AVERAGE / AVERAGE / BELOW_AVERAGE",
            "ad_group_criterion_quality_info_post_click_quality_score": "Landing page relevance score",
            "ad_group_criterion_quality_info_search_predicted_ctr": "Predicted click rate",
            "ad_group_criterion_position_estimates_first_page_cpc_micros": "Minimum bid to appear on page 1 (micros)"
        },
        "links_to": ["p_ads_AdGroup_9403250839", "p_ads_Campaign_9403250839"]
    },
    "p_ads_Budget_9403250839": {
        "emoji": "💰",
        "category": "Structure",
        "simple": "Budget configurations for campaigns",
        "description": "80 budget records. Shows what daily budget is set for each campaign and whether Google recommends increasing it. campaign_budget_recommended_budget_amount_micros tells you what Google thinks you should spend.",
        "key_columns": {
            "campaign_budget_id": "Unique budget ID",
            "campaign_budget_amount_micros": "Daily budget — divide by 1,000,000 for dollars",
            "campaign_budget_status": "ENABLED / REMOVED",
            "campaign_budget_delivery_method": "STANDARD (even pacing) / ACCELERATED (spend fast)",
            "campaign_budget_recommended_budget_amount_micros": "Google's suggested budget to get more results",
            "campaign_budget_has_recommended_budget": "TRUE if Google thinks budget is too low"
        },
        "links_to": ["p_ads_Campaign_9403250839"]
    },
    "p_ads_BidGoal_9403250839": {
        "emoji": "🎯",
        "category": "Structure",
        "simple": "Portfolio bidding strategies shared across campaigns",
        "description": "Shared bidding strategies. Instead of each campaign managing its own bids, multiple campaigns can share one strategy. Contains target CPA and target ROAS settings.",
        "key_columns": {
            "bidding_strategy_id": "Unique strategy ID",
            "bidding_strategy_name": "Strategy name",
            "bidding_strategy_type": "TARGET_CPA / TARGET_ROAS / MAXIMIZE_CONVERSIONS",
            "bidding_strategy_target_cpa_target_cpa_micros": "Target cost per acquisition in micros",
            "bidding_strategy_target_roas_target_roas": "Target return on ad spend (e.g. 4.0 = $4 revenue per $1 spent)"
        },
        "links_to": ["p_ads_Campaign_9403250839"]
    },
    "p_ads_CampaignCriterion_9403250839": {
        "emoji": "🎛️",
        "category": "Structure",
        "simple": "Campaign-level targeting rules — devices, negatives, bid adjustments",
        "description": "7,808 rows — the largest table. Contains campaign-level targeting: device bid modifiers (bid more on mobile), negative keywords at campaign level, location exclusions. campaign_criterion_type tells you what kind of rule each row is.",
        "key_columns": {
            "campaign_id": "Which campaign this rule applies to",
            "campaign_criterion_type": "DEVICE / KEYWORD / LOCATION / AGE_RANGE",
            "campaign_criterion_negative": "TRUE = exclusion rule, FALSE = targeting rule",
            "campaign_criterion_bid_modifier": "Bid multiplier e.g. 1.2 = bid 20% more",
            "campaign_criterion_device_type": "DESKTOP / MOBILE / TABLET",
            "campaign_criterion_display_name": "Human-readable name of the criterion"
        },
        "links_to": ["p_ads_Campaign_9403250839"]
    },
    "p_ads_AdGroupCriterion_9403250839": {
        "emoji": "🎯",
        "category": "Structure",
        "simple": "Ad group level targeting criteria",
        "description": "4,336 rows. Targeting rules at the ad group level — more specific than campaign level. Includes keywords, user lists, topics, and placements at the ad group level.",
        "key_columns": {
            "ad_group_criterion_criterion_id": "Unique criterion ID",
            "ad_group_id": "Which ad group",
            "ad_group_criterion_type": "KEYWORD / LISTING_GROUP / USER_LIST",
            "ad_group_criterion_negative": "Is this an exclusion",
            "ad_group_criterion_status": "ENABLED / PAUSED"
        },
        "links_to": ["p_ads_AdGroup_9403250839"]
    },
    "p_ads_AdGroupBidModifier_9403250839": {
        "emoji": "📱",
        "category": "Structure",
        "simple": "Bid adjustments by device type per ad group",
        "description": "348 rows. Controls how much more or less to bid for each device. A modifier of 1.3 on mobile means bid 30% more for mobile clicks. Important for LSA campaigns where mobile converts much better than desktop.",
        "key_columns": {
            "ad_group_id": "Which ad group",
            "ad_group_bid_modifier_device_type": "DESKTOP / MOBILE / TABLET",
            "ad_group_bid_modifier_bid_modifier": "Multiplier — 1.0 = no change, 1.3 = +30%, 0.7 = -30%",
            "ad_group_bid_modifier_bid_modifier_source": "Where the modifier came from"
        },
        "links_to": ["p_ads_AdGroup_9403250839"]
    },
    "p_ads_LocationBasedCampaignCriterion_9403250839": {
        "emoji": "📍",
        "category": "Structure",
        "simple": "Geographic locations targeted or excluded per campaign",
        "description": "544 rows. Shows exactly which cities, states, or zip codes each campaign is targeting. criterion_id maps to a Google location ID. If negative = TRUE, that location is excluded from the campaign.",
        "key_columns": {
            "campaign_id": "Which campaign",
            "campaign_criterion_criterion_id": "Google's geo ID (maps to a city/state/zip code)",
            "campaign_criterion_negative": "TRUE = excluded location, FALSE = targeted location",
            "campaign_criterion_bid_modifier": "Bid adjustment for this location"
        },
        "links_to": ["p_ads_Campaign_9403250839"]
    },
    "p_ads_AgeRange_9403250839": {
        "emoji": "👶",
        "category": "Structure",
        "simple": "Age range targeting settings per ad group",
        "description": "770 rows. Controls which age groups see your ads. Can increase or decrease bids for certain age groups, or exclude them entirely.",
        "key_columns": {
            "ad_group_criterion_age_range_type": "AGE_RANGE_18_24 / AGE_RANGE_25_34 / AGE_RANGE_35_44 etc",
            "ad_group_criterion_bid_modifier": "Bid adjustment for this age group",
            "ad_group_criterion_negative": "Is this age group excluded",
            "ad_group_criterion_status": "ENABLED / PAUSED"
        },
        "links_to": ["p_ads_AdGroup_9403250839"]
    },
    "p_ads_Gender_9403250839": {
        "emoji": "⚧️",
        "category": "Structure",
        "simple": "Gender targeting settings per ad group",
        "description": "300 rows. Controls bid adjustments by gender. For a home services company, this can reveal whether men or women are more likely to book.",
        "key_columns": {
            "ad_group_criterion_gender_type": "MALE / FEMALE / UNDETERMINED",
            "ad_group_criterion_bid_modifier": "Bid adjustment",
            "ad_group_criterion_negative": "Is this gender excluded"
        },
        "links_to": ["p_ads_AdGroup_9403250839"]
    },
    "p_ads_ParentalStatus_9403250839": {
        "emoji": "👨‍👩‍👧",
        "category": "Structure",
        "simple": "Parental status targeting per ad group",
        "description": "330 rows. Allows targeting or excluding people based on whether they are parents. Parents are often homeowners — relevant for generator installs.",
        "key_columns": {
            "ad_group_criterion_parental_status_type": "PARENT / NOT_A_PARENT / UNDETERMINED",
            "ad_group_criterion_bid_modifier": "Bid adjustment for this parental status"
        },
        "links_to": ["p_ads_AdGroup_9403250839"]
    },
    "p_ads_CampaignAudience_9403250839": {
        "emoji": "👥",
        "category": "Structure",
        "simple": "Audience targeting at the campaign level",
        "description": "196 rows. Connects campaigns to audience lists — remarketing lists (people who visited the website), in-market audiences (people Google knows are looking for generators), and customer match lists.",
        "key_columns": {
            "campaign_id": "Which campaign",
            "campaign_criterion_criterion_id": "Audience list ID",
            "campaign_criterion_bid_modifier": "Bid adjustment for this audience"
        },
        "links_to": ["p_ads_Campaign_9403250839"]
    },
    "p_ads_AdGroupAudience_9403250839": {
        "emoji": "🎪",
        "category": "Structure",
        "simple": "Audience targeting at the ad group level",
        "description": "184 rows. Same as CampaignAudience but more granular — set at the ad group level for finer control over which audience sees which ads.",
        "key_columns": {
            "ad_group_id": "Which ad group",
            "ad_group_criterion_criterion_id": "Audience list ID",
            "ad_group_criterion_status": "ENABLED / PAUSED"
        },
        "links_to": ["p_ads_AdGroup_9403250839"]
    },
    "p_ads_CampaignStats_9403250839": {
        "emoji": "📈",
        "category": "Performance",
        "simple": "Daily campaign performance — spend, clicks, conversions",
        "description": "THE most important performance table. Every day, for every campaign, broken down by device and network. Cost is in MICROS — divide by 1,000,000 for dollars. This is what we use to build fact_marketing_spend.",
        "key_columns": {
            "campaign_id": "Join to Campaign table for name",
            "segments_date": "The date",
            "segments_device": "DESKTOP / MOBILE / TABLET",
            "segments_day_of_week": "MONDAY / TUESDAY / WEDNESDAY etc",
            "segments_ad_network_type": "SEARCH / DISPLAY / YOUTUBE",
            "metrics_cost_micros": "SPEND — divide by 1,000,000 for dollars!",
            "metrics_clicks": "Number of ad clicks",
            "metrics_impressions": "Times the ad was shown",
            "metrics_conversions": "Leads generated (calls + form fills)",
            "metrics_ctr": "Click-through rate (0-1 scale, ×100 for %)",
            "metrics_cost_per_conversion": "Cost per lead in dollars",
            "metrics_average_cpc": "Average cost per click"
        },
        "links_to": ["p_ads_Campaign_9403250839"]
    },
    "p_ads_CampaignBasicStats_9403250839": {
        "emoji": "📊",
        "category": "Performance",
        "simple": "Simplified daily campaign stats — fewer columns",
        "description": "17 rows. A slimmed-down version of CampaignStats with just the core metrics. Useful for quick overviews without the extra columns.",
        "key_columns": {
            "campaign_id": "Which campaign",
            "segments_date": "Date",
            "segments_device": "Device type",
            "metrics_clicks": "Clicks",
            "metrics_impressions": "Impressions",
            "metrics_cost_micros": "Spend in micros",
            "metrics_conversions": "Conversions"
        },
        "links_to": ["p_ads_Campaign_9403250839"]
    },
    "p_ads_CampaignConversionStats_9403250839": {
        "emoji": "🎯",
        "category": "Performance",
        "simple": "Conversions broken down by conversion action type",
        "description": "2 rows. Tells you WHAT TYPE of conversion happened — was it a phone call, a form submission, or a chat? Each conversion action has a name. This lets you separate phone call leads from form leads.",
        "key_columns": {
            "campaign_id": "Which campaign",
            "segments_date": "Date",
            "segments_conversion_action_name": "Name of the conversion action e.g. 'Phone Call', 'Form Submit'",
            "segments_conversion_action_category": "DEFAULT / LEAD / PURCHASE",
            "metrics_conversions": "Number of this type of conversion",
            "metrics_conversions_value": "Dollar value assigned to these conversions"
        },
        "links_to": ["p_ads_Campaign_9403250839"]
    },
    "p_ads_HourlyCampaignStats_9403250839": {
        "emoji": "⏰",
        "category": "Performance",
        "simple": "Campaign performance broken down by hour of the day",
        "description": "85 rows. Same as CampaignStats but with a segments_hour column (0-23). Tells you exactly when during the day people click and convert. Critical for ad scheduling — run ads harder at 10am if that's when most leads come in.",
        "key_columns": {
            "campaign_id": "Which campaign",
            "segments_date": "Date",
            "segments_hour": "Hour 0-23 (0=midnight, 9=9am, 17=5pm)",
            "segments_device": "Device type",
            "metrics_clicks": "Clicks in that hour",
            "metrics_impressions": "Impressions in that hour",
            "metrics_conversions": "Leads in that hour",
            "metrics_cost_micros": "Spend in that hour"
        },
        "links_to": ["p_ads_Campaign_9403250839"]
    },
    "p_ads_HourlyCampaignConversionStats_9403250839": {
        "emoji": "📞",
        "category": "Performance",
        "simple": "Conversion details by hour — when do leads actually come in?",
        "description": "3 rows. Conversion breakdown by hour and conversion type. Tells you not just when people click but when they actually convert into leads. Combine with HourlyCampaignStats for a full hourly picture.",
        "key_columns": {
            "campaign_id": "Which campaign",
            "segments_hour": "Hour 0-23",
            "segments_conversion_action_name": "Type of conversion",
            "metrics_conversions": "Conversions in that hour"
        },
        "links_to": ["p_ads_Campaign_9403250839"]
    },
    "p_ads_AccountStats_9403250839": {
        "emoji": "🏦",
        "category": "Performance",
        "simple": "Daily stats rolled up to the entire account level",
        "description": "14 rows. Same metrics as CampaignStats but with all campaigns summed together. Good for total account-level reporting — total spend this week, total impressions this month etc.",
        "key_columns": {
            "customer_id": "The account ID (no campaign_id here)",
            "segments_date": "Date",
            "segments_device": "Device",
            "metrics_cost_micros": "Total account spend for this day",
            "metrics_clicks": "Total clicks across all campaigns",
            "metrics_conversions": "Total conversions across all campaigns"
        },
        "links_to": []
    },
    "p_ads_AccountBasicStats_9403250839": {
        "emoji": "📉",
        "category": "Performance",
        "simple": "Simplified account-level daily stats",
        "description": "17 rows. Simplified version of AccountStats with fewer columns. Good for quick account-level KPI checks.",
        "key_columns": {
            "customer_id": "Account ID",
            "segments_date": "Date",
            "metrics_clicks": "Total clicks",
            "metrics_impressions": "Total impressions",
            "metrics_cost_micros": "Total spend"
        },
        "links_to": []
    },
    "p_ads_AccountConversionStats_9403250839": {
        "emoji": "✅",
        "category": "Performance",
        "simple": "Account-level conversion breakdown by action type",
        "description": "2 rows. Shows total conversions across the whole account broken down by conversion action type — useful for seeing the overall mix of phone calls vs form fills.",
        "key_columns": {
            "segments_conversion_action_name": "Conversion action name",
            "segments_date": "Date",
            "metrics_conversions": "Total conversions of this type",
            "metrics_conversions_value": "Total value"
        },
        "links_to": []
    },
    "p_ads_HourlyAccountStats_9403250839": {
        "emoji": "🕐",
        "category": "Performance",
        "simple": "Account-level hourly performance (all campaigns combined)",
        "description": "85 rows. Same as HourlyCampaignStats but all campaigns combined. Shows total account activity by hour — good for overall scheduling decisions.",
        "key_columns": {
            "segments_date": "Date",
            "segments_hour": "Hour 0-23",
            "segments_device": "Device",
            "metrics_clicks": "Total clicks in this hour",
            "metrics_cost_micros": "Total spend in this hour"
        },
        "links_to": []
    },
    "p_ads_BudgetStats_9403250839": {
        "emoji": "💸",
        "category": "Performance",
        "simple": "Budget performance + Google's recommended budget changes",
        "description": "5 rows. Shows campaign performance and Google's recommendation for budget increases. The estimated_change columns tell you how many more clicks/conversions you'd get if you increased the budget.",
        "key_columns": {
            "campaign_id": "Which campaign",
            "campaign_name": "Campaign name",
            "campaign_status": "Status",
            "metrics_cost_micros": "Actual spend",
            "campaign_budget_recommended_budget_estimated_change_weekly_clicks": "Extra clicks Google says you'd get with a higher budget",
            "campaign_budget_recommended_budget_estimated_change_weekly_cost_micros": "Extra spend required"
        },
        "links_to": ["p_ads_Campaign_9403250839"]
    },
    "p_ads_CampaignLocationTargetStats_9403250839": {
        "emoji": "🗺️",
        "category": "Performance",
        "simple": "Performance by geographic location — which cities convert?",
        "description": "118 rows. Shows clicks, spend, and conversions per geographic location target. Tells you which cities are generating leads and at what cost. Critical for a local service business to know where their ad dollars are working.",
        "key_columns": {
            "campaign_id": "Which campaign",
            "campaign_criterion_criterion_id": "Google location ID (maps to city/state/zip)",
            "segments_date": "Date",
            "metrics_clicks": "Clicks from this location",
            "metrics_conversions": "Conversions from this location",
            "metrics_cost_micros": "Spend attributed to this location"
        },
        "links_to": ["p_ads_Campaign_9403250839"]
    },
    "p_ads_CampaignCrossDeviceStats_9403250839": {
        "emoji": "🔄",
        "category": "Performance",
        "simple": "Cross-device conversions — clicked on mobile, converted on desktop",
        "description": "5 rows. Tracks when someone clicks an ad on one device but completes the conversion on a different device. Important because someone might see the ad on their phone but call from their computer.",
        "key_columns": {
            "campaign_id": "Which campaign",
            "segments_date": "Date",
            "metrics_cross_device_conversions": "Conversions that happened on a different device",
            "metrics_phone_calls": "Phone calls generated",
            "metrics_phone_impressions": "Times phone number was shown"
        },
        "links_to": ["p_ads_Campaign_9403250839"]
    },
    "p_ads_CampaignCookieStats_9403250839": {
        "emoji": "🥧",
        "category": "Performance",
        "simple": "Search impression share — how often your ad could have shown but didn't",
        "description": "5 rows. Shows what % of eligible searches your ad actually appeared for. If impression share is 40%, your ad missed 60% of chances. Lost due to budget vs lost due to rank tells you whether the fix is more money or better ads.",
        "key_columns": {
            "campaign_id": "Which campaign",
            "metrics_search_impression_share": "% of eligible impressions you captured",
            "metrics_search_budget_lost_impression_share": "% lost because budget ran out",
            "metrics_search_rank_lost_impression_share": "% lost because ad rank was too low",
            "metrics_absolute_top_impression_percentage": "% of times your ad showed as position 1"
        },
        "links_to": ["p_ads_Campaign_9403250839"]
    },
    "p_ads_PaidOrganicStats_9403250839": {
        "emoji": "🌱",
        "category": "Performance",
        "simple": "Paid vs organic clicks — are you paying for clicks you'd get for free?",
        "description": "26 rows. Compares paid clicks to organic (SEO) clicks for the same search terms. If you're getting organic clicks for a keyword, you might not need to bid as high on it. Very useful for budget optimization.",
        "key_columns": {
            "paid_organic_search_term_view_search_term": "The search term",
            "segments_date": "Date",
            "metrics_clicks": "Paid ad clicks",
            "metrics_organic_clicks": "Free organic (SEO) clicks",
            "metrics_combined_clicks": "Total clicks paid + organic",
            "metrics_organic_impressions": "Times you showed organically"
        },
        "links_to": []
    },
    "p_ads_AdGroupLabel_9403250839": {
        "emoji": "🏷️",
        "category": "Labels",
        "simple": "Labels applied to ad groups for organization",
        "description": "8 rows. Custom labels used to organize and filter ad groups. Labels are like sticky notes that help categorize ad groups for reporting and management.",
        "key_columns": {
            "ad_group_id": "Which ad group",
            "ad_group_name": "Ad group name",
            "label_id": "Which label",
            "label_name": "Label name"
        },
        "links_to": ["p_ads_AdGroup_9403250839"]
    },
    "p_ads_CampaignLabel_9403250839": {
        "emoji": "🏷️",
        "category": "Labels",
        "simple": "Labels applied to campaigns",
        "description": "2 rows. Custom labels on campaigns. Can be used to group campaigns by season, product line, or status for easier filtering in reports.",
        "key_columns": {
            "campaign_id": "Which campaign",
            "campaign_name": "Campaign name",
            "label_id": "Which label",
            "label_name": "Label name"
        },
        "links_to": ["p_ads_Campaign_9403250839"]
    },
    "p_ads_ClickStats_9403250839": {
        "emoji": "🔗",
        "category": "Attribution",
        "simple": "⭐ MOST IMPORTANT — Individual clicks with GCLID for attribution",
        "description": "Currently 0 rows — will populate when search ads run. THIS IS THE HEART OF PBOS. Every click gets a unique GCLID. When ServiceTitan stores the GCLID on a job, you JOIN this table to know exactly which campaign, keyword, and location generated that job. Without this table populated, you cannot do profit attribution.",
        "key_columns": {
            "click_view_gclid": "THE GCLID — unique ID per click, links to ServiceTitan",
            "campaign_id": "Which campaign this click came from",
            "ad_group_id": "Which ad group",
            "click_view_keyword": "Which keyword triggered the click",
            "click_view_keyword_info_text": "Keyword text",
            "click_view_keyword_info_match_type": "BROAD / PHRASE / EXACT",
            "click_view_area_of_interest_city": "City the user was interested in",
            "click_view_area_of_interest_region": "State/region",
            "click_view_location_of_presence_city": "City where user physically was",
            "segments_date": "Date of click",
            "segments_device": "Device used (mobile/desktop)",
            "metrics_clicks": "Always 1 — one row per click"
        },
        "links_to": ["p_ads_Campaign_9403250839", "p_ads_AdGroup_9403250839"]
    },
    "p_ads_KeywordStats_9403250839": {
        "emoji": "🔍",
        "category": "Attribution",
        "simple": "Daily performance per keyword — currently empty, critical when live",
        "description": "Currently 0 rows. When search campaigns run, this fills up with daily stats per keyword — how many clicks, how much spend, how many conversions each keyword generates. Combine with Keyword table to calculate cost per lead per keyword.",
        "key_columns": {
            "ad_group_criterion_criterion_id": "Join to Keyword table for keyword text",
            "campaign_id": "Which campaign",
            "segments_date": "Date",
            "metrics_clicks": "Clicks on this keyword",
            "metrics_cost_micros": "Spend on this keyword",
            "metrics_conversions": "Conversions from this keyword",
            "metrics_impressions": "Times ad showed for this keyword"
        },
        "links_to": ["p_ads_Keyword_9403250839", "p_ads_Campaign_9403250839"]
    },
    "p_ads_SearchQueryStats_9403250839": {
        "emoji": "🔎",
        "category": "Attribution",
        "simple": "⭐ Waste Hunter — actual search terms people typed to find your ads",
        "description": "Currently 0 rows. When live, this is the WASTE HUNTER table. Shows the exact words people typed that triggered your ads. Search terms with high spend and 0 conversions = wasted money = add as negative keywords. This is N-gram analysis in PBOS.",
        "key_columns": {
            "search_term_view_search_term": "EXACT words the user typed",
            "search_term_view_status": "ADDED = already a keyword / EXCLUDED = already negative / NONE = not yet managed",
            "segments_date": "Date",
            "metrics_clicks": "Clicks from this search term",
            "metrics_cost_micros": "Spend wasted on this term",
            "metrics_conversions": "Conversions from this term — 0 = wasted spend",
            "metrics_impressions": "Times your ad showed for this term"
        },
        "links_to": ["p_ads_Campaign_9403250839"]
    }
}

CATEGORIES = ["All", "Structure", "Performance", "Attribution", "Account", "Labels"]
CATEGORY_COLORS = {
    "Structure":    "🔵",
    "Performance":  "🟢",
    "Attribution":  "🔴",
    "Account":      "🟡",
    "Labels":       "⚪"
}

# --- SIDEBAR ---
st.sidebar.header("🔍 Filter Tables")
selected_category = st.sidebar.selectbox("Category", CATEGORIES)
search_term       = st.sidebar.text_input("Search table name", "").lower()
rows_to_show      = st.sidebar.slider("Sample rows to load", 5, 50, 10, 5)

filtered_tables = {
    name: info for name, info in TABLE_INFO.items()
    if (selected_category == "All" or info["category"] == selected_category)
    and (search_term == "" or search_term in name.lower() or search_term in info["simple"].lower())
}

# --- OVERVIEW STATS (live from BigQuery) ---
@st.cache_data(ttl=3600)
def load_overview():
    try:
        campaigns = client.query(f"SELECT COUNT(*) as n FROM `{PROJECT_ID}.{DATASET}.p_ads_Campaign_9403250839`").to_dataframe()["n"][0]
        keywords  = client.query(f"SELECT COUNT(*) as n FROM `{PROJECT_ID}.{DATASET}.p_ads_Keyword_9403250839`").to_dataframe()["n"][0]
        ads       = client.query(f"SELECT COUNT(*) as n FROM `{PROJECT_ID}.{DATASET}.p_ads_Ad_9403250839`").to_dataframe()["n"][0]
        dates     = client.query(f"""
            SELECT MIN(segments_date) as min_d, MAX(segments_date) as max_d
            FROM `{PROJECT_ID}.{DATASET}.p_ads_CampaignStats_9403250839`
        """).to_dataframe()
        date_range = f"{dates['min_d'][0].strftime('%b %d')} – {dates['max_d'][0].strftime('%b %d %Y')}"
        return int(campaigns), int(keywords), int(ads), date_range
    except:
        return 56, 2866, 316, "Loading..."

campaigns, keywords, ads, date_range = load_overview()

st.markdown("---")
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Total Tables (p_ads_)", "34 with data")
c2.metric("Campaigns", f"{campaigns:,}")
c3.metric("Keywords",  f"{keywords:,}")
c4.metric("Ads",       f"{ads:,}")
c5.metric("Data range", date_range)
st.markdown("---")

# --- IMPORTANT NOTES ---
with st.expander("⚠️ Important things to know before querying"):
    st.markdown("""
**Always use `p_ads_` tables.** The `ads_` tables are empty views — ignore them completely.

**Money is stored in MICROS.** Divide `metrics_cost_micros` by **1,000,000** to get dollars.
Example: `417750000 ÷ 1000000 = $417.75`

**`_PARTITIONTIME` vs `segments_date`.** Always filter by `segments_date` not `_PARTITIONTIME`.

**`click_view_gclid` in `p_ads_ClickStats`** is the most important column in the whole system.
It links a Google Ad click to a ServiceTitan job — that's how GPROAS is calculated.

**Quality score 1-4** on a keyword = you're paying the **stupidity tax** — Google charges you more because your ad is irrelevant to that keyword.
""")

# --- TABLE GRID ---
st.subheader(f"📋 Tables ({len(filtered_tables)} shown)")

cols = st.columns(4)
selected_table = st.session_state.get("selected_ga_table", None)

for i, (tname, tinfo) in enumerate(filtered_tables.items()):
    col = cols[i % 4]
    with col:
        is_selected = selected_table == tname
        label = f"{tinfo['emoji']} {tname.replace('p_ads_','').replace('_9403250839','')}"
        if st.button(label, key=f"btn_{tname}", use_container_width=True,
                     type="primary" if is_selected else "secondary"):
            st.session_state["selected_ga_table"] = None if is_selected else tname
            st.rerun()

# --- TABLE DETAIL ---
selected_table = st.session_state.get("selected_ga_table", None)

if selected_table and selected_table in TABLE_INFO:
    info = TABLE_INFO[selected_table]
    st.markdown("---")
    st.markdown(f"## {info['emoji']} `{selected_table}`")
    st.markdown(f"**{info['simple']}**")
    st.info(info["description"])

    col1, col2 = st.columns([2, 1])
    with col1:
        st.markdown("#### 📌 What each column means")
        for col_name, col_desc in info["key_columns"].items():
            st.markdown(f"- **`{col_name}`** — {col_desc}")
    with col2:
        st.markdown("#### 🔗 Connects to")
        if info["links_to"]:
            for link in info["links_to"]:
                short = link.replace("p_ads_","").replace("_9403250839","")
                st.markdown(f"- `{short}`")
        else:
            st.markdown("_No direct joins_")
        st.markdown("#### 📁 Category")
        st.markdown(f"{CATEGORY_COLORS.get(info['category'], '⚪')} {info['category']}")

    st.markdown("---")
    st.markdown(f"#### 🔴 Live Data from BigQuery — `{selected_table}` ({rows_to_show} rows)")

    try:
        with st.spinner(f"Loading {rows_to_show} rows..."):
            df = client.query(f"""
                SELECT * FROM `{PROJECT_ID}.{DATASET}.{selected_table}`
                LIMIT {rows_to_show}
            """).to_dataframe()

        total = client.query(f"""
            SELECT COUNT(*) as total
            FROM `{PROJECT_ID}.{DATASET}.{selected_table}`
        """).to_dataframe()["total"][0]

        st.success(f"✅ Loaded {len(df)} rows")
        st.caption(f"📊 This table has **{total:,} total rows** in BigQuery")

        if total == 0:
            st.warning("⚠️ This table is currently empty — it will populate once campaigns are actively running.")
        else:
            st.dataframe(df, use_container_width=True, hide_index=True)
            csv = df.to_csv(index=False)
            st.download_button(
                label=f"⬇️ Download sample as CSV",
                data=csv,
                file_name=f"{selected_table}_sample.csv",
                mime="text/csv"
            )

    except Exception as e:
        st.error(f"❌ Could not load data: {e}")

else:
    st.markdown("")
    st.markdown("👆 **Click any table above to see its data and explanation**")